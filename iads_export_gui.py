"""GUI for building an iads-export manual_export.yaml file and running the export.

Run with any Python that has tkinter (no extra packages needed):
    python iads_export_gui.py

The export itself runs with the iads-export virtual environment's python
(<repo>\\ie_venv\\Scripts\\python.exe), which is equivalent to activating the
venv and running `python -m iads_export.manual <yaml>`.
"""
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRN_SCRIPT = os.path.join(SCRIPT_DIR, "selectFromPrn.py")
PLOT_SCRIPT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "csvdata_tools", "plotcsv.py"))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, ".iads_export_gui.json")
DEFAULT_REPO = r"C:\Users\MikeMuir\OneDrive - Merlin Labs\Desktop\git_work\iads-export"

IRIG_RE = re.compile(r"^\d{1,3}:\d{1,2}:\d{1,2}:\d{1,2}(\.\d+)?$")

# Help text adapted from the iads-export README / config/doc/manual_export_guide.yaml
HELP = {
    "directory": (
        "IADS Data Directory",
        "The location of the IADS Data Directory you want to export data from.",
    ),
    "time_format": (
        "Time Format",
        "Output time format for the timestamp column in the CSV.\n\n"
        "  IRIG  - formatted as \"242:19:39:37.000\" (day-of-year:HH:MM:SS.mmm), "
        "counted since the start of the new year.\n"
        "  SSNY  - seconds since new year, formatted as a float (DEFAULT).\n"
        "  SSM   - seconds since midnight, formatted as a float.",
    ),
    "name": (
        "Export Name",
        "A simple name to keep track of what each export does. It is only a label.",
    ),
    "enabled": (
        "Enabled",
        "Whether or not to actually run this export. Uncheck to keep the entry in "
        "the YAML file without running it.",
    ),
    "output_file": (
        "Output File",
        "Path of the CSV file you want written by this export.",
    ),
    "data_group_file": (
        "Data Group File",
        "A CSV file containing the list of parameters to export (a single header row "
        "of parameter names).\n\n"
        "Select an existing one, or build a new one - 'Build New...' launches "
        "selectFromPrn.py, where you load a .prn file, pick variables, and use "
        "'Export to CSV'. When you save, the CSV path is filled in here automatically.",
    ),
    "start_time": (
        "Start Time",
        "Start of the time range for exported data.\n\n"
        "  beginning - start of data collection.\n"
        "  IRIG      - formatted as \"242:19:39:37.000\", since the start of the "
        "new year (the GUI quotes it in the YAML for you).",
    ),
    "stop_time": (
        "Stop Time",
        "End of the time range for exported data.\n\n"
        "  end       - end of data collection.\n"
        "  seconds   - integer number of seconds after start_time.\n"
        "  IRIG      - formatted as \"242:19:39:37.000\", since the start of the "
        "new year (the GUI quotes it in the YAML for you).",
    ),
}


def yq(value):
    """Single-quote a string for YAML (safe for Windows backslash paths)."""
    return "'" + str(value).replace("'", "''") + "'"


def _parse_scalar(raw):
    """Parse one YAML scalar from the simple manual-export format."""
    raw = raw.strip()
    if raw[:1] == "'":
        end = raw.find("'", 1)
        while end != -1 and raw[end + 1:end + 2] == "'":
            end = raw.find("'", end + 2)
        return raw[1:end].replace("''", "'") if end != -1 else raw[1:]
    if raw[:1] == '"':
        end = raw.find('"', 1)
        inner = raw[1:end] if end != -1 else raw[1:]
        return inner.replace('\\\\', '\\').replace('\\"', '"')
    raw = re.split(r"\s+#", raw, maxsplit=1)[0].strip()
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw


