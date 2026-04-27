import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import pandas as pd


# ---------------------------------------------------------------------------

def load_csv(path):
    df = pd.read_csv(path)
    # Make column names unique if duplicates exist
    seen = {}
    cols = []
    for c in df.columns:
        if c in seen:
            seen[c] += 1
            cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            cols.append(c)
    df.columns = cols
    return df


def render(fig, df, time_col, variables, zeroize, subplots, shared_x, right_axis_vars=None):
    """Returns (ax_primary, ax_right_or_None). ax_primary is the first subplot in subplot mode."""
    fig.clear()
    right_axis_vars = right_axis_vars or set()
    vars_left  = [v for v in variables if v not in right_axis_vars]
    vars_right = [v for v in variables if v in right_axis_vars]

    t = df[time_col].copy()
    if zeroize:
        first = t.dropna().iloc[0] if not t.dropna().empty else 0
        t = t - first
    xlabel = f"{time_col} (s, zeroed)" if zeroize else time_col
    n = len(variables)

    if subplots and n > 1:
        axes = fig.subplots(n, 1, sharex=shared_x)
        for ax, var in zip(axes, variables):
            ax.plot(t, df[var])
            ax.set_ylabel(var, fontsize=8)
            ax.tick_params(labelsize=7)
        axes[-1].set_xlabel(xlabel)
        fig.tight_layout()
        return axes[0], None
    else:
        prop_cycle = matplotlib.rcParams["axes.prop_cycle"].by_key()["color"]
        ax = fig.add_subplot(111)
        for i, var in enumerate(vars_left):
            ax.plot(t, df[var], label=var, color=prop_cycle[i % len(prop_cycle)])
        ax.set_xlabel(xlabel)

        ax2 = None
        if vars_right:
            ax2 = ax.twinx()
            offset = len(vars_left)
            for i, var in enumerate(vars_right):
                ax2.plot(t, df[var], label=var, color=prop_cycle[(offset + i) % len(prop_cycle)],
                         linestyle="--")
            ax2.tick_params(labelsize=7)
            lines1, labels1 = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8)
        else:
            ax.legend(fontsize=8)

        fig.tight_layout()
        return ax, ax2


