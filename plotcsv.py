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


def render(fig, df, time_col, variables, zeroize, subplots, shared_x):
    fig.clear()
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
    else:
        ax = fig.add_subplot(111)
        for var in variables:
            ax.plot(t, df[var], label=var)
        ax.set_xlabel(xlabel)
        ax.legend(fontsize=8)

    fig.tight_layout()


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
        tk.Label(p, text="Selected:").pack(anchor="w", padx=4)
        frm2 = tk.Frame(p)
        frm2.pack(fill=tk.BOTH, expand=True, padx=4)
        sb2 = tk.Scrollbar(frm2)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.lb_sel = tk.Listbox(frm2, selectmode=tk.EXTENDED,
                                  yscrollcommand=sb2.set, exportselection=False)
        self.lb_sel.pack(fill=tk.BOTH, expand=True)
        sb2.config(command=self.lb_sel.yview)
        self.lb_sel.bind("<Double-Button-1>", lambda _: self._remove())

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
            self.lb_sel.insert(tk.END, v)

    def _add(self):
        for i in self.lb_avail.curselection():
            v = self.lb_avail.get(i)
            if v not in self.selected:
                self.selected.append(v)
        self._refresh_sel()

    def _remove(self):
        drop = {self.lb_sel.get(i) for i in self.lb_sel.curselection()}
        self.selected = [v for v in self.selected if v not in drop]
        self._refresh_sel()

    def _clear(self):
        self.selected = []
        self._refresh_sel()

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
            render(self.fig, self.df, self.time_col, self.selected,
                   self.var_zero.get(), self.var_sub.get(), self.var_sharex.get())
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
               self.var_zero.get(), self.var_sub.get(), self.var_sharex.get())
        canvas.draw()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