def parse_manual_yaml(text):
    """Parse a manual export YAML file into {'directory', 'time_format', 'exports': [dict]}.

    Handles the flat layout used by iads-export (top-level keys plus a list of
    simple key/value mappings); it is not a general YAML parser.
    """
    result = {"exports": []}
    current = None
    in_exports = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indented = line[:1] in (" ", "	")
        if not indented:
            key, _, val = stripped.partition(":")
            in_exports = key == "exports"
            if not in_exports:
                result[key] = _parse_scalar(val)
            continue
        if not in_exports:
            continue
        if stripped.startswith("- "):
            current = {}
            result["exports"].append(current)
            stripped = stripped[2:].strip()
        if current is not None and ":" in stripped:
            key, _, val = stripped.partition(":")
            current[key.strip()] = _parse_scalar(val)
    return result


class LabeledRow:
    """Helper to lay out 'label [widget] [info]' rows on a grid."""

    @staticmethod
    def info_button(parent, key):
        title, text = HELP[key]
        return ttk.Button(
            parent, text="?", width=3,
            command=lambda: messagebox.showinfo(title, text, parent=parent.winfo_toplevel()),
        )


class ExportFrame(ttk.Frame):
    def __init__(self, parent, app, name="Export"):
        super().__init__(parent, padding=10)
        self.app = app
        self.columnconfigure(1, weight=1)

        self.name_var = tk.StringVar(value=name)
        self.enabled_var = tk.BooleanVar(value=True)
        self.output_var = tk.StringVar()
        self.group_var = tk.StringVar()
        self.start_mode = tk.StringVar(value="beginning")
        self.start_val = tk.StringVar()
        self.stop_mode = tk.StringVar(value="end")
        self.stop_val = tk.StringVar()

        r = 0
        ttk.Label(self, text="Name:").grid(row=r, column=0, sticky=tk.W, pady=4)
        ttk.Entry(self, textvariable=self.name_var).grid(row=r, column=1, sticky=tk.EW, padx=6)
        LabeledRow.info_button(self, "name").grid(row=r, column=2)

        r += 1
        ttk.Checkbutton(self, text="Enabled", variable=self.enabled_var).grid(
            row=r, column=1, sticky=tk.W, padx=6, pady=4)
        LabeledRow.info_button(self, "enabled").grid(row=r, column=2)

        r += 1
        ttk.Label(self, text="Output CSV:").grid(row=r, column=0, sticky=tk.W, pady=4)
        ttk.Entry(self, textvariable=self.output_var).grid(row=r, column=1, sticky=tk.EW, padx=6)
        ttk.Button(self, text="Browse...", command=self._browse_output).grid(row=r, column=3, padx=2)
        LabeledRow.info_button(self, "output_file").grid(row=r, column=2)

        r += 1
        ttk.Label(self, text="Data group file:").grid(row=r, column=0, sticky=tk.W, pady=4)
        ttk.Entry(self, textvariable=self.group_var).grid(row=r, column=1, sticky=tk.EW, padx=6)
        LabeledRow.info_button(self, "data_group_file").grid(row=r, column=2)
        btns = ttk.Frame(self)
        btns.grid(row=r, column=3)
        ttk.Button(btns, text="Select Existing...", command=self._browse_group).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Build New...", command=self._build_group).pack(side=tk.LEFT, padx=2)

        r += 1
        ttk.Label(self, text="Start time:").grid(row=r, column=0, sticky=tk.W, pady=4)
        f = ttk.Frame(self)
        f.grid(row=r, column=1, sticky=tk.W, padx=6)
        self.start_combo = ttk.Combobox(f, textvariable=self.start_mode, state="readonly",
                                        values=["beginning", "IRIG"], width=12)
        self.start_combo.pack(side=tk.LEFT)
        self.start_entry = ttk.Entry(f, textvariable=self.start_val, width=22)
        self.start_entry.pack(side=tk.LEFT, padx=6)
        ttk.Label(f, text="(e.g. 240:14:52:21.000)", foreground="gray").pack(side=tk.LEFT)
        LabeledRow.info_button(self, "start_time").grid(row=r, column=2)
        self.start_combo.bind("<<ComboboxSelected>>", lambda e: self._sync())

        r += 1
        ttk.Label(self, text="Stop time:").grid(row=r, column=0, sticky=tk.W, pady=4)
        f = ttk.Frame(self)
        f.grid(row=r, column=1, sticky=tk.W, padx=6)
        self.stop_combo = ttk.Combobox(f, textvariable=self.stop_mode, state="readonly",
                                       values=["end", "seconds after start", "IRIG"], width=18)
        self.stop_combo.pack(side=tk.LEFT)
        self.stop_entry = ttk.Entry(f, textvariable=self.stop_val, width=22)
        self.stop_entry.pack(side=tk.LEFT, padx=6)
        LabeledRow.info_button(self, "stop_time").grid(row=r, column=2)
        self.stop_combo.bind("<<ComboboxSelected>>", lambda e: self._sync())

        self._sync()

    def _sync(self):
        self.start_entry.configure(state="normal" if self.start_mode.get() == "IRIG" else "disabled")
        self.stop_entry.configure(state="disabled" if self.stop_mode.get() == "end" else "normal")

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="Output CSV", defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=self.app.initial_dir(self.output_var.get()))
        if path:
            self.output_var.set(os.path.normpath(path))

    def _browse_group(self):
        path = filedialog.askopenfilename(
            title="Select data group CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialdir=self.app.initial_dir(self.group_var.get()))
        if path:
            self.group_var.set(os.path.normpath(path))

    def _build_group(self):
        if not os.path.isfile(PRN_SCRIPT):
            messagebox.showerror("Missing script", f"Could not find:\n{PRN_SCRIPT}")
            return
        fd, result_file = tempfile.mkstemp(prefix="selectFromPrn_", suffix=".txt")
        os.close(fd)
        proc = subprocess.Popen([sys.executable, PRN_SCRIPT, "--result-file", result_file],
                                cwd=SCRIPT_DIR)

        def read_result():
            try:
                with open(result_file, encoding="utf-8") as f:
                    return f.read().strip()
            except OSError:
                return ""

        def poll():
            saved = read_result()
            if saved and os.path.normpath(saved) != self.group_var.get():
                self.group_var.set(os.path.normpath(saved))
            if proc.poll() is None:
                self.after(500, poll)
                return
            try:
                os.remove(result_file)
            except OSError:
                pass

        poll()

    def load(self, d):
        """Populate the fields from a parsed export mapping."""
        self.name_var.set(str(d.get("name", self.name_var.get())))
        self.enabled_var.set(bool(d.get("enabled", True)))
        self.output_var.set(str(d.get("output_file", "")))
        self.group_var.set(str(d.get("data_group_file", "")))
        start = str(d.get("start_time", "beginning"))
        if start == "beginning":
            self.start_mode.set("beginning")
        else:
            self.start_mode.set("IRIG")
            self.start_val.set(start)
        stop = d.get("stop_time", "end")
        if stop == "end":
            self.stop_mode.set("end")
        elif isinstance(stop, int):
            self.stop_mode.set("seconds after start")
            self.stop_val.set(str(stop))
        else:
            self.stop_mode.set("IRIG")
            self.stop_val.set(str(stop))
        self._sync()

    def validate(self):
        """Return an error string, or None if OK."""
        label = self.name_var.get() or "(unnamed)"
        if not self.output_var.get().strip():
            return f"[{label}] Output file is required."
        if not self.group_var.get().strip():
            return f"[{label}] Data group file is required."
        elif not os.path.isfile(self.group_var.get().strip()):
            return f"[{label}] Data group file does not exist."
        if self.start_mode.get() == "IRIG" and not IRIG_RE.match(self.start_val.get().strip()):
            return f"[{label}] Start time must look like 240:14:52:21.000"
        mode = self.stop_mode.get()
        val = self.stop_val.get().strip()
        if mode == "IRIG" and not IRIG_RE.match(val):
            return f"[{label}] Stop time must look like 240:14:52:21.000"
        if mode == "seconds after start" and not val.isdigit():
            return f"[{label}] Stop time seconds must be an integer."
        return None

    def to_yaml(self):
        start = yq(self.start_val.get().strip()) if self.start_mode.get() == "IRIG" else yq("beginning")
        mode = self.stop_mode.get()
        if mode == "end":
            stop = yq("end")
        elif mode == "IRIG":
            stop = yq(self.stop_val.get().strip())
        else:
            stop = str(int(self.stop_val.get().strip()))
        return (
            f"  - name: {yq(self.name_var.get().strip() or 'Export')}\n"
            f"    enabled: {'true' if self.enabled_var.get() else 'false'}\n"
            f"    output_file: {yq(self.output_var.get().strip())}\n"
            f"    data_group_file: {yq(self.group_var.get().strip())}\n"
            f"    start_time: {start}\n"
            f"    stop_time: {stop}\n"
        )


class App:
    def __init__(self, root):
        self.root = root
        root.title("IADS Export Builder")
        root.geometry("900x720")
        root.minsize(760, 560)

        self.settings = self._load_settings()
        self.repo_var = tk.StringVar(value=self.settings.get("repo", DEFAULT_REPO))
        self.dir_var = tk.StringVar(value=self.settings.get("directory", ""))
        self.tf_var = tk.StringVar(value=self.settings.get("time_format", "SSNY"))
        self.yaml_var = tk.StringVar(value=self.settings.get(
            "yaml", os.path.join(self.repo_var.get(), "config", "manual_export_gui.yaml")))
        self.log_queue = queue.Queue()
        self.running = False
        self.exports = []

        self._build_ui()
        if not self.load_yaml(self.yaml_var.get(), quiet=True):
            self._add_export()
        self._drain_log()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        top = ttk.LabelFrame(self.root, text="Global settings", padding=10)
        top.pack(fill=tk.X, padx=10, pady=(10, 4))
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="iads-export repo:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(top, textvariable=self.repo_var).grid(row=0, column=1, sticky=tk.EW, padx=6)
        ttk.Button(top, text="Browse...", command=self._browse_repo).grid(row=0, column=3)

        ttk.Label(top, text="Data directory:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(top, textvariable=self.dir_var).grid(row=1, column=1, sticky=tk.EW, padx=6)
        LabeledRow.info_button(top, "directory").grid(row=1, column=2)
        ttk.Button(top, text="Browse...", command=self._browse_dir).grid(row=1, column=3)

        ttk.Label(top, text="Time format:").grid(row=2, column=0, sticky=tk.W, pady=3)
        ttk.Combobox(top, textvariable=self.tf_var, state="readonly",
                     values=["IRIG", "SSNY", "SSM"], width=10).grid(row=2, column=1, sticky=tk.W, padx=6)
        LabeledRow.info_button(top, "time_format").grid(row=2, column=2)

        ttk.Label(top, text="YAML file:").grid(row=3, column=0, sticky=tk.W, pady=3)
        ttk.Entry(top, textvariable=self.yaml_var).grid(row=3, column=1, sticky=tk.EW, padx=6)
        yaml_btns = ttk.Frame(top)
        yaml_btns.grid(row=3, column=3)
        ttk.Button(yaml_btns, text="Load", command=lambda: self.load_yaml(self.yaml_var.get())).pack(
            side=tk.LEFT, padx=(0, 2))
        ttk.Button(yaml_btns, text="Browse...", command=self._browse_yaml).pack(side=tk.LEFT)

        ex = ttk.LabelFrame(self.root, text="Exports", padding=6)
        ex.pack(fill=tk.BOTH, expand=False, padx=10, pady=4)
        bar = ttk.Frame(ex)
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="+ Add export", command=self._add_export).pack(side=tk.LEFT)
        ttk.Button(bar, text="Remove current", command=self._remove_export).pack(side=tk.LEFT, padx=6)
        self.nb = ttk.Notebook(ex)
        self.nb.pack(fill=tk.X, pady=(6, 0))

        actions = ttk.Frame(self.root)
        actions.pack(fill=tk.X, padx=10, pady=4)
        self.action_btns = [
            ttk.Button(actions, text="Save YAML", command=self.save_yaml),
            ttk.Button(actions, text="Check parameters (--check)", command=lambda: self.run(["--check"])),
            ttk.Button(actions, text="Run Export", command=lambda: self.run([])),
        ]
        for b in self.action_btns:
            b.pack(side=tk.LEFT, padx=(0, 6))
        self.plot_btn = ttk.Button(actions, text="Plot Output (plotcsv)", command=self.plot_output,
                                   state="disabled")
        self.plot_btn.pack(side=tk.LEFT, padx=(0, 6))

        logf = ttk.LabelFrame(self.root, text="Output", padding=4)
        logf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))
        self.log = tk.Text(logf, height=10, wrap=tk.WORD, state="disabled")
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _add_export(self, data=None):
        n = len(self.exports) + 1
        frame = ExportFrame(self.nb, self, name=f"Export {n}")
        if data:
            frame.load(data)
        self.exports.append(frame)
        self.nb.add(frame, text=frame.name_var.get() or f"Export {n}")
        self.nb.select(frame)
        frame.name_var.trace_add("write", lambda *_, f=frame: self._retitle(f))

    def load_yaml(self, path, quiet=False):
        """Replace the current exports with those in a YAML file. Returns True if any loaded."""
        path = (path or "").strip()
        try:
            with open(path, encoding="utf-8") as f:
                data = parse_manual_yaml(f.read())
        except (OSError, UnicodeDecodeError) as e:
            if not quiet:
                messagebox.showerror("Cannot load", f"Could not read YAML file:\n{e}")
            return False
        exports = [e for e in data["exports"] if e]
        if not exports:
            if not quiet:
                messagebox.showwarning("Cannot load", "No exports found in that YAML file.")
            return False
        for frame in self.exports:
            self.nb.forget(frame)
            frame.destroy()
        self.exports = []
        for e in exports:
            self._add_export(e)
        self.nb.select(self.exports[0])
        # Header values from the settings file win; the YAML fills in anything missing.
        if not self.dir_var.get() and data.get("directory"):
            self.dir_var.set(str(data["directory"]))
        if "time_format" not in self.settings and data.get("time_format") in ("IRIG", "SSNY", "SSM"):
            self.tf_var.set(data["time_format"])
        self._log(f"Loaded {len(exports)} export(s) from {path}\n")
        return True

    def _retitle(self, frame):
        self.nb.tab(frame, text=frame.name_var.get() or "(unnamed)")

    def _remove_export(self):
        if len(self.exports) <= 1:
            messagebox.showinfo("Exports", "At least one export is required.")
            return
        frame = self.nametowidget(self.nb.select())
        self.nb.forget(frame)
        self.exports.remove(frame)
        frame.destroy()

    # ------------------------------------------------------------ browse
    def initial_dir(self, current):
        if current and os.path.isdir(os.path.dirname(current)):
            return os.path.dirname(current)
        return self.dir_var.get() if os.path.isdir(self.dir_var.get()) else None

    def _browse_repo(self):
        p = filedialog.askdirectory(title="iads-export repo folder", initialdir=self.repo_var.get() or None)
        if p:
            self.repo_var.set(os.path.normpath(p))

    def _browse_dir(self):
        p = filedialog.askdirectory(title="IADS Data Directory", initialdir=self.dir_var.get() or None)
        if p:
            self.dir_var.set(os.path.normpath(p))

    def _browse_yaml(self):
        p = filedialog.asksaveasfilename(
            title="Save manual export YAML", defaultextension=".yaml",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.yaml_var.get()) or None,
            initialfile=os.path.basename(self.yaml_var.get()) or None)
        if p:
            self.yaml_var.set(os.path.normpath(p))

    # -------------------------------------------------------------- yaml
    def _validate(self):
        d = self.dir_var.get().strip()
        if not d or not os.path.isdir(d):
            return "Data directory is required and must exist."
        if not self.yaml_var.get().strip():
            return "Choose a YAML file location."
        for e in self.exports:
            err = e.validate()
            if err:
                return err
        return None

    def save_yaml(self):
        err = self._validate()
        if err:
            messagebox.showerror("Cannot save", err)
            return False
        text = (
            f"directory: {yq(self.dir_var.get().strip())}\n"
            f"time_format: {self.tf_var.get()}\n"
            "exports:\n" + "\n".join(e.to_yaml() for e in self.exports)
        )
        path = self.yaml_var.get().strip()
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            messagebox.showerror("Cannot save", str(e))
            return False
        self._log(f"Saved {path}\n")
        return True

    # --------------------------------------------------------------- run
    def run(self, extra_args):
        if self.running:
            return
        repo = self.repo_var.get().strip()
        venv_python = os.path.join(repo, "ie_venv", "Scripts", "python.exe")
        if not os.path.isfile(venv_python):
            messagebox.showerror("Virtual environment not found",
                                 f"Expected:\n{venv_python}\n\nSet the iads-export repo folder.")
            return
        if not self.save_yaml():
            return
        cmd = [venv_python, "-m", "iads_export.manual", *extra_args, self.yaml_var.get().strip()]
        self._log("\n> " + " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n")
        self._set_running(True)
        self.plot_btn.configure(state="disabled")
        is_export = not extra_args
        threading.Thread(target=self._worker, args=(cmd, repo, is_export), daemon=True).start()

    def _worker(self, cmd, cwd, is_export):
        ok = False
        try:
            proc = subprocess.Popen(
                cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for line in proc.stdout:
                self.log_queue.put(line)
            code = proc.wait()
            ok = is_export and code == 0
            self.log_queue.put(f"\n[finished with exit code {code}]\n")
        except OSError as e:
            self.log_queue.put(f"\n[failed to start: {e}]\n")
        self.log_queue.put(("done", ok))

    # -------------------------------------------------------------- plot
    def _plottable_outputs(self):
        paths = [e.output_var.get().strip() for e in self.exports if e.enabled_var.get()]
        return [p for p in paths if os.path.isfile(p)]

    def plot_output(self):
        if not os.path.isfile(PLOT_SCRIPT):
            messagebox.showerror("Missing script", f"Could not find:\n{PLOT_SCRIPT}")
            return
        files = self._plottable_outputs()
        if not files:
            messagebox.showwarning("Nothing to plot", "No exported output file was found.")
            return
        path = files[0] if len(files) == 1 else self._choose_file(files)
        if not path:
            return
        subprocess.Popen([sys.executable, PLOT_SCRIPT, path], cwd=os.path.dirname(PLOT_SCRIPT))

    def _choose_file(self, files):
        dlg = tk.Toplevel(self.root)
        dlg.title("Choose file to plot")
        dlg.transient(self.root)
        dlg.grab_set()
        lb = tk.Listbox(dlg, width=90, height=min(len(files), 10), exportselection=False)
        for f in files:
            lb.insert(tk.END, f)
        lb.selection_set(0)
        lb.pack(padx=10, pady=10)
        result = []

        def ok():
            sel = lb.curselection()
            if sel:
                result.append(files[sel[0]])
            dlg.destroy()

        lb.bind("<Double-Button-1>", lambda e: ok())
        ttk.Button(dlg, text="Plot", command=ok).pack(pady=(0, 10))
        self.root.wait_window(dlg)
        return result[0] if result else None

    # --------------------------------------------------------------- log
    def _set_running(self, running):
        self.running = running
        for b in self.action_btns:
            b.configure(state="disabled" if running else "normal")

    def _drain_log(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple):
                    self._set_running(False)
                    if item[1] and self._plottable_outputs():
                        self.plot_btn.configure(state="normal")
                else:
                    self._log(item)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log)

    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert(tk.END, text)
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    # ---------------------------------------------------------- settings
    def _load_settings(self):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _on_close(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({"repo": self.repo_var.get(), "directory": self.dir_var.get(),
                           "time_format": self.tf_var.get(), "yaml": self.yaml_var.get()}, f)
        except OSError:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