# ---------------------------------------------------------------------------

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("CSV Plotter")
        self.root.geometry("1000x680")
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        self.df = None
        self.time_col = None
        self.all_vars = []
        self.selected = []
        self.right_axis_vars = set()   # subset of selected on right axis
        self.ax  = None
        self.ax2 = None

        self._build()

    def _quit(self):
        sys.exit(0)

    # ---------------------------------------------------------------- build --

    def _build(self):
        # --- top bar ---
        bar = tk.Frame(self.root)
        bar.pack(fill=tk.X, padx=8, pady=4)
        tk.Button(bar, text="Open CSV…", command=self._open).pack(side=tk.LEFT)
        self.lbl_file = tk.Label(bar, text="No file loaded", fg="grey", anchor="w")
        self.lbl_file.pack(side=tk.LEFT, padx=8)

        # --- split pane ---
        pw = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=6, sashrelief=tk.RAISED)
        pw.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        left = tk.Frame(pw, width=220)
        pw.add(left, minsize=200)

        right = tk.Frame(pw)
        pw.add(right, minsize=500)

        self._build_sidebar(left)
        self._build_canvas(right)

    def _build_sidebar(self, p):
        # search
        tk.Label(p, text="Search:").pack(anchor="w", padx=4, pady=(6, 0))
        self.sv_search = tk.StringVar()
        self.sv_search.trace_add("write", lambda *_: self._filter())
        tk.Entry(p, textvariable=self.sv_search).pack(fill=tk.X, padx=4)

        # available list
        tk.Label(p, text="Available variables:").pack(anchor="w", padx=4, pady=(8, 0))
        frm = tk.Frame(p)
        frm.pack(fill=tk.BOTH, expand=True, padx=4)
        sb = tk.Scrollbar(frm)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.lb_avail = tk.Listbox(frm, selectmode=tk.EXTENDED,
                                   yscrollcommand=sb.set, exportselection=False)
        self.lb_avail.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.lb_avail.yview)
        self.lb_avail.bind("<Double-Button-1>", lambda _: self._add())

        # add / clear row
        row = tk.Frame(p)
        row.pack(fill=tk.X, padx=4, pady=2)
        tk.Button(row, text="Add →",    command=self._add).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row, text="Clear all", command=self._clear).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # selected list
        tk.Label(p, text="Selected (right-click to set axis):").pack(anchor="w", padx=4)
        frm2 = tk.Frame(p)
        frm2.pack(fill=tk.BOTH, expand=True, padx=4)
        sb2 = tk.Scrollbar(frm2)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.lb_sel = tk.Listbox(frm2, selectmode=tk.EXTENDED,
                                  yscrollcommand=sb2.set, exportselection=False)
        self.lb_sel.pack(fill=tk.BOTH, expand=True)
        sb2.config(command=self.lb_sel.yview)
        self.lb_sel.bind("<Double-Button-1>", lambda _: self._remove())
        self.lb_sel.bind("<Button-3>", self._sel_context_menu)

        tk.Button(p, text="Remove selected", command=self._remove).pack(
            fill=tk.X, padx=4, pady=(2, 4))

        # options
        opts = tk.LabelFrame(p, text="Options", padx=6, pady=4)
        opts.pack(fill=tk.X, padx=4, pady=4)

        self.var_zero    = tk.BooleanVar(value=True)
        self.var_sub     = tk.BooleanVar(value=False)
        self.var_sharex  = tk.BooleanVar(value=True)

        tk.Checkbutton(opts, text="Zeroize time",      variable=self.var_zero).pack(anchor="w")
        tk.Checkbutton(opts, text="Separate subplots", variable=self.var_sub).pack(anchor="w")
        tk.Checkbutton(opts, text="Shared X axis",     variable=self.var_sharex).pack(anchor="w")

        # action buttons
        tk.Button(p, text="Plot", command=self._plot,
                  bg="#2979ff", fg="white", font=("", 10, "bold")).pack(
            fill=tk.X, padx=4, pady=(4, 2))
        tk.Button(p, text="Set axis limits…", command=self._limits_dialog).pack(
            fill=tk.X, padx=4, pady=(0, 2))
        tk.Button(p, text="Export to new window", command=self._export,
                  bg="#388e3c", fg="white").pack(fill=tk.X, padx=4, pady=(0, 8))

    def _build_canvas(self, p):
        self.fig = Figure()
        self.canvas = FigureCanvasTkAgg(self.fig, master=p)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(self.canvas, p).update()

    # --------------------------------------------------------------- logic --

    def _open(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.df = load_csv(path)
        except Exception as e:
            messagebox.showerror("Error reading CSV", str(e))
            return
        self.time_col = self.df.columns[0]
        self.all_vars = list(self.df.columns[1:])
        self.selected = []
        self.right_axis_vars = set()
        self.lbl_file.config(text=path, fg="black")
        self._filter()
        self._refresh_sel()

    def _filter(self):
        q = self.sv_search.get().lower()
        self.lb_avail.delete(0, tk.END)
        for v in self.all_vars:
            if q in v.lower():
                self.lb_avail.insert(tk.END, v)

    def _refresh_sel(self):
        self.lb_sel.delete(0, tk.END)
        for v in self.selected:
            label = f"{v}  [R]" if v in self.right_axis_vars else v
            self.lb_sel.insert(tk.END, label)

    def _add(self):
        for i in self.lb_avail.curselection():
            v = self.lb_avail.get(i)
            if v not in self.selected:
                self.selected.append(v)
        self._refresh_sel()

    def _remove(self):
        drop_indices = set(self.lb_sel.curselection())
        kept = [(v) for i, v in enumerate(self.selected) if i not in drop_indices]
        removed = {v for i, v in enumerate(self.selected) if i in drop_indices}
        self.selected = kept
        self.right_axis_vars -= removed
        self._refresh_sel()

    def _clear(self):
        self.selected = []
        self.right_axis_vars = set()
        self._refresh_sel()

    def _sel_context_menu(self, event):
        # Select the item under the cursor if not already selected
        idx = self.lb_sel.nearest(event.y)
        if idx < 0 or idx >= len(self.selected):
            return
        if idx not in self.lb_sel.curselection():
            self.lb_sel.selection_clear(0, tk.END)
            self.lb_sel.selection_set(idx)

        var = self.selected[idx]
        menu = tk.Menu(self.root, tearoff=0)
        if var in self.right_axis_vars:
            menu.add_command(label="Move to left axis",
                             command=lambda: self._set_axis(idx, right=False))
        else:
            menu.add_command(label="Move to right axis",
                             command=lambda: self._set_axis(idx, right=True))
        menu.tk_popup(event.x_root, event.y_root)

    def _set_axis(self, idx, right):
        var = self.selected[idx]
        if right:
            self.right_axis_vars.add(var)
        else:
            self.right_axis_vars.discard(var)
        self._refresh_sel()

    def _limits_dialog(self):
        if self.ax is None:
            messagebox.showwarning("No plot", "Plot something first.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Set axis limits")
        dlg.resizable(False, False)
        dlg.grab_set()

        def labeled_row(parent, text, row, default):
            tk.Label(parent, text=text, anchor="w").grid(row=row, column=0, sticky="w", padx=6, pady=3)
            var = tk.StringVar(value=f"{default:.6g}")
            tk.Entry(parent, textvariable=var, width=14).grid(row=row, column=1, padx=6, pady=3)
            return var

        frm = tk.Frame(dlg)
        frm.pack(padx=12, pady=8)

        xmin, xmax = self.ax.get_xlim()
        ymin, ymax = self.ax.get_ylim()

        tk.Label(frm, text="X axis", font=("", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=6)
        sv_xmin = labeled_row(frm, "X min", 1, xmin)
        sv_xmax = labeled_row(frm, "X max", 2, xmax)

        tk.Label(frm, text="Left Y axis", font=("", 9, "bold")).grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 0))
        sv_ymin = labeled_row(frm, "Y min", 4, ymin)
        sv_ymax = labeled_row(frm, "Y max", 5, ymax)

        sv_y2min = sv_y2max = None
        if self.ax2 is not None:
            y2min, y2max = self.ax2.get_ylim()
            tk.Label(frm, text="Right Y axis", font=("", 9, "bold")).grid(row=6, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 0))
            sv_y2min = labeled_row(frm, "Y min", 7, y2min)
            sv_y2max = labeled_row(frm, "Y max", 8, y2max)

        def apply():
            try:
                self.ax.set_xlim(float(sv_xmin.get()), float(sv_xmax.get()))
                self.ax.set_ylim(float(sv_ymin.get()), float(sv_ymax.get()))
                if self.ax2 is not None and sv_y2min is not None:
                    self.ax2.set_ylim(float(sv_y2min.get()), float(sv_y2max.get()))
                self.canvas.draw()
            except ValueError:
                messagebox.showerror("Invalid input", "All limits must be numbers.", parent=dlg)

        def reset():
            self.ax.autoscale()
            if self.ax2 is not None:
                self.ax2.autoscale()
            self.canvas.draw()
            dlg.destroy()

        btn_row = tk.Frame(dlg)
        btn_row.pack(pady=(0, 10))
        tk.Button(btn_row, text="Apply",  command=apply,         bg="#2979ff", fg="white", width=8).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="Reset",  command=reset,         width=8).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_row, text="Close",  command=dlg.destroy,   width=8).pack(side=tk.LEFT, padx=4)

    def _ready(self):
        if self.df is None:
            messagebox.showwarning("No file", "Open a CSV file first.")
            return False
        if not self.selected:
            messagebox.showwarning("Nothing selected", "Select at least one variable.")
            return False
        return True

    def _plot(self):
        if not self._ready():
            return
        try:
            self.ax, self.ax2 = render(self.fig, self.df, self.time_col, self.selected,
                                       self.var_zero.get(), self.var_sub.get(),
                                       self.var_sharex.get(), self.right_axis_vars)
            self.canvas.draw()
        except Exception as e:
            messagebox.showerror("Plot error", str(e))

    def _export(self):
        if not self._ready():
            return
        win = tk.Toplevel(self.root)
        win.title("Plot")
        win.geometry("860x560")
        fig = Figure()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        NavigationToolbar2Tk(canvas, win).update()
        render(fig, self.df, self.time_col, self.selected,
               self.var_zero.get(), self.var_sub.get(), self.var_sharex.get(),
               self.right_axis_vars)
        canvas.draw()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
