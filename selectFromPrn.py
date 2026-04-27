import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fnmatch
import csv
import os


class PrnSelectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Select Variables from PRN File")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)

        self.all_variables = []
        self.selected_variables = []

        self._build_ui()

    def _build_ui(self):
        # Top bar: file loading
        top_frame = ttk.Frame(self.root, padding=8)
        top_frame.pack(fill=tk.X)

        ttk.Button(top_frame, text="Load .prn File", command=self.load_prn).pack(side=tk.LEFT)
        self.file_label = ttk.Label(top_frame, text="No file loaded", foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=10)

        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)
        ttk.Button(top_frame, text="Load existing .csv", command=self.load_csv).pack(side=tk.LEFT)
        self.csv_label = ttk.Label(top_frame, text="No csv loaded", foreground="gray")
        self.csv_label.pack(side=tk.LEFT, padx=10)

        # Search bar
        search_frame = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        search_frame.pack(fill=tk.X)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=6)
        ttk.Label(search_frame, text='(use * as wildcard)', foreground="gray").pack(side=tk.LEFT)
        ttk.Button(search_frame, text="Clear", command=self._clear_search).pack(side=tk.LEFT, padx=4)

        # Main panels
        panels = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        panels.pack(fill=tk.BOTH, expand=True)
        panels.columnconfigure(0, weight=1)
        panels.columnconfigure(2, weight=1)
        panels.rowconfigure(1, weight=1)

        # Available variables (left)
        ttk.Label(panels, text="Available Variables").grid(row=0, column=0, sticky=tk.W)
        self.avail_count = ttk.Label(panels, text="(0)", foreground="gray")
        self.avail_count.grid(row=0, column=0, sticky=tk.E)

        avail_frame = ttk.Frame(panels)
        avail_frame.grid(row=1, column=0, sticky=tk.NSEW)
        avail_frame.rowconfigure(0, weight=1)
        avail_frame.columnconfigure(0, weight=1)

        self.avail_list = tk.Listbox(avail_frame, selectmode=tk.EXTENDED, exportselection=False)
        avail_scroll = ttk.Scrollbar(avail_frame, orient=tk.VERTICAL, command=self.avail_list.yview)
        self.avail_list.configure(yscrollcommand=avail_scroll.set)
        self.avail_list.grid(row=0, column=0, sticky=tk.NSEW)
        avail_scroll.grid(row=0, column=1, sticky=tk.NS)
        self.avail_list.bind("<Double-Button-1>", lambda e: self.add_selected())

        # Middle buttons
        btn_frame = ttk.Frame(panels, padding=(6, 0))
        btn_frame.grid(row=1, column=1, sticky=tk.NS)
        btn_frame.rowconfigure((0, 1, 2, 3, 4), weight=1)

        ttk.Button(btn_frame, text="Add →\nAll Shown", command=self.add_all_shown, width=10).grid(row=1, column=0, pady=4)
        ttk.Button(btn_frame, text="Add →", command=self.add_selected, width=10).grid(row=2, column=0, pady=4)
        ttk.Button(btn_frame, text="← Remove", command=self.remove_selected, width=10).grid(row=3, column=0, pady=4)
        ttk.Button(btn_frame, text="← Remove\nAll", command=self.remove_all, width=10).grid(row=4, column=0, pady=4)

        # Selected variables (right)
        ttk.Label(panels, text="Selected Variables").grid(row=0, column=2, sticky=tk.W)
        self.sel_count = ttk.Label(panels, text="(0)", foreground="gray")
        self.sel_count.grid(row=0, column=2, sticky=tk.E)

        sel_frame = ttk.Frame(panels)
        sel_frame.grid(row=1, column=2, sticky=tk.NSEW)
        sel_frame.rowconfigure(0, weight=1)
        sel_frame.columnconfigure(0, weight=1)

        self.sel_list = tk.Listbox(sel_frame, selectmode=tk.EXTENDED, exportselection=False)
        sel_scroll = ttk.Scrollbar(sel_frame, orient=tk.VERTICAL, command=self.sel_list.yview)
        self.sel_list.configure(yscrollcommand=sel_scroll.set)
        self.sel_list.grid(row=0, column=0, sticky=tk.NSEW)
        sel_scroll.grid(row=0, column=1, sticky=tk.NS)
        self.sel_list.bind("<Double-Button-1>", lambda e: self.remove_selected())

        # Bottom bar: export
        bottom_frame = ttk.Frame(self.root, padding=8)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Button(
            bottom_frame, text="Export to CSV", command=self.export_csv
        ).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------ #
    # File loading
    # ------------------------------------------------------------------ #

    def load_prn(self):
        path = filedialog.askopenfilename(
            title="Open PRN File",
            filetypes=[("PRN files", "*.prn"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                names = []
                for line in f:
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    # Skip header row if present (Name column would be the literal "Name")
                    if parts[1].lower() == "name":
                        continue
                    names.append(parts[1])
        except OSError as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return

        self.all_variables = names
        self.file_label.configure(
            text=os.path.basename(path), foreground="black"
        )
        self._apply_filter()

    def load_csv(self):
        path = filedialog.askopenfilename(
            title="Open existing CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                first_row = next(reader, [])
                names = [cell.strip() for cell in first_row if cell.strip()]
        except OSError as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return

        self.remove_all()
        self._add_vars(names)
        self.csv_label.configure(text=os.path.basename(path), foreground="black")

    # ------------------------------------------------------------------ #
    # Filter / search
    # ------------------------------------------------------------------ #

    def _apply_filter(self):
        pattern = self.search_var.get().strip()
        if pattern:
            # Wrap in * so partial matches work without requiring explicit leading/trailing *
            wrapped = pattern if "*" in pattern else f"*{pattern}*"
            filtered = [v for v in self.all_variables if fnmatch.fnmatchcase(v.upper(), wrapped.upper())]
        else:
            filtered = list(self.all_variables)

        self.avail_list.delete(0, tk.END)
        for v in filtered:
            self.avail_list.insert(tk.END, v)
        self._update_counts()

    def _clear_search(self):
        self.search_var.set("")

    # ------------------------------------------------------------------ #
    # Add / remove
    # ------------------------------------------------------------------ #

    def add_selected(self):
        indices = self.avail_list.curselection()
        to_add = [self.avail_list.get(i) for i in indices]
        self._add_vars(to_add)

    def add_all_shown(self):
        to_add = list(self.avail_list.get(0, tk.END))
        self._add_vars(to_add)

    def _add_vars(self, vars_to_add):
        existing = set(self.selected_variables)
        for v in vars_to_add:
            if v not in existing:
                self.selected_variables.append(v)
                existing.add(v)
                self.sel_list.insert(tk.END, v)
        self._update_counts()

    def remove_selected(self):
        indices = list(self.sel_list.curselection())[::-1]  # reverse to delete safely
        for i in indices:
            self.sel_list.delete(i)
            del self.selected_variables[i]
        self._update_counts()

    def remove_all(self):
        self.sel_list.delete(0, tk.END)
        self.selected_variables.clear()
        self._update_counts()

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #

    def export_csv(self):
        if not self.selected_variables:
            messagebox.showwarning("Nothing to export", "No variables selected.")
            return

        path = filedialog.asksaveasfilename(
            title="Save CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.selected_variables)
        except OSError as e:
            messagebox.showerror("Error", f"Could not write file:\n{e}")
            return

        messagebox.showinfo("Exported", f"Saved {len(self.selected_variables)} variable(s) to:\n{path}")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _update_counts(self):
        self.avail_count.configure(text=f"({self.avail_list.size()})")
        self.sel_count.configure(text=f"({len(self.selected_variables)})")


def main():
    root = tk.Tk()
    app = PrnSelectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
