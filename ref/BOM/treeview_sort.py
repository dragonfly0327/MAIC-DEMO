"""
Generic Treeview Column Sorting Utility & Dialog.
Supports Unlimited N-Level Multi-Column Sorting (Primary, Secondary, Tertiary, etc.) as well as 3-state header clicks.
"""

import tkinter as tk
from tkinter import ttk


class SortRecordsDialog(tk.Toplevel):
    """
    Dialog allowing users to set dynamic multi-level column sort rules (Primary, Secondary, Tertiary, etc.).
    """
    def __init__(self, master, columns, current_sort_rules=None,
                 current_primary_col=None, current_primary_state=None,
                 current_secondary_col=None, current_secondary_state=None,
                 current_col=None, current_state=None):
        super().__init__(master)
        self.title("Sort Records")
        self.geometry("520x440")
        self.resizable(True, True)
        self.minsize(480, 360)
        self.configure(bg="#EBF8FF")
        self.transient(master)
        self.grab_set()

        self.columns = [c for c in columns if c and c != "(None)"]
        self.result_sort_rules = [] # List of tuples: [ (col_name, 'asc'|'desc'), ... ]

        # Parse incoming sort rules for backward compatibility
        rules = []
        if current_sort_rules:
            rules = list(current_sort_rules)
        else:
            pri_c = current_primary_col or current_col
            pri_s = current_primary_state or current_state
            if pri_c and pri_s:
                rules.append((pri_c, pri_s))
            if current_secondary_col and current_secondary_state:
                rules.append((current_secondary_col, current_secondary_state))

        if not rules and self.columns:
            rules.append((self.columns[0], "asc"))

        main = tk.Frame(self, bg="#EBF8FF", padx=20, pady=15)
        main.pack(fill="both", expand=True)

        tk.Label(main, text="Sort Table Records", font=("Segoe UI", 12, "bold"), fg="#1A365D", bg="#EBF8FF").pack(anchor="w", pady=(0, 2))
        tk.Label(main, text="Add and configure multi-level column sort rules:", font=("Segoe UI", 9, "italic"), fg="#4A5568", bg="#EBF8FF").pack(anchor="w", pady=(0, 10))

        # Canvas & Scrollbar for dynamic level rows
        container = tk.Frame(main, bg="#EBF8FF")
        container.pack(fill="both", expand=True, pady=5)

        self.canvas = tk.Canvas(container, bg="#EBF8FF", highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.rules_frame = tk.Frame(self.canvas, bg="#EBF8FF")

        self.rules_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.rules_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling setup
        def _on_mousewheel(event):
            try:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        self._on_mousewheel_func = _on_mousewheel

        def _bind_mousewheel(event=None):
            self.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event=None):
            self.unbind_all("<MouseWheel>")

        self.bind("<Enter>", _bind_mousewheel)
        self.bind("<Leave>", _unbind_mousewheel)
        self.bind("<MouseWheel>", _on_mousewheel)
        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        self.rules_frame.bind("<MouseWheel>", _on_mousewheel)
        _bind_mousewheel()

        self.level_rows = [] # Store row objects

        for r in rules:
            self._add_rule_row(initial_col=r[0], initial_state=r[1])

        # Bottom action bar
        bottom_bar = tk.Frame(main, bg="#EBF8FF")
        bottom_bar.pack(fill="x", pady=(15, 0))

        btn_add = tk.Button(bottom_bar, text="➕ Add Sort Level", command=self._add_rule_row, font=("Segoe UI", 9, "bold"), bg="#E2E8F0", fg="#1A365D", cursor="hand2")
        btn_add.pack(side="left")

        btn_clear = tk.Button(bottom_bar, text="Clear Sort", command=self._on_clear, font=("Segoe UI", 9), bg="#E2E8F0", cursor="hand2")
        btn_clear.pack(side="left", padx=10)

        btn_apply = tk.Button(bottom_bar, text="Apply Sort", command=self._on_apply, font=("Segoe UI", 9, "bold"), bg="#1A365D", fg="white", cursor="hand2")
        btn_apply.pack(side="right")

        btn_cancel = tk.Button(bottom_bar, text="Cancel", command=self.destroy, font=("Segoe UI", 9), cursor="hand2")
        btn_cancel.pack(side="right", padx=5)

        # Backward compatibility properties
        self.result_primary_col = None
        self.result_primary_state = None
        self.result_secondary_col = None
        self.result_secondary_state = None
        self.result_col = None
        self.result_state = None

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (260)
        y = (self.winfo_screenheight() // 2) - (220)
        self.geometry(f"+{x}+{y}")

    def destroy(self):
        try:
            self.unbind_all("<MouseWheel>")
        except Exception:
            pass
        super().destroy()

    def _get_level_title(self, idx):
        if idx == 1: return "Level 1 (Primary Sort)"
        elif idx == 2: return "Level 2 (Secondary Sort)"
        elif idx == 3: return "Level 3 (Tertiary Sort)"
        else: return f"Level {idx} Sort Rule"

    def _add_rule_row(self, initial_col=None, initial_state="asc"):
        level_idx = len(self.level_rows) + 1
        title_text = self._get_level_title(level_idx)

        lf = tk.LabelFrame(self.rules_frame, text=title_text, bg="#EBF8FF", fg="#1A365D", font=("Segoe UI", 9, "bold"), padx=10, pady=6)
        lf.pack(fill="x", pady=4)

        f1 = tk.Frame(lf, bg="#EBF8FF")
        f1.pack(fill="x", pady=2)

        cols_with_none = ["(None)"] + self.columns
        var_col = tk.StringVar(value=initial_col or (self.columns[0] if self.columns else "(None)"))
        tk.Label(f1, text="Column:", font=("Segoe UI", 9), bg="#EBF8FF", fg="#1A365D", width=8, anchor="w").pack(side="left")
        cmb_col = ttk.Combobox(f1, textvariable=var_col, values=cols_with_none, state="readonly", font=("Segoe UI", 9))
        cmb_col.pack(side="left", fill="x", expand=True, padx=(0, 10))

        dir_val = "Descending (▼)" if initial_state == "desc" else "Ascending (▲)"
        var_dir = tk.StringVar(value=dir_val)
        tk.Label(f1, text="Order:", font=("Segoe UI", 9), bg="#EBF8FF", fg="#1A365D", width=6, anchor="w").pack(side="left")
        cmb_dir = ttk.Combobox(f1, textvariable=var_dir, values=["Ascending (▲)", "Descending (▼)"], state="readonly", width=15, font=("Segoe UI", 9))
        cmb_dir.pack(side="left")

        if level_idx > 1:
            btn_del = tk.Button(f1, text="❌", command=lambda f=lf: self._remove_rule_row(f), bg="#EBF8FF", bd=0, cursor="hand2", fg="#E53E3E", font=("Segoe UI", 9, "bold"))
            btn_del.pack(side="right", padx=(5, 0))

        if hasattr(self, '_on_mousewheel_func'):
            lf.bind("<MouseWheel>", self._on_mousewheel_func)
            f1.bind("<MouseWheel>", self._on_mousewheel_func)

        row_data = {"col_var": var_col, "dir_var": var_dir, "frame": lf}
        self.level_rows.append(row_data)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _remove_rule_row(self, frame):
        for i, r in enumerate(self.level_rows):
            if r["frame"] == frame:
                r["frame"].destroy()
                self.level_rows.pop(i)
                break
        for idx, r in enumerate(self.level_rows, start=1):
            r["frame"].config(text=self._get_level_title(idx))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_clear(self):
        self.result_sort_rules = []
        self.result_primary_col = None
        self.result_primary_state = None
        self.result_secondary_col = None
        self.result_secondary_state = None
        self.result_col = None
        self.result_state = None
        self.destroy()

    def _on_apply(self):
        rules = []
        for r in self.level_rows:
            col = r["col_var"].get()
            d = r["dir_var"].get()
            if col and col != "(None)":
                direction = "desc" if "Descending" in d else "asc"
                if not any(rule[0] == col for rule in rules):
                    rules.append((col, direction))

        self.result_sort_rules = rules
        if rules:
            self.result_primary_col = rules[0][0]
            self.result_primary_state = rules[0][1]
            self.result_col = rules[0][0]
            self.result_state = rules[0][1]
            if len(rules) > 1:
                self.result_secondary_col = rules[1][0]
                self.result_secondary_state = rules[1][1]
            else:
                self.result_secondary_col = None
                self.result_secondary_state = None
        else:
            self._on_clear()
            return
        self.destroy()


def attach_treeview_sort(tree, col_types=None):
    """
    Attaches click-to-sort behavior supporting N-level multi-column sort tracking.
    """
    col_types = col_types or {}
    sort_rules = [] # List of (col, direction)
    initial_items_order = []

    def _sort_col(col):
        nonlocal initial_items_order, sort_rules
        current_children = list(tree.get_children(''))
        if not initial_items_order or set(initial_items_order) != set(current_children):
            initial_items_order = list(current_children)

        # Look for existing rule for clicked col
        existing_idx = next((i for i, r in enumerate(sort_rules) if r[0] == col), -1)

        if existing_idx == 0:
            # Clicked primary rule -> cycle ASC -> DESC -> REMOVE
            col_name, state = sort_rules[0]
            if state == 'asc':
                sort_rules[0] = (col_name, 'desc')
            else:
                sort_rules.pop(0)
        elif existing_idx > 0:
            # Clicked existing non-primary rule -> move to primary and toggle
            col_name, state = sort_rules.pop(existing_idx)
            new_state = 'desc' if state == 'asc' else 'asc'
            sort_rules.insert(0, (col_name, new_state))
        else:
            # New rule -> insert as primary
            sort_rules.insert(0, (col, 'asc'))

        if not sort_rules:
            for index, child in enumerate(initial_items_order):
                if child in tree.get_children(''):
                    tree.move(child, '', index)
        else:
            apply_multi_level_treeview_sort(tree, sort_rules, col_types)

    try:
        cols = tree['columns']
        if isinstance(cols, (tuple, list)):
            for col in cols:
                tree.heading(col, command=lambda c=col: _sort_col(c))
    except Exception:
        pass


def apply_multi_level_treeview_sort(tree, sort_rules, col_types=None):
    """
    Sorts a Treeview in place using a list of sort_rules = [ (col, 'asc'|'desc'), ... ]
    Applies stable sorts in reverse priority order and updates column headings.
    """
    col_types = col_types or {}
    if not tree.get_children(''):
        return

    def _parse_val(v, c_name):
        if v is None: v = ""
        v_str = str(v).strip()
        c_type = col_types.get(c_name, 'str')
        if c_type == 'num':
            try: return (0, float(v_str.replace(',', '')))
            except (ValueError, TypeError): return (1, v_str.lower())
        else:
            try: return (0, float(v_str.replace(',', '')))
            except (ValueError, TypeError): return (1, v_str.lower())

    # Apply stable sorts in REVERSE order of rule priority
    for col_name, direction in reversed(sort_rules):
        rev = (direction == 'desc')
        row_tuples = [(tree.set(child, col_name), child) for child in tree.get_children('')]
        row_tuples.sort(key=lambda x: _parse_val(x[0], col_name), reverse=rev)
        for index, (_, child) in enumerate(row_tuples):
            tree.move(child, '', index)

    # Update headings with arrows and priority numbers
    rule_map = {col: (direction, idx + 1) for idx, (col, direction) in enumerate(sort_rules)}
    cols = tree['columns']
    for c in cols:
        curr_text = str(tree.heading(c, 'text'))
        # Strip existing indicators
        for i in range(1, 10):
            curr_text = curr_text.replace(f" ▲ ({i})", "").replace(f" ▼ ({i})", "")
        curr_text = curr_text.replace(" ▲", "").replace(" ▼", "")

        if c in rule_map:
            direction, priority = rule_map[c]
            arrow = " ▲" if direction == 'asc' else " ▼"
            if len(sort_rules) > 1:
                curr_text += f"{arrow} ({priority})"
            else:
                curr_text += f"{arrow}"
        tree.heading(c, text=curr_text)
