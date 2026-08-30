import tkinter as tk
from tkinter import ttk
import os
import json
from datetime import datetime

# --- Reusable Premium Button Styling Helper ---
def apply_premium_button_style(btn, is_primary=True, font_family="Segoe UI"):
    """
    Applies unified premium flat styling to standard tk.Button widgets.
    """
    if is_primary:
        # Primary Action Color Palette (Dark Navy #1A365D with Bold White Text)
        bg_color = "#1A365D"
        fg_color = "#FFFFFF"
        hover_bg = "#0077B6"
        active_bg = "#2B71B9"
        font = (font_family, 10, "bold")
    else:
        # Neutral / Cancel Color Palette (Slate Gray #E2E8F0 with Dark Text)
        bg_color = "#E2E8F0"
        fg_color = "#2D3748"
        hover_bg = "#CBD5E0"
        active_bg = "#CBD5E0"
        font = (font_family, 10)

    btn.config(
        bg=bg_color,
        fg=fg_color,
        activebackground=active_bg,
        activeforeground=fg_color,
        bd=0,
        relief="flat",
        padx=15,
        pady=5,
        cursor="hand2",
        font=font
    )

    def on_enter(e):
        btn.config(bg=hover_bg)
    def on_leave(e):
        btn.config(bg=bg_color)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)


# --- Reusable Premium Window Centering Helper ---
def center_window_on_parent_or_screen(window, width=None, height=None):
    """
    Dynamically centers a Toplevel window on its parent, or falls back to the screen.
    """
    window.update_idletasks()
    
    # Get active dimensions
    w = width or window.winfo_width()
    h = height or window.winfo_height()
    
    # Fallback to parsed geometry string if not mapped yet
    if w <= 1 or h <= 1:
        try:
            geom = window.geometry()
            size_part = geom.split("+")[0]
            w_parsed, h_parsed = map(int, size_part.split("x"))
            w = w_parsed
            h = h_parsed
        except:
            w = width or 400
            h = height or 300

    # Always resolve master first from the window object
    try:
        master = window.master
    except:
        master = None

    # Override large database/workflow windows to fixed 1200x700
    if w >= 800 or h >= 450:
        w, h = 1200, 700
        master = None

    # Center on master if master is visible and mapped (for small popups/dialogs)
    if master and hasattr(master, 'winfo_viewable') and master.winfo_exists() and master.winfo_viewable() and master.winfo_width() > 1:
        try:
            x = max(0, master.winfo_rootx() + (master.winfo_width() // 2) - (w // 2))
            y = max(0, master.winfo_rooty() + (master.winfo_height() // 2) - (h // 2))
            window.geometry(f"{w}x{h}+{x}+{y}")
            return
        except:
            pass

    # Screen fallback
    try:
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = max(0, (screen_width // 2) - (w // 2))
        y = max(0, (screen_height // 2) - (h // 2))
        window.geometry(f"{w}x{h}+{x}+{y}")
    except:
        window.geometry(f"{w}x{h}+50+50")


# --- Reusable Multi-Value Text Input Dialog ---
# --- Reusable Multi-Value Text Input Dialog ---
class MultiValueInputDialog(tk.Toplevel):
    """
    Standard popup dialog to enter multiple values (one per line).
    Supports available_options listbox search on left and filter text area on right.
    """
    def __init__(self, master, title, initial_values=None, available_options=None):
        super().__init__(master)
        self.title(title)
        self.configure(bg="#EBF8FF")
        self.transient(master)
        self.grab_set()

        self.initial_values = initial_values or []
        self.available_options = available_options if available_options is not None else []
        self.result = None

        self._create_widgets()
        w, h = (800, 550) if self.available_options else (450, 500)
        center_window_on_parent_or_screen(self, w, h)

        self._wait_var = tk.IntVar()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_variable(self._wait_var)

    def _create_widgets(self):
        btn_frame = tk.Frame(self, bg="#EBF8FF")
        btn_frame.pack(side="bottom", fill="x", padx=15, pady=(0, 15))

        btn_cancel = tk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=12)
        apply_premium_button_style(btn_cancel, is_primary=False)
        btn_cancel.pack(side="left")

        btn_clear = tk.Button(btn_frame, text="Clear", command=self._on_clear, width=12)
        apply_premium_button_style(btn_clear, is_primary=False)
        btn_clear.pack(side="left", padx=10)

        btn_ok = tk.Button(btn_frame, text="Confirm", command=self._on_confirm, width=12)
        apply_premium_button_style(btn_ok, is_primary=True)
        btn_ok.pack(side="right", padx=5)

        main_frame = tk.Frame(self, bg="#EBF8FF")
        main_frame.pack(side="top", fill="both", expand=True, padx=15, pady=(15, 0))

        if self.available_options:
            split_frame = tk.Frame(main_frame, bg="#EBF8FF")
            split_frame.pack(fill="both", expand=True)

            # LEFT PANE: Available Values
            left_frame = tk.LabelFrame(split_frame, text="Available Values", font=("Segoe UI", 10, "bold"), fg="#1A365D", bg="#EBF8FF", padx=10, pady=10)
            left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

            search_frame = tk.Frame(left_frame, bg="#EBF8FF")
            search_frame.pack(fill="x", pady=(0, 5))
            tk.Label(search_frame, text="Search:", font=("Segoe UI", 10), bg="#EBF8FF", fg="#1A365D").pack(side="left")
            self.search_var = tk.StringVar()
            self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Segoe UI", 10), bd=1, relief="solid")
            self.search_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
            self.search_var.trace_add("write", lambda *args: self._filter_options())

            list_container = tk.Frame(left_frame, bg="#EBF8FF")
            list_container.pack(fill="both", expand=True, pady=5)

            self.listbox = tk.Listbox(list_container, selectmode="extended", font=("Segoe UI", 10), bd=1, relief="solid")
            list_scroll_y = ttk.Scrollbar(list_container, orient="vertical", command=self.listbox.yview)
            list_scroll_x = ttk.Scrollbar(list_container, orient="horizontal", command=self.listbox.xview)
            self.listbox.configure(yscrollcommand=list_scroll_y.set, xscrollcommand=list_scroll_x.set)
            list_scroll_y.pack(side="right", fill="y")
            list_scroll_x.pack(side="bottom", fill="x")
            self.listbox.pack(side="left", fill="both", expand=True)

            self.listbox.bind("<Double-Button-1>", lambda e: self._add_selected())

            for opt in self.available_options:
                self.listbox.insert(tk.END, opt)

            btn_add = tk.Button(left_frame, text="Add Selected ➡️", command=self._add_selected)
            apply_premium_button_style(btn_add, is_primary=True)
            btn_add.pack(anchor="e", pady=(5, 0))

            # RIGHT PANE: Filter List (One per line)
            right_frame = tk.LabelFrame(split_frame, text="Filter List (One per line)", font=("Segoe UI", 10, "bold"), fg="#1A365D", bg="#EBF8FF", padx=10, pady=10)
            right_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

            text_container = tk.Frame(right_frame, bg="#EBF8FF")
            text_container.pack(fill="both", expand=True, pady=5)

            self.text_area = tk.Text(text_container, font=("Segoe UI", 10), bd=1, relief="solid")
            text_scroll = ttk.Scrollbar(text_container, orient="vertical", command=self.text_area.yview)
            self.text_area.configure(yscrollcommand=text_scroll.set)
            text_scroll.pack(side="right", fill="y")
            self.text_area.pack(side="left", fill="both", expand=True)

            if self.initial_values:
                self.text_area.insert("1.0", "\n".join(self.initial_values))
        else:
            tk.Label(
                main_frame, 
                text="Filter List (One per line):", 
                font=("Segoe UI", 10, "bold"), 
                fg="#1A365D", 
                bg="#EBF8FF"
            ).pack(anchor="w", pady=(0, 5))

            self.text_area = tk.Text(
                main_frame, 
                height=15, 
                width=40, 
                font=("Segoe UI", 10), 
                bd=1, 
                relief="solid"
            )
            self.text_area.pack(fill="both", expand=True, pady=5)
            
            if self.initial_values:
                self.text_area.insert("1.0", "\n".join(self.initial_values))

    def _filter_options(self):
        if not hasattr(self, 'listbox'):
            return
        query = self.search_var.get().strip().lower()
        self.listbox.delete(0, tk.END)
        for opt in self.available_options:
            if not query or query in str(opt).lower():
                self.listbox.insert(tk.END, opt)

    def _add_selected(self):
        if not hasattr(self, 'listbox'):
            return
        selected_indices = self.listbox.curselection()
        if not selected_indices:
            return
        selected_vals = [self.listbox.get(i) for i in selected_indices]
        
        current_text = self.text_area.get("1.0", "end-1c")
        existing_lines = [line.strip() for line in current_text.split("\n") if line.strip()]
        
        for val in selected_vals:
            if val not in existing_lines:
                existing_lines.append(str(val))
                
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", "\n".join(existing_lines))

    def _on_clear(self):
        self.text_area.delete("1.0", "end")

    def _on_cancel(self):
        self.result = None
        self._wait_var.set(1)
        self.destroy()

    def _on_confirm(self):
        content = self.text_area.get("1.0", "end-1c")
        self.result = [line.strip() for line in content.split("\n") if line.strip()]
        self._wait_var.set(1)
        self.destroy()


# --- Reusable Premium View History / Change Log Dialog ---
class StandardHistoryDialog(tk.Toplevel):
    """
    Standard Reusable Change Log / History Viewer.
    Presents changes in a premium alternating table, separated by date.
    
    Accepts:
        parent: Parent window instance.
        record_title: Label displaying what record this history represents (e.g., 'MPN 123 | Supplier ABC').
        history_list: A list of dicts. Each dict must follow this structure:
            {
                "Date": "DD.MM.YYYY",
                "Time": "HH:MM:SS",
                "Changed By": "Username",
                "Field Name": "FieldName",
                "Old Value": "PreviousVal",
                "New Value": "NewVal"
            }
    """
    def __init__(self, parent, record_title, history_list):
        super().__init__(parent)
        self._skip_autofit = True
        self.title(f"Display Changes - {record_title}")
        self.resizable(True, True)
        self.configure(bg="#EBF8FF")
        try:
            self.grab_set()
        except Exception:
            pass

        self.record_title = record_title
        self.history_list = history_list

        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 1200, 700
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.minsize(900, 450)
        except Exception:
            self.geometry("1200x700")

        self._build_ui()

    def _build_ui(self):
        # 1. SAP-style Blue Header Title Bar
        header_frame = tk.Frame(self, bg="#dcedf5", height=50)
        header_frame.pack(side="top", fill="x")
        
        tk.Label(
            header_frame, 
            text=f"📋  Display Changes: {self.record_title}", 
            font=("Segoe UI", 13, "bold", "italic"), 
            bg="#dcedf5", 
            fg="#1A365D"
        ).pack(side="left", padx=15, pady=10)

        # 2. Bottom Close Action Button packed FIRST to guarantee visibility
        btn_frame = tk.Frame(self, bg="#EBF8FF", pady=10)
        btn_frame.pack(side="bottom", fill="x")
        tk.Label(
            btn_frame,
            text=f"Total records: {len(self.history_list)}",
            font=("Segoe UI", 9),
            fg="#4a4a4a", bg="#EBF8FF"
        ).pack(side="left", padx=15)
        btn_close = tk.Button(btn_frame, text="Close", command=self.destroy)
        apply_premium_button_style(btn_close, is_primary=False)
        btn_close.pack(side="right", padx=15)

        # 3. Main Content Frame fills remaining space above bottom buttons
        content_frame = tk.Frame(self, bg="#EBF8FF", padx=10, pady=5)
        content_frame.pack(side="top", fill="both", expand=True)

        style = ttk.Style(self)
        style.configure("History.Treeview", font=("Segoe UI", 10), rowheight=38)
        style.configure("History.Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#dcedf5", foreground="#1A365D")

        # 4. Treeview Table Layout
        cols = ("Date", "Time", "Changed By", "Field Name", "New Value", "Old Value")
        self.tree = ttk.Treeview(content_frame, columns=cols, show="headings", style="History.Treeview", selectmode="none")
        
        col_widths = {
            "Date": 110,
            "Time": 90,
            "Changed By": 170,
            "Field Name": 350,
            "New Value": 240,
            "Old Value": 240
        }
        for col in cols:
            self.tree.heading(col, text=col, anchor="w")
            self.tree.column(col, width=col_widths.get(col, 150), minwidth=80, stretch=False, anchor="w")

        # Scrollbar integration
        y_scroll = ttk.Scrollbar(content_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(content_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        
        y_scroll.pack(side="right", fill="y")
        x_scroll.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        # Custom Styling Tags for alternating rows & separation
        self.tree.tag_configure("oddrow", background="#ffffff")
        self.tree.tag_configure("evenrow", background="#f0f4f8")
        self.tree.tag_configure("separator", background="#dcdcdc")

        # 5. Populate history (Newest changes first)
        current_date = None
        row_idx = 0
        for h in reversed(self.history_list):
            h_date = h.get("Date", "")
            
            # Insert a neat grey separator line when the date changes
            if current_date != h_date:
                if current_date is not None:
                    self.tree.insert("", "end", values=("", "", "", "", "", ""), tags=("separator",))
                current_date = h_date
                
            tag = "evenrow" if row_idx % 2 == 0 else "oddrow"
            self.tree.insert(
                "", 
                "end", 
                values=(
                    h.get("Date", ""),
                    h.get("Time", ""),
                    h.get("Changed By", ""),
                    h.get("Field Name", ""),
                    h.get("New Value", ""),
                    h.get("Old Value", "")
                ), 
                tags=(tag,)
            )
            row_idx += 1


# --- Reusable Premium Multi-Value Filter Dialog ---
class StandardFilterDialog(tk.Toplevel):
    """
    Standard Reusable Multi-Value Filter Dialog.
    Generates a premium form that supports both single string searches
    and multi-value selection popups (one entry per line).
    
    Accepts:
        master: The parent window.
        title: Title of the filter window.
        fields_config: List of tuples or dicts representing rows to filter:
            [
                ("Date", "Source Date"),     # (key_name, display_label)
                ("Desc", "Description"),
                ("Supp", "Supplier"),
                ("MPN", "MPN")
            ]
        initial_filters: Current dict of active filter states. e.g.:
            {
                "Date": ["18.05.2026", "17.05.2026"],
                "Desc": [],
                "Supp": ["Radysis"],
                "MPN": []
            }
            
    Returns:
        result: On "Execute Filter", returns an updated dictionary of filter lists:
            { "Date": [...], "Desc": [...], "Supp": [...], "MPN": [...] }
        or None if cancelled.
    """
    def __init__(self, master, title, fields_config, initial_filters=None, available_options_map=None):
        super().__init__(master)
        self.title(title or "Search Criteria")
        win_h = max(380, 160 + len(fields_config) * 42)
        # self.geometry(f"520x{win_h}")
        self.configure(bg="#EBF8FF")
        self.transient(master)
        self.grab_set()

        self.fields_config = fields_config
        self.initial_filters = initial_filters or {}
        self.available_options_map = available_options_map or {}
        
        # Internal filter storage
        self.filter_data = {}
        # StringVar values displayed in Entry fields
        self.string_vars = {}

        # Initialize _wait_var BEFORE _build_ui so button callbacks never crash
        self._wait_var = tk.IntVar()

        # Initialize filter values and display strings
        for key, label in self.fields_config:
            vals = self.initial_filters.get(key, [])
            self.filter_data[key] = list(vals)
            self.string_vars[key] = tk.StringVar(value=self._fmt_display_val(vals))

        self.result = None
        self._build_ui()
        center_window_on_parent_or_screen(self, 520, win_h)

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_variable(self._wait_var)

    def _fmt_display_val(self, vals):
        if not vals:
            return ""
        if len(vals) == 1:
            return vals[0]
        return f"<{len(vals)} values selected>"

    def _build_ui(self):
        main_frame = tk.Frame(self, bg="#EBF8FF", padx=20, pady=15)
        main_frame.pack(fill="both", expand=True)

        tk.Label(
            main_frame, 
            text="Search Criteria", 
            font=("Segoe UI", 12, "bold"), 
            fg="#1A365D", 
            bg="#EBF8FF"
        ).pack(anchor="w", pady=(0, 10))

        # Dynamically build filter rows based on config
        for key, label in self.fields_config:
            row_frame = tk.Frame(main_frame, bg="#EBF8FF")
            row_frame.pack(fill="x", pady=5)

            # Label (fixed width for perfect vertical alignment)
            lbl = tk.Label(
                row_frame, 
                text=f"{label}:", 
                width=18, 
                anchor="w", 
                font=("Segoe UI", 10, "bold"), 
                bg="#EBF8FF", 
                fg="#1A365D"
            )
            lbl.pack(side="left")

            # Entry box
            entry = tk.Entry(
                row_frame, 
                textvariable=self.string_vars[key], 
                font=("Segoe UI", 10), 
                bd=1, 
                relief="solid"
            )
            entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

            # Multi-value selection trigger button (⁝≡)
            btn_multi = tk.Button(
                row_frame, 
                text="⁝≡", 
                width=4, 
                bg="#1A365D", 
                fg="white", 
                font=("Segoe UI", 10, "bold"),
                bd=0, 
                relief="flat", 
                activebackground="#0077B6",
                cursor="hand2",
                command=lambda k=key, v=self.string_vars[key]: self._open_multi_input(k, v)
            )
            btn_multi.pack(side="left")

        # Instruction Note at the bottom
        tk.Label(
            main_frame, 
            text="* Use the ⁝≡ button next to fields to input multiple values.", 
            font=("Segoe UI", 9, "italic"), 
            fg="#4A5568", 
            bg="#EBF8FF"
        ).pack(anchor="w", pady=(15, 0))

        # Bottom Button controls
        btn_frame = tk.Frame(main_frame, bg="#EBF8FF")
        btn_frame.pack(fill="x", pady=(20, 0))

        btn_cancel = tk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=10)
        apply_premium_button_style(btn_cancel, is_primary=False)
        btn_cancel.pack(side="left")

        btn_clear = tk.Button(btn_frame, text="Clear All", command=self._on_clear_all, width=10)
        apply_premium_button_style(btn_clear, is_primary=False)
        btn_clear.pack(side="left", padx=10)

        btn_execute = tk.Button(btn_frame, text="Execute Filter", command=self._on_execute, width=14)
        apply_premium_button_style(btn_execute, is_primary=True)
        btn_execute.pack(side="right")

    def _open_multi_input(self, key, var):
        curr_vals = self.filter_data.get(key, [])
        
        # If the user typed something in directly, load it as the initial item
        if not curr_vals and var.get() and not var.get().startswith("<"):
            curr_vals = [var.get()]

        options = self.available_options_map.get(key, None)
        title_key = key.replace("_", " ").title()
        dialog = MultiValueInputDialog(self, f"Multi-Selection for {title_key}", curr_vals, available_options=options)
        if dialog.result is not None:
            self.filter_data[key] = dialog.result
            var.set(self._fmt_display_val(dialog.result))

        else:
            self.filter_criteria = None
            if hasattr(self, 'populate_tree'):
                self.populate_tree()
            elif hasattr(self, 'refresh_projects'):
                self.refresh_projects()
    def _on_clear_all(self):
        for key, _ in self.fields_config:
            self.string_vars[key].set("")
            self.filter_data[key] = []

    def _on_cancel(self):
        self.result = None
        self._wait_var.set(1)
        self.destroy()

    def _on_execute(self):
        # Read directly typed entries (if they are not multi-value placeholders)
        for key, _ in self.fields_config:
            v = self.string_vars[key].get().strip()
            if v and not v.startswith("<"):
                self.filter_data[key] = [v]
            elif not v:
                self.filter_data[key] = []

        self.result = self.filter_data
        self.result_filters = self.filter_data
        self._wait_var.set(1)
        self.destroy()
