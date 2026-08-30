from tkinter import Toplevel, Frame, StringVar, Label, Button, Canvas, Listbox, Scrollbar, Checkbutton, Radiobutton, IntVar, Entry, Text, W, EW, E, MULTIPLE, simpledialog, LabelFrame, CENTER, messagebox
from tkinter.ttk import Combobox, Treeview, Scrollbar as TtkScrollbar
import json
import os
import openpyxl
from utils import show_info, show_error, macro_file
from typing import List, Tuple, Dict


def style_premium_button(btn, bg_color="#1A365D", fg_color="#FFFFFF", hover_bg="#0077B6", font=("Segoe UI", 10, "bold")):
    is_ttk = False
    try:
        is_ttk = "ttk" in btn.__module__
    except:
        pass

    if not is_ttk:
        curr_w = 0
        try:
            val = btn.cget("width")
            if val and int(val) > 0:
                curr_w = int(val)
        except:
            pass
        
        for opt, val in [
            ("bg", bg_color),
            ("background", bg_color),
            ("fg", fg_color),
            ("foreground", fg_color),
            ("activebackground", hover_bg),
            ("activeforeground", fg_color),
            ("font", font),
            ("width", curr_w),
            ("padx", 15),
            ("pady", 3),
            ("bd", 0),
            ("relief", "flat"),
            ("highlightthickness", 0),
            ("cursor", "hand2")
        ]:
            try:
                btn.config(**{opt: val})
            except:
                pass

        # Deferred execution to bypass OS mapping theme override on Windows
        def _deferred_paint():
            try:
                btn.config(bg=bg_color, background=bg_color, fg=fg_color, foreground=fg_color)
            except:
                pass
        try:
            btn.after(50, _deferred_paint)
        except:
            pass

        def on_enter(e):
            try:
                if str(btn.cget("state")) != "disabled":
                    btn.config(bg=hover_bg, background=hover_bg, fg=fg_color, foreground=fg_color)
            except:
                pass
        def on_leave(e):
            try:
                if str(btn.cget("state")) != "disabled":
                    btn.config(bg=bg_color, background=bg_color, fg=fg_color, foreground=fg_color)
            except:
                pass
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.bind("<FocusIn>", on_enter)
        btn.bind("<FocusOut>", on_leave)
        btn.bind("<Return>", lambda e: btn.invoke())
    else:
        try:
            # Tell ttk button to auto-size as well
            btn.config(width=0)
        except:
            pass

def apply_panel_theme(widget, bg="#EBF8FF", fg="#1A365D"):
    try:
        import tkinter.ttk as ttk
        style = ttk.Style()
        
        # Configure global ttk style configurations for consistency
        try:
            style.configure("TFrame", background=bg)
            style.configure("TLabelframe", background=bg)
            style.configure("TLabelframe.Label", background=bg, foreground=fg, font=("Segoe UI", 11, "bold"))
            style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 11))
            style.configure("TCheckbutton", background=bg, foreground=fg, font=("Segoe UI", 11))
            style.configure("TRadiobutton", background=bg, foreground=fg, font=("Segoe UI", 11))
            style.configure("TCombobox", font=("Segoe UI", 11))
            style.configure("TEntry", font=("Segoe UI", 11))
            
            style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
            style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
            
            style.configure("TButton", background=fg, foreground="#FFFFFF", font=("Segoe UI", 10, "bold"))
            style.map("TButton",
                background=[('active', '#0077B6'), ('pressed', '#0077B6')],
                foreground=[('active', '#FFFFFF'), ('pressed', '#FFFFFF')]
            )
        except Exception as e:
            pass

        try:
            widget_class = widget.winfo_class().lower()
        except:
            widget_class = ""

        if widget_class in ("frame", "labelframe", "tlabelframe", "tframe", "checkbutton", "radiobutton"):
            try:
                curr_bg = str(widget.cget("bg")).lower()
                if curr_bg != "#1a365d":
                    widget.configure(bg=bg)
            except:
                pass
            if widget_class in ("checkbutton", "radiobutton"):
                try:
                    widget.configure(fg=fg, font=("Segoe UI", 11))
                except:
                    pass
            if widget_class in ("labelframe", "tlabelframe"):
                try:
                    widget.configure(fg=fg, font=("Segoe UI", 11, "bold"))
                except:
                    pass
        elif widget_class in ("label", "tlabel"):
            try:
                # Intelligently preserve headers & titles
                curr_font = widget.cget("font")
                is_title = False
                if curr_font:
                    font_str = str(curr_font).lower()
                    if "bold" in font_str or any(x in font_str for x in ("12", "13", "14", "15", "16", "17", "18", "20")):
                        is_title = True
                if not is_title:
                    widget.configure(font=("Segoe UI", 11))
            except:
                try:
                    widget.configure(font=("Segoe UI", 11))
                except:
                    pass
            try:
                curr_bg = str(widget.cget("bg")).lower()
                if curr_bg != "#1a365d":
                    widget.configure(bg=bg, fg=fg)
            except:
                pass
        elif widget_class in ("entry", "text", "listbox"):
            try:
                widget.configure(font=("Segoe UI", 11))
            except:
                pass
        elif widget_class in ("button", "tbutton"):
            try:
                curr_bg = str(widget.cget("bg")).lower()
                if any(r in curr_bg for r in ("dc3545", "c82333", "28a745", "248a3e", "2ead4e", "red", "green")):
                    hover_color = "#c82333" if any(r in curr_bg for r in ("dc3545", "c82333", "red")) else "#248a3e"
                    style_premium_button(widget, bg_color=widget.cget("bg"), hover_bg=hover_color)
                else:
                    style_premium_button(widget)
            except:
                try:
                    style_premium_button(widget)
                except:
                    pass
        elif widget_class in ("canvas", "tcanvas"):
            try:
                widget.configure(bg=bg)
            except:
                pass
    except Exception as e:
        print(f"Error styling widget: {e}")
        
    try:
        for child in widget.winfo_children():
            apply_panel_theme(child, bg, fg)
    except:
        pass

class BasePanel(Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.result = None
        import tkinter as tk
        self._wait_var = tk.IntVar()
        self.configure(bg="#EBF8FF")

    def wait_for_close(self):
        try:
            self.master.configure(bg="#EBF8FF")
        except:
            pass
        self.wait_variable(self._wait_var)
        return getattr(self, 'result', None)

    def _on_cancel(self):
        self.result = None
        self._wait_var.set(1)

class BaseDialog(Toplevel):
    """The base class for all dialog windows."""
    def __init__(self, master, title, make_transient=True):
        parent_toplevel = master.winfo_toplevel()
        super().__init__(parent_toplevel)
        self.master = parent_toplevel
        self.title(title)
        if make_transient:
            self.transient(parent_toplevel)
            self.grab_set()
            self.result = None
            self._center_on_master()
        else:
            self.grab_set()
            self.result = None
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _center_on_master(self):
        self.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def wait_for_close(self):
        try:
            self.configure(bg="#EBF8FF")
        except:
            pass
        self.master.wait_window(self)

    def _on_cancel(self):
        self.result = None
        self.destroy()

class ValidationDialog(Toplevel):
    # current_value is now a list of unvalidated (mpn, mfr) tuples or a single mpn string
    def __init__(self, master, unvalidated_mpn_mfr_pairs: List[Tuple[str, str]], desc_value: str, part_value: str, source_data: List[Tuple]):
        super().__init__(master)
        self.title("Validate MPN(s)")
        self.transient(master)
        self.grab_set()

        self.desc_value = desc_value
        self.part_value = part_value
        self.source_data = source_data
        
        # New attributes to manage the multi-item process
        self.unvalidated_pairs = unvalidated_mpn_mfr_pairs
        self.current_pair_index = 0
        
        # Output containers
        # Stores { 'original_unvalidated_mpn': ('validated_mpn', 'validated_mfr') }
        self.validated_mappings: Dict[str, Tuple[str, str]] = {} 
        # Stores newly added entries: list of (mpn, mfr, flag_state)
        self.new_entries: List[Tuple[str, str, int]] = [] 
        self.equivalent_entries: List[Tuple[str, str]] = [] 
        
        # State variables for the current item
        self.new_mpn = StringVar()
        self.new_mfr = StringVar()
        self.is_flagged = IntVar()
        self.is_cancelled_entirely = False
        
        self.main_frame = Frame(self, padx=10, pady=10)
        self.main_frame.pack(fill="both", expand=True)
        
        self._create_widgets()
        self._load_next_unvalidated_pair() # Start the validation process
        
        self.wait_window()

    def _create_widgets(self):
        # Frame for dynamic message and current unvalidated MPN
        self.header_frame = Frame(self.main_frame)
        self.header_frame.pack(fill='x', pady=5)
        
        self.message_label = Label(self.header_frame, text="", font=("Arial", 10, "bold"))
        self.message_label.pack(pady=5)
        Label(self.header_frame, text=f"Customer Part: '{self.part_value}'.", font=("Arial", 10, "bold")).pack(pady=5)
        Label(self.header_frame, text=f"Description: '{self.desc_value}'.", font=("Arial", 10, "bold")).pack(pady=5)
        
        # --- Manual Entry and Add Button ---
        manual_entry_frame = Frame(self.main_frame)
        manual_entry_frame.pack(pady=(10, 0))

        Label(manual_entry_frame, text="Manual Entry / New MPN:").grid(row=0, columnspan=2, pady=5)
        Label(manual_entry_frame, text="MPN:").grid(row=1, column=0, sticky=E, padx=5)
        self.mpn_entry = Entry(manual_entry_frame, textvariable=self.new_mpn)
        self.mpn_entry.grid(row=1, column=1, sticky=W)
        Label(manual_entry_frame, text="MFR:").grid(row=2, column=0, sticky=E, padx=5)
        self.mfr_entry = Entry(manual_entry_frame, textvariable=self.new_mfr)
        self.mfr_entry.grid(row=2, column=1, sticky=W)
        
        Checkbutton(manual_entry_frame, text="Fabricate Part", variable=self.is_flagged).grid(row=3, column=0, columnspan=2, pady=(10, 0))
        # Changed button command to map the current unvalidated MPN to the new manual entry
        Button(manual_entry_frame, text="Add New to Source & Use", command=self.on_add_new_entry_and_map).grid(row=4, column=0, columnspan=2, pady=5)

        Label(self.main_frame, text="or Select Existing from Source (Use Select/Double-Click)").pack(pady=(10,0))

        # --- Search and Treeview (for existing values) ---
        search_frame = Frame(self.main_frame)
        search_frame.pack(fill="x", pady=5)
        # Search controls (as in original code)
        Label(search_frame, text="Search in:").pack(side="left")
        self.search_field_var = StringVar(value="All")
        self.search_field_combo = Combobox(search_frame, textvariable=self.search_field_var, values=["All", "MPN", "MFR", "Description"], state="readonly")
        self.search_field_combo.pack(side="left", padx=5)
        self.search_field_combo.bind("<<ComboboxSelected>>", self.filter_treeview)
        
        Label(search_frame, text="Search for:").pack(side="left")
        self.search_var = StringVar()
        self.search_entry = Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5)
        self.search_var.trace_add("write", self.filter_treeview)
        
        # Treeview for displaying existing values.
        tree_frame = Frame(self.main_frame)
        tree_frame.pack(pady=10, fill="both", expand=True)
        
        columns = ("MPN", "MFR", "Description", "Latest Price")
        self.tree = Treeview(tree_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("MPN", text="MPN")
        self.tree.heading("MFR", text="MFR")
        self.tree.heading("Description", text="Description")
        self.tree.heading("Latest Price", text="Latest Price")

        v_scrollbar = Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scrollbar.set)
        v_scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.populate_treeview(self.source_data)
        self.tree.bind("<Double-1>", self.on_double_click_select) # Double-click is still a single mapping
        
        # --- Control Buttons (Modified) ---
        button_frame = Frame(self.main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        # NEW BUTTON: Adds all selected rows as equivalence parts and advances to the next unvalidated MPN
        Button(button_frame, text="Add Selected as Equivalents & Next", command=self.on_add_equivalents_and_next).pack(side='left', padx=5, expand=True)
        
        # RENAME: Change 'Map to Selected & Next' to avoid confusion with multi-select button
        Button(button_frame, text="Map Current to Selected & Next", command=self.on_select_and_map).pack(side='left', padx=5, expand=True)
        
        # Old buttons
        Button(button_frame, text="Skip for Now & Next", command=self.on_skip_and_next).pack(side='left', padx=5, expand=True)
        Button(button_frame, text="Exit Validation Entirely", command=self.on_cancel).pack(side='right', padx=5, expand=True)

    def on_add_equivalents_and_next(self):
        """
        Adds all currently selected MPNs in the table to the output list
        as equivalent parts and then moves to the next unvalidated MPN.
        """
        selected_items = self.tree.selection()
        if not selected_items:
            show_error("Selection Error", "Please select one or more MPNs from the table to add as equivalents.")
            return

        for item_id in selected_items:
            values = self.tree.item(item_id, "values")
            # Append (MPN, MFR) tuple to the equivalents list
            self.equivalent_entries.append((values[0], values[1])) 
            
        show_info("Equivalents Added", f"Added {len(selected_items)} MPN(s) as equivalents for the final list.")
        
        # Since this action is independent of mapping the current unvalidated MPN,
        # we treat the current unvalidated MPN as 'skipped' and move to the next.
        self.current_pair_index += 1
        self._load_next_unvalidated_pair()

    def _load_next_unvalidated_pair(self):
        """Loads the next unvalidated MPN/MFR pair for the user to process."""
        if self.current_pair_index < len(self.unvalidated_pairs):
            mpn, mfr = self.unvalidated_pairs[self.current_pair_index]
            
            # Update header message
            self.message_label.config(text=f"Validating {self.current_pair_index + 1} of {len(self.unvalidated_pairs)}: MPN '{mpn}' (MFR: '{mfr}')")
            
            # Pre-populate the manual entry with the unvalidated value
            self.new_mpn.set(mpn)
            self.new_mfr.set(mfr)
            self.is_flagged.set(0)
            self.tree.selection_remove(self.tree.selection()) # Clear selection
        else:
            # All items validated/mapped/skipped
            self.destroy()

    def populate_treeview(self, data):
        self.tree.delete(*self.tree.get_children())
        for mpn, mfr, desc, price in data:
            self.tree.insert("", "end", values=(mpn, mfr, desc, price))

    # Existing filter_treeview logic remains correct
    def filter_treeview(self, *args):
        search_query = self.search_var.get().lower()
        selected_field = self.search_field_var.get()
        filtered_data = []

        if not search_query:
            self.populate_treeview(self.source_data)
            return

        for item in self.source_data:
            if len(item) == 4:
                mpn, mfr, desc, price = item
            else:
                continue

            mpn_lower = str(mpn).lower()
            mfr_lower = str(mfr).lower()
            desc_lower = str(desc).lower()

            is_match = False
            if selected_field == "MPN" and search_query in mpn_lower:
                is_match = True
            elif selected_field == "MFR" and search_query in mfr_lower:
                is_match = True
            elif selected_field == "Description" and search_query in desc_lower:
                is_match = True
            elif selected_field == "All" and (search_query in mpn_lower or search_query in mfr_lower or search_query in desc_lower):
                is_match = True
            
            if is_match:
                filtered_data.append(item)

        self.populate_treeview(filtered_data)

    def _map_and_advance(self, validated_mpn: str, validated_mfr: str):
        """Internal function to store the mapping and move to the next item."""
        if self.current_pair_index < len(self.unvalidated_pairs):
            original_mpn, _ = self.unvalidated_pairs[self.current_pair_index]
            self.validated_mappings[original_mpn] = (validated_mpn, validated_mfr)
            self.current_pair_index += 1
            self._load_next_unvalidated_pair()
    
    def on_select_and_map(self):
        """Maps the current unvalidated MPN to a selected existing MPN."""
        selected_item = self.tree.focus()
        if not selected_item:
            show_error("Selection Error", "Please select an MPN from the list or use 'Add New' to proceed.")
            return

        values = self.tree.item(selected_item, "values")
        validated_mpn = values[0]
        validated_mfr = values[1]
        
        self._map_and_advance(validated_mpn, validated_mfr)
        
    def on_double_click_select(self, event):
        """Maps the current unvalidated MPN to a double-clicked existing MPN."""
        self.on_select_and_map()
    
    def on_add_new_entry_and_map(self):
        """Adds a new MPN to the source_data (in-memory) and maps the current unvalidated MPN to it."""
        new_mpn_val = self.new_mpn.get().strip()
        new_mfr_val = self.new_mfr.get().strip()
        flag_state = self.is_flagged.get()

        if not new_mpn_val:
            show_error("Validation Error", "Please enter a value for the new MPN.")
            return
        
        # 1. Record the new entry for post-dialog source update
        self.new_entries.append((new_mpn_val, new_mfr_val, flag_state))
        
        # 2. Add to the source_data set (in-memory only for this dialog session)
        # Note: We need a dummy description and price for the 4-tuple format
        self.source_data.append((new_mpn_val, new_mfr_val, self.desc_value, 'N/A')) 
        
        # 3. Refresh Treeview and search list to include the new entry
        self.filter_treeview() 
        
        # 4. Map the current unvalidated MPN to the new entry and advance
        self._map_and_advance(new_mpn_val, new_mfr_val)
        
    def on_skip_and_next(self):
        """Skips the current unvalidated MPN, effectively keeping its original value."""
        # By not adding it to self.validated_mappings, we implicitly keep the original MPN
        # in the final list, which is what the loop in process_file_and_validate will do.
        self.current_pair_index += 1
        self._load_next_unvalidated_pair()

    def on_cancel(self):
        # Clear all outputs to signal cancellation in the calling function
        self.validated_mappings = {}
        self.new_entries = []
        self.is_cancelled_entirely = True 
        self.destroy()

class eValidationDialog(Toplevel):
    def __init__(self, master, current_value, desc_value, part_value, source_data):
        super().__init__(master)
        self.title("Validate Value")
        self.transient(master)
        self.grab_set()

        self.current_value = current_value
        self.desc_value = desc_value
        self.part_value = part_value
        self.source_data = source_data
        self.selected_value = None
        self.selected_mfr = None
        self.new_value = None
        self.new_mfr_value = None
        
        # Add these lines to initialize the variable holders
        self.new_mpn = StringVar()
        self.new_mfr = StringVar()
        self.is_flagged = IntVar()
        
        self._create_widgets()
        
        self.wait_window()
    
    def _create_widgets(self):
        main_frame = Frame(self)
        main_frame.pack(fill="both", expand=True)

        # Case 1: The row has no MPN value.
        if not self.current_value:
            Label(main_frame, text=f"No MPN was found for this entry: '{self.desc_value}'.", font=("Arial", 10, "bold")).pack(pady=5)
            Label(main_frame, text=f"Customer Part: '{self.part_value}'.", font=("Arial", 10, "bold")).pack(pady=5)
            
            # Manual Entry section with input fields.
            manual_entry_frame = Frame(main_frame)
            manual_entry_frame.pack(pady=(20, 0))

            Label(manual_entry_frame, text="Manual Entry:").grid(row=0, columnspan=2, pady=5)
            Label(manual_entry_frame, text="MPN:").grid(row=1, column=0, sticky="e", padx=5)
            self.mpn_entry = Entry(manual_entry_frame, textvariable=self.new_mpn)
            self.mpn_entry.grid(row=1, column=1, sticky="w")
            Label(manual_entry_frame, text="MFR:").grid(row=2, column=0, sticky="e", padx=5)
            self.mfr_entry = Entry(manual_entry_frame, textvariable=self.new_mfr)
            self.mfr_entry.grid(row=2, column=1, sticky="w")
            
            # The "Add New Entry" button is tied to this specific flow.
            Checkbutton(manual_entry_frame, text="Fabricate Part", variable=self.is_flagged).grid(row=3, column=0, columnspan=2, pady=(10, 0))
            Button(manual_entry_frame, text="Add New Entry", command=self.on_new_entry_manual).grid(row=4, column=0, columnspan=2, pady=5)

            Label(main_frame, text="or").pack(pady=(10,0))

            # Search controls for existing MPNs.
            search_frame = Frame(main_frame)
            search_frame.pack(fill="x", pady=5)
            
            Label(search_frame, text="Search in:").pack(side="left")
            self.search_field_var = StringVar(value="All")
            self.search_field_combo = Combobox(search_frame, textvariable=self.search_field_var,
                                               values=["All", "MPN", "MFR", "Description"], state="readonly")
            self.search_field_combo.pack(side="left", padx=5)
            self.search_field_combo.bind("<<ComboboxSelected>>", self.filter_treeview)
            
            Label(search_frame, text="Search for:").pack(side="left")
            self.search_var = StringVar()
            self.search_entry = Entry(search_frame, textvariable=self.search_var)
            self.search_entry.pack(side="left", fill="x", expand=True, padx=5)
            self.search_var.trace_add("write", self.filter_treeview)
            
            # Treeview for displaying existing values.
            tree_frame = Frame(main_frame)
            tree_frame.pack(pady=10, fill="both", expand=True)
            
            columns = ("MPN", "MFR", "Description", "Latest Price")
            self.tree = Treeview(tree_frame, columns=columns, show="headings")
            self.tree.heading("MPN", text="MPN")
            self.tree.heading("MFR", text="MFR")
            self.tree.heading("Description", text="Description")
            self.tree.heading("Latest Price", text="Latest Price")
            self.tree.column("MPN", width=150)
            self.tree.column("MFR", width=150)
            self.tree.column("Description", width=400)
            self.tree.column("Latest Price", width=100)

            v_scrollbar = Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=v_scrollbar.set)
            v_scrollbar.pack(side="right", fill="y")
            self.tree.pack(side="left", fill="both", expand=True)

            self.populate_treeview(self.source_data)
            self.tree.bind("<Double-1>", self.on_double_click_select)
            
            Button(main_frame, text="Use Selected MPN", command=self.on_select).pack(pady=(10, 0))

        # Case 2: The row has an unvalidated MPN.
        else:
            Label(main_frame, text=f"The value '{self.current_value}' was not found.", font=("Arial", 10, "bold")).pack(pady=5)
            
            # Search controls for existing MPNs.
            search_frame = Frame(main_frame)
            search_frame.pack(fill="x", pady=5)
            
            Label(search_frame, text="Search in:").pack(side="left")
            self.search_field_var = StringVar(value="All")
            self.search_field_combo = Combobox(search_frame, textvariable=self.search_field_var,
                                               values=["All", "MPN", "MFR", "Description"], state="readonly")
            self.search_field_combo.pack(side="left", padx=5)
            self.search_field_combo.bind("<<ComboboxSelected>>", self.filter_treeview)
            
            Label(search_frame, text="Search for:").pack(side="left")
            self.search_var = StringVar()
            self.search_entry = Entry(search_frame, textvariable=self.search_var)
            self.search_entry.pack(side="left", fill="x", expand=True, padx=5)
            self.search_var.trace_add("write", self.filter_treeview)
            
            # Treeview for displaying existing values.
            tree_frame = Frame(main_frame)
            tree_frame.pack(pady=10, fill="both", expand=True)
            
            columns = ("MPN", "MFR", "Description", "Latest Price")
            self.tree = Treeview(tree_frame, columns=columns, show="headings")
            self.tree.heading("MPN", text="MPN")
            self.tree.heading("MFR", text="MFR")
            self.tree.heading("Description", text="Description")
            self.tree.heading("Latest Price", text="Latest Price")
            self.tree.column("MPN", width=150)
            self.tree.column("MFR", width=150)
            self.tree.column("Description", width=400)
            self.tree.column("Latest Price", width=100)

            v_scrollbar = Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=v_scrollbar.set)
            v_scrollbar.pack(side="right", fill="y")
            self.tree.pack(side="left", fill="both", expand=True)

            self.populate_treeview(self.source_data)
            self.tree.bind("<Double-1>", self.on_double_click_select)
            
            Button(main_frame, text="Use Selected MPN", command=self.on_select).pack(pady=(10, 0))

            Label(main_frame, text="or").pack(pady=(10,0))
            
            # This "Add New Entry" button uses the original, unvalidated value.
            new_entry_frame = Frame(main_frame)
            new_entry_frame.pack()
            Checkbutton(new_entry_frame, text="Fabricate Part", variable=self.is_flagged).pack(side="left", padx=(0, 10))
            Button(new_entry_frame, text=f"Add '{self.current_value}' as New Entry", command=self.on_new_entry_unvalidated).pack(side="left")
            
        # The "Cancel" button is common to both paths.
        Button(main_frame, text="Cancel", command=self.on_cancel).pack(pady=20)
    
    def populate_treeview(self, data):
        self.tree.delete(*self.tree.get_children())
        for mpn, mfr, desc, price in data:
            self.tree.insert("", "end", values=(mpn, mfr, desc, price))

    def filter_treeview(self, *args):
        search_query = self.search_var.get().lower()
        selected_field = self.search_field_var.get()
        filtered_data = []

        if not search_query:
            self.populate_treeview(self.source_data)
            return

        for item in self.source_data:
            if len(item) == 4:
                mpn, mfr, desc, price = item
            else:
                continue

            mpn_lower = str(mpn).lower()
            mfr_lower = str(mfr).lower()
            desc_lower = str(desc).lower()
            price = str(price)

            is_match = False
            if selected_field == "MPN" and search_query in mpn_lower:
                is_match = True
            elif selected_field == "MFR" and search_query in mfr_lower:
                is_match = True
            elif selected_field == "Description" and search_query in desc_lower:
                is_match = True
            elif selected_field == "All" and (search_query in mpn_lower or search_query in mfr_lower or search_query in desc_lower):
                is_match = True
            
            if is_match:
                filtered_data.append(item)

        self.populate_treeview(filtered_data)
        
    def on_select(self):
        selected_item = self.tree.focus()
        if selected_item:
            self.selected_value = self.tree.item(selected_item, "values")[0]
            self.selected_mfr = self.tree.item(selected_item, "values")[1]
            self.destroy()

    def on_double_click_select(self, event):
        self.on_select()
    
    # New method for when a new entry is created manually (no original MPN).
    def on_new_entry_manual(self):
        self.new_value = self.new_mpn.get()
        self.new_mfr_value = self.new_mfr.get()
        self.flag_state = self.is_flagged.get()
        self.destroy()

    # Existing method for when an unvalidated entry is logged as new.
    def on_new_entry_unvalidated(self):
        self.new_value = self.current_value
        self.flag_state = self.is_flagged.get()
        self.destroy()

    def on_cancel(self):
        self.destroy()



class SpecialColumnsSelectorDialog(BaseDialog):
    def __init__(self, master, actual_headers, special_columns, default_cust_name=""):
        super().__init__(master, "Select Special Columns Method")
        self.actual_headers = actual_headers
        self.special_columns = special_columns
        self.results = {} 
        self.cust_name = ""
        self.RFQ_ID = ""
        self.email_subject = ""

        self.column_method_vars = {col: StringVar(self, value="map_column") for col in special_columns}
        self.column_selection_vars = {col: StringVar(self) for col in special_columns}
        self.fixed_value_entry_vars = {col: StringVar(self) for col in special_columns}
        self.cust_name_var = StringVar(self, value=default_cust_name)
        self.rfq_id_var = StringVar(self)
        self.email_subject_var = StringVar(self)
        self.input_widgets = {}

        self._create_widgets()
        for col in special_columns:
            self._on_method_select(col)

        self.wait_for_close()

    def _create_widgets(self):
        main_frame = Frame(self, padx=10, pady=10)
        main_frame.pack(fill="both", expand=True)

        row_num = 0
        Label(main_frame, text=f"Enter Customer Name:", font=("Arial", 10, "bold")).grid(row=row_num, column=0, sticky=W, pady=(5, 0))
        row_num += 1
        
        cust_name_entry = Entry(main_frame, textvariable=self.cust_name_var, width=40)
        cust_name_entry.grid(row=row_num, column=0, columnspan=3, sticky="ew", padx=(0, 0))
        row_num += 1

        Label(main_frame, text=f"RFQ Number:", font=("Arial", 10, "bold")).grid(row=row_num, column=0, sticky=W, pady=(5, 0))
        row_num += 1

        rfq_id_entry = Entry(main_frame, textvariable=self.rfq_id_var, width=40)
        rfq_id_entry.grid(row=row_num, column=0, columnspan=3, sticky="ew", padx=(0, 0))
        row_num += 1

        Label(main_frame, text=f"Project Title:", font=("Arial", 10, "bold")).grid(row=row_num, column=0, sticky=W, pady=(5, 0))
        row_num += 1

        email_subject_entry = Entry(main_frame, textvariable=self.email_subject_var, width=40)
        email_subject_entry.grid(row=row_num, column=0, columnspan=3, sticky="ew", padx=(0, 0))
        row_num += 1

        Label(main_frame, text=f"Enter Customer Name and Select for Model Details:",
              font=("Arial", 10, "bold")).grid(row=0, column=0, columnspan=3, pady=10, sticky=W)

        row_num += 1
        combobox_options = [""] + sorted(list(set(self.actual_headers)))

        for col_name in self.special_columns:
            Label(main_frame, text=f"For '{col_name}':", font=("Arial", 9, "bold")).grid(row=row_num, column=0, columnspan=3, sticky=W, pady=(10, 0))
            row_num += 1

            rb_map = Radiobutton(main_frame, text="Map from Excel column",
                                 variable=self.column_method_vars[col_name], value="map_column",
                                 command=lambda c=col_name: self._on_method_select(c))
            rb_map.grid(row=row_num, column=0, columnspan=1, sticky=W)
            
            col_combobox = Combobox(main_frame, textvariable=self.column_selection_vars[col_name],
                                     values=combobox_options, state="readonly")
            col_combobox.grid(row=row_num, column=1, columnspan=2, padx=(5,0), sticky="ew")
            self.input_widgets[f'{col_name}_combobox'] = col_combobox
            row_num += 1

            rb_fixed = Radiobutton(main_frame, text="Enter a fixed value",
                                    variable=self.column_method_vars[col_name], value="fixed_value",
                                    command=lambda c=col_name: self._on_method_select(c))
            rb_fixed.grid(row=row_num, column=0, columnspan=1, sticky=W, pady=(5,0))

            fixed_entry = Entry(main_frame, textvariable=self.fixed_value_entry_vars[col_name])
            fixed_entry.grid(row=row_num, column=1, columnspan=2, padx=(5,0), sticky="ew")
            self.input_widgets[f'{col_name}_entry'] = fixed_entry
            row_num += 1
            
            Label(main_frame, text="").grid(row=row_num, column=0, columnspan=3, pady=5)
            row_num += 1


        Button(main_frame, text="Confirm", command=self._on_confirm).grid(row=row_num, column=0, pady=10, sticky=E)
        Button(main_frame, text="Cancel", command=self._on_cancel).grid(row=row_num, column=1, pady=10, sticky=W)

        main_frame.grid_columnconfigure(1, weight=1)

    def _on_method_select(self, col_name):
        current_method = self.column_method_vars[col_name].get()
        combobox = self.input_widgets[f'{col_name}_combobox']
        entry = self.input_widgets[f'{col_name}_entry']

        if current_method == "map_column":
            combobox.config(state="readonly")
            entry.config(state="disabled")
            self.fixed_value_entry_vars[col_name].set("")
        else:
            combobox.config(state="disabled")
            self.column_selection_vars[col_name].set("")
            entry.config(state="normal")

    def _on_confirm(self):
        self.results = {}
        self.cust_name = self.cust_name_var.get().strip()
        self.RFQ_ID = self.rfq_id_var.get().strip()
        self.email_subject = self.email_subject_var.get().strip()
        
        if not self.cust_name:
            show_error("Missing Information", "Please enter a Customer Name.", parent=self)
            return

        if self.RFQ_ID:
            from utils import check_rfq_exists, show_warning
            existing_cust = check_rfq_exists(self.RFQ_ID)
            if existing_cust:
                show_warning("RFQ Number Already Exists", f"The RFQ Number '{self.RFQ_ID}' has already been used in the system under Customer '{existing_cust}'.\n\nPlease specify a new, unique RFQ number to proceed.", parent=self)
                return
        
        for col_name in self.special_columns:
            method = self.column_method_vars[col_name].get()
            
            if method == "map_column":
                selected_column = self.column_selection_vars[col_name].get().strip()
                if not selected_column:
                    show_error("Missing Selection", f"Please select an Excel column for '{col_name}'.", parent=self)
                    return
                self.results[col_name] = {'method': 'map', 'source_column': selected_column}
            else:
                fixed_val = self.fixed_value_entry_vars[col_name].get() 
                self.results[col_name] = {'method': 'fixed', 'value': fixed_val}
        
        self.result = (self.results, self.cust_name, self.RFQ_ID, self.email_subject) # Store the result in the base class's result attribute
        self.destroy()

    def get_selection(self):
        return self.result

class MultiColumnSelectionDialog(BaseDialog):
    def __init__(self, master, actual_headers, target_column_name, initial_selections=None):
        super().__init__(master, f"Select Source(s) for '{target_column_name}'")
        self.actual_headers = actual_headers
        self.target_column_name = target_column_name
        self.selected_columns = initial_selections if initial_selections is not None else []
        self._skip_autofit = True  # Prevent auto-maximize
        self.geometry("420x480")
        self.resizable(True, True)
        self.minsize(380, 360)
        self._create_widgets()
        self.wait_for_close()

    def _create_widgets(self):
        main_frame = Frame(self, padx=10, pady=10)
        main_frame.pack(fill="both", expand=True)

        Label(main_frame, text=f"Select one or more Excel columns to map to '{self.target_column_name}':",
              font=("Arial", 10, "bold")).pack(pady=5, anchor=W)

        listbox_frame = Frame(main_frame)
        listbox_frame.pack(fill="both", expand=True, pady=5)

        scrollbar = Scrollbar(listbox_frame)
        scrollbar.pack(side="right", fill="y")

        self.listbox = Listbox(listbox_frame, selectmode=MULTIPLE, yscrollcommand=scrollbar.set, height=10)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        for i, header in enumerate(sorted(self.actual_headers)):
            self.listbox.insert("end", header)
            if header in self.selected_columns:
                self.listbox.selection_set(i)

        Button(main_frame, text="Confirm Selection", command=self._on_confirm).pack(pady=10)
        Button(main_frame, text="Cancel", command=self._on_cancel).pack(pady=5)

    def _on_confirm(self):
        selection = [self.listbox.get(i) for i in self.listbox.curselection()]
        if not selection:
            show_error("No Selection", "Please select at least one column or click Cancel.", parent=self)
            return
        self.result = selection
        self.destroy()

    def get_selection(self):
        return self.result

class ColumnMapperDialog(BaseDialog):
    def __init__(self, master, actual_headers, standard_columns, mandatory_columns, special_columns_to_skip, multi_source_columns, initial_mapping=None):
        super().__init__(master, "Map Excel Columns")
        
        self.actual_headers = actual_headers
        self.standard_columns = standard_columns
        self.mandatory_columns = mandatory_columns
        self.special_columns_to_skip = special_columns_to_skip
        self.multi_source_columns = multi_source_columns
        self.mapping_vars = {}
        self.multi_mapping_labels = {}
        self.result_mapping = {}
        self.initial_mapping = initial_mapping

        self._create_widgets()
        self.wait_for_close()

    def _create_widgets(self):
        row_num = 0
        Label(self, text="Map your desired standard columns to the actual Excel headers:",
              font=("Arial", 10, "bold")).grid(row=row_num, column=0, columnspan=3, pady=10)
        row_num += 1

        combobox_options = [""] + sorted(list(set(self.actual_headers)))

        for col_name in self.standard_columns:
            if col_name in self.special_columns_to_skip:
                continue

            Label(self, text=f"'{col_name}' will be:").grid(row=row_num, column=0, padx=5, pady=2, sticky="w")

            if col_name in self.multi_source_columns:
                current_selection_label = Label(self, text="No sources selected", wraplength=200)
                current_selection_label.grid(row=row_num, column=1, padx=5, pady=2, sticky="w")
                self.multi_mapping_labels[col_name] = current_selection_label
                self.result_mapping[col_name] = []

                select_btn = Button(self, text="Select Sources", 
                                    command=lambda c=col_name: self._open_multi_selection_dialog(c))
                select_btn.grid(row=row_num, column=2, padx=5, pady=2, sticky="w")
            else:
                var = StringVar(self)
                initial_selection = ""
                for actual_h in self.actual_headers:
                    if actual_h.lower() == col_name.lower():
                        initial_selection = actual_h
                        break
                var.set(initial_selection)

                combobox = Combobox(self, textvariable=var, values=combobox_options, state="readonly", width=40)
                combobox.grid(row=row_num, column=1, columnspan=2, padx=5, pady=2, sticky="w")
                self.mapping_vars[col_name] = var

            row_num += 1

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        Button(self, text="Confirm Mapping", command=self._on_confirm).grid(row=row_num, column=0, columnspan=3, pady=10, padx=5, sticky="ew")
        Button(self, text="Cancel", command=self._on_cancel).grid(row=row_num+1, column=0, columnspan=3, pady=5, padx=5, sticky="ew")

    def _open_multi_selection_dialog(self, col_name):
        initial_selections = self.result_mapping.get(col_name, [])
        multi_dialog = MultiColumnSelectionDialog(self, self.actual_headers, col_name, initial_selections)
        selected_sources = multi_dialog.get_selection()

        if selected_sources is not None:
            self.result_mapping[col_name] = selected_sources
            display_text = ", ".join(selected_sources) if selected_sources else "No sources selected"
            self.multi_mapping_labels[col_name].config(text=display_text)

    def _on_confirm(self):
        final_mapping = {}
        all_selected_actual_headers = set()

        for standard_col, var in self.mapping_vars.items():
            actual_header = var.get().strip()
            if actual_header:
                if actual_header in all_selected_actual_headers:
                    show_error("Duplicate Selection",
                               f"The Excel header '{actual_header}' has been mapped to more than one standard column.", parent=self)
                    return
                final_mapping[actual_header] = standard_col
                all_selected_actual_headers.add(actual_header)
            elif standard_col in self.mandatory_columns:
                show_error("Missing Mapping",
                           f"Mandatory column '{standard_col}' has not been mapped to an Excel header.", parent=self)
                return

        for col_name in self.multi_source_columns:
            sources = self.result_mapping.get(col_name, [])
            if not sources and col_name in self.mandatory_columns:
                show_error("Missing Mapping",
                           f"Mandatory multi-source column '{col_name}' has no sources selected.", parent=self)
                return

            if sources:
                for source in sources:
                    if source in all_selected_actual_headers:
                        show_error("Duplicate Selection",
                                   f"The Excel header '{source}' has been selected for '{col_name}' and also used for another mapping.", parent=self)
                        return
                    all_selected_actual_headers.add(source)
                final_mapping[col_name] = sources

        self.result = final_mapping
        self.destroy()
    
    def get_mapping(self):
        return self.result

class CategoryInputDialog(BaseDialog):
    def __init__(self, master, initial_categories=None):
        super().__init__(master, "Set MOQs")
        self._skip_autofit = True  # Prevent auto-maximize
        self.geometry("520x540")
        self.resizable(True, True)
        self.minsize(450, 480)
        self.categories = initial_categories if initial_categories is not None else []
        self._create_widgets()
        self.wait_for_close()

    def _create_widgets(self):
        main_frame = Frame(self, padx=20, pady=15)
        main_frame.pack(fill="both", expand=True)

        # SAP Title Banner matching "Block/Unblock Data" style
        title_frame = Frame(main_frame, bg="#eef5fb", bd=1, relief="solid")
        title_frame.pack(fill="x", pady=(0, 15))
        Label(title_frame, text="Set MOQs", font=("Arial", 12, "bold"), fg="#1a365d", bg="#eef5fb").pack(pady=8)

        Label(main_frame, text="Enter Quantity to Quote and click 'Add':",
              font=("Arial", 10, "bold")).pack(pady=5, anchor=W)

        entry_frame = Frame(main_frame)
        entry_frame.pack(fill="x", pady=5)

        self.category_entry_var = StringVar()
        self.category_entry = Entry(entry_frame, textvariable=self.category_entry_var, font=("Arial", 10))
        self.category_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.category_entry.bind("<Return>", lambda event: self._add_category())

        add_button = Button(entry_frame, text="Add Quantity", width=14, font=("Arial", 9, "bold"), command=self._add_category)
        add_button.pack(side="right")

        listbox_frame = Frame(main_frame)
        listbox_frame.pack(fill="both", expand=True, pady=8)

        scrollbar = Scrollbar(listbox_frame)
        scrollbar.pack(side="right", fill="y")

        self.category_listbox = Listbox(listbox_frame, selectmode=MULTIPLE, yscrollcommand=scrollbar.set, font=("Arial", 10), height=8)
        self.category_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.category_listbox.yview)

        self._populate_listbox()

        # Action Buttons Row (just after the listbox frame)
        action_btn_frame = Frame(main_frame)
        action_btn_frame.pack(fill="x", pady=8)
        
        Button(action_btn_frame, text="Remove Selected", width=16, font=("Arial", 9, "bold"), command=self._remove_selected_categories).pack(side="left", padx=(0, 5))
        Button(action_btn_frame, text="Remove All", width=14, font=("Arial", 9, "bold"), command=self._remove_all_categories).pack(side="left", padx=5)

        # Bottom Buttons Row (Confirm and Cancel)
        bottom_btn_frame = Frame(main_frame)
        bottom_btn_frame.pack(fill="x", side="bottom", pady=(15, 5))
        
        Button(bottom_btn_frame, text="Cancel", width=14, font=("Arial", 10, "bold"), command=self._on_cancel).pack(side="left")
        Button(bottom_btn_frame, text="Confirm", width=14, bg="#1a365d", fg="white", font=("Arial", 10, "bold"), command=self._on_confirm).pack(side="right")

    def _remove_all_categories(self):
        self.categories = []
        self._populate_listbox()

    def _populate_listbox(self):
        self.category_listbox.delete(0, "end")
        for category in self.categories:
            self.category_listbox.insert("end", category)

    def _add_category(self):
        new_category = self.category_entry_var.get().strip()
        if new_category:
            try:
                qty = int(new_category)
                if qty <= 0:
                    show_error("Invalid Input", "Quantity must be an integer greater than 0.", parent=self)
                    return
                new_category_str = str(qty)
                if new_category_str not in self.categories:
                    self.categories.append(new_category_str)
                    self.categories.sort(key=lambda x: int(x))
                    self._populate_listbox()
                    self.category_entry_var.set("")
                else:
                    show_info("Duplicate Category", f"'{new_category_str}' is already in the list.", parent=self)
            except ValueError:
                show_error("Invalid Input", "Quantity must be a valid integer.", parent=self)
        self.category_entry.focus_set()

    def _remove_selected_categories(self):
        selected_indices = self.category_listbox.curselection()
        if not selected_indices:
            show_info("No Selection", "Please select categories to remove.", parent=self)
            return

        for index in reversed(selected_indices):
            category_to_remove = self.category_listbox.get(index)
            if category_to_remove in self.categories:
                self.categories.remove(category_to_remove)
        self._populate_listbox()

    def _on_confirm(self):
        self.result = self.categories
        self.destroy()

    def get_categories(self):
        return self.result

class AssemblyMOQDialog(BaseDialog):
    def __init__(self, master, unique_assemblies, initial_global_moqs=None, initial_assembly_moqs=None):
        super().__init__(master, "Assembly MOQ Manager")
        self.unique_assemblies = list(unique_assemblies)
        self.global_moqs = initial_global_moqs if initial_global_moqs else []
        self.assembly_moqs = initial_assembly_moqs if initial_assembly_moqs else {assy: list(self.global_moqs) for assy in self.unique_assemblies}
        
        # UI variables
        self.global_moq_lbl_var = StringVar(value="Current Global MOQs: " + (", ".join(map(str, self.global_moqs)) if self.global_moqs else "- None -"))
        
        self.geometry("1100x750")
        
        import tkinter as tk
        self._wait_var = tk.IntVar()
        self._create_widgets()
        
        self.status_bar = Label(self, text="", font=("Arial", 10, "bold"), anchor="center", pady=5)
        self.status_bar.pack(side="bottom", fill="x")
        
        self.protocol("WM_DELETE_WINDOW", self._on_cancel_moq)
        
    def _on_cancel_moq(self):
        self.result = "CANCEL"
        self._wait_var.set(1)
        self.destroy()

    def _create_widgets(self):
        main_frame = Frame(self, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        # --- Top Section: Global MOQs ---
        top_frame = LabelFrame(main_frame, text="1. Define Global MOQs", padx=10, pady=10)
        top_frame.pack(fill="x", pady=(0, 10))
        
        Button(top_frame, text="Set Global MOQs", command=self._set_global_moq).pack(side="left", padx=(0, 10))
        Label(top_frame, textvariable=self.global_moq_lbl_var, font=("Arial", 10)).pack(side="left")

        # --- Middle Section: Grid ---
        grid_frame = LabelFrame(main_frame, text="2. Assign MOQs to Assemblies", padx=10, pady=10)
        grid_frame.pack(fill="both", expand=True, pady=10)

        columns = ("assy", "moqs", "status")
        self.tree = Treeview(grid_frame, columns=columns, show="headings", height=10, selectmode="extended")
        self.tree.heading("assy", text="Assembly #")
        self.tree.heading("moqs", text="Assigned MOQs")
        self.tree.heading("status", text="Status")
        
        self.tree.column("assy", width=150, anchor="center")
        self.tree.column("moqs", width=250, anchor="center")
        self.tree.column("status", width=100, anchor="center")

        scrollbar = Scrollbar(grid_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.tag_configure("missing", foreground="red")
        self.tree.tag_configure("global", foreground="green")
        self.tree.tag_configure("custom", foreground="#0056b3")

        self._populate_tree()

        # Action Buttons under Grid
        action_frame = Frame(main_frame)
        action_frame.pack(fill="x", pady=5)
        Button(action_frame, text="Apply Global MOQs to Selected", command=self._apply_global_to_selected).pack(side="left", fill="x", expand=True, padx=2)
        Button(action_frame, text="Set Custom MOQs for Selected", command=self._set_custom_to_selected).pack(side="left", fill="x", expand=True, padx=2)

        # --- Bottom Section: Confirm ---
        btn_frame = Frame(main_frame)
        btn_frame.pack(fill="x", pady=(10, 0))
        Button(btn_frame, text="Confirm & Proceed", bg="#2ead4e", fg="white", font=("Arial", 10, "bold"), command=self._on_confirm).pack(side="right", padx=5)
        Button(btn_frame, text="⬅ Back to Map Columns", bg="#ffc107", fg="black", command=self._on_back).pack(side="right", padx=5)
        Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="right", padx=5)

    def _format_moq_list(self, moqs):
        if not moqs:
            return "- None -"
        return "[" + ", ".join(str(m) for m in moqs) + "]"

    def _populate_tree(self):
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)

        for assy in self.unique_assemblies:
            moqs = self.assembly_moqs[assy]
            moq_str = self.format_moq_str(moqs)
            
            if not moqs:
                status = "🔴 Missing"
                tag = "missing"
            elif moqs == self.global_moqs:
                status = "🟢 Global"
                tag = "global"
            else:
                status = "🔵 Custom"
                tag = "custom"
                
            self.tree.insert("", "end", iid=assy, values=(assy, moq_str, status), tags=(tag,))

    def format_moq_str(self, moqs):
        if not moqs:
            return "- None -"
        return f"[{', '.join(str(m) for m in sorted(moqs))}]"

    def _set_global_moq(self):
        # Reusing the existing CategoryInputDialog just for picking MOQs
        dialog = CategoryInputDialog(self, initial_categories=list(self.global_moqs))
        res = dialog.get_categories()
        if res is not None:
            # Check if user entered numbers
            try:
                old_global = list(self.global_moqs)
                self.global_moqs = sorted([int(x) for x in res])
                self.global_moq_lbl_var.set(f"Current Global MOQs: {self.format_moq_str(self.global_moqs)}")
                # Apply new Global MOQs ONLY to assemblies using Global MOQs or with no MOQs set yet.
                # Do NOT overwrite assemblies that currently have Custom MOQs!
                for assy in self.unique_assemblies:
                    current = self.assembly_moqs.get(assy, [])
                    if not current or current == old_global:
                        self.assembly_moqs[assy] = list(self.global_moqs)
                self._populate_tree()
            except ValueError:
                show_error("Invalid Input", "MOQs must be integer numbers.", parent=self)

    def _on_back(self):
        self.result = "BACK"
        self._wait_var.set(1)
        self.destroy()

    def _apply_global_to_selected(self):
        if not self.global_moqs:
            show_error("No Global MOQs", "Please define Global MOQs first.", parent=self)
            return

        selected = self.tree.selection()
        if not selected:
            show_info("No Selection", "Please select assemblies from the table.", parent=self)
            return

        for iid in selected:
            self.assembly_moqs[iid] = list(self.global_moqs)
            
        self._populate_tree()

    def _set_custom_to_selected(self):
        selected = self.tree.selection()
        if not selected:
            show_info("No Selection", "Please select one or more assemblies from the table.", parent=self)
            return

        initial_cats = []
        if selected:
            first_iid = selected[0]
            existing = self.assembly_moqs.get(first_iid, [])
            if existing and sorted(existing) != sorted(self.global_moqs):
                initial_cats = list(existing)

        dialog = CategoryInputDialog(self, initial_categories=initial_cats)
        res = dialog.get_categories()
        
        if res is not None:
            try:
                custom_moqs = sorted([int(x) for x in res])
                for iid in selected:
                    self.assembly_moqs[iid] = list(custom_moqs)
                self._populate_tree()
            except ValueError:
                show_error("Invalid Input", "MOQs must be integer numbers.", parent=self)

    def _on_confirm(self):
        # Validation: Any missing?
        missing = [assy for assy, moqs in self.assembly_moqs.items() if not moqs]
        if missing:
            msg = "The following assemblies have NO MOQs assigned:\n" + ", ".join(missing[:5])
            if len(missing) > 5:
                msg += "..."
            msg += "\n\nAre you sure you want to proceed without MOQs for them? (They will be skipped in Sourcing)"
            if not messagebox.askyesno("Missing MOQs", msg, parent=self):
                return
        
        # Show Yellow Status Bar Here!
        self.status_bar.config(text="⏳ Applying calculations to BOM ...", bg="orange", fg="white")
        self.update_idletasks()
        
        self.result = self.assembly_moqs
        self._wait_var.set(1)

    def get_assembly_moqs(self):
        self.wait_variable(self._wait_var)
        return getattr(self, 'result', None), self.global_moqs


class MassUpdateDialog(Toplevel):
    def __init__(self, parent, current_data, item_label, value_label):
        super().__init__(parent)
        self.parent = parent
        self.current_data = current_data
        self.item_label = item_label
        self.value_label = value_label
        self.title(f"Mass Update - {item_label}")
        self.geometry("450x600")
        self.transient(parent)
        self.grab_set()
        
        self.entry_vars = {}
        
        self._create_widgets()
        self._center_on_master()

    def _center_on_master(self):
        self.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        main_frame = Frame(self, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        header_label = Label(main_frame, text=f"Update {self.value_label}s", font=("Arial", 14, "bold"), fg="#2c75b1")
        header_label.pack(pady=(0, 10))
        
        instruction = "Use 'Tab' key to navigate quickly between fields."
        Label(main_frame, text=instruction, justify="left", font=("Arial", 10), wraplength=400).pack(pady=(0, 10), anchor="w")

        # Scrollable Canvas
        canvas_frame = Frame(main_frame)
        canvas_frame.pack(fill="both", expand=True)

        self.canvas = Canvas(canvas_frame, highlightthickness=0)
        scrollbar = Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        
        self.scrollable_frame = Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Grid Header
        Label(self.scrollable_frame, text=self.item_label, font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        Label(self.scrollable_frame, text=self.value_label, font=("Arial", 10, "bold")).grid(row=0, column=1, sticky="w", padx=10, pady=5)
        
        # Dynamic Grid of Entries
        for idx, key in enumerate(sorted(self.current_data.keys()), start=1):
            Label(self.scrollable_frame, text=key, font=("Arial", 10)).grid(row=idx, column=0, sticky="w", padx=10, pady=5)
            
            var = StringVar(value=str(self.current_data[key]))
            self.entry_vars[key] = var
            
            entry = Entry(self.scrollable_frame, textvariable=var, width=15, justify="right")
            entry.grid(row=idx, column=1, padx=10, pady=5)
            
        # Buttons
        button_frame = Frame(main_frame)
        button_frame.pack(side="bottom", fill="x", pady=(15, 0))

        btn_cancel = Button(button_frame, text="Cancel", command=self.destroy, width=15)
        btn_cancel.pack(side="left", padx=5)

        btn_save = Button(button_frame, text="Save All Changes", command=self._save_changes, width=15)
        btn_save.pack(side="right", padx=5)

        apply_panel_theme(self)

    def _save_changes(self):
        updated_data = {}
        error_keys = []
        
        # Validate all entries before applying
        for key, var in self.entry_vars.items():
            val_str = var.get().strip()
            try:
                updated_data[key] = float(val_str)
            except ValueError:
                error_keys.append(key)
                
        if error_keys:
            err_msg = ", ".join(error_keys[:5])
            if len(error_keys) > 5:
                err_msg += "..."
            show_error("Validation Error", f"Invalid numeric format for: {err_msg}", parent=self)
            return
            
        # Apply changes to parent
        self.parent.data = updated_data
        self.parent._save_data()
        self.parent._populate_tree()
        self.parent._add_new() # Clear entry fields to refresh state
        
        show_info("Success", "Mass update completed successfully.", parent=self.parent)
        self.destroy()



class ChangeDefaultMarkupDialog(BaseDialog):
    def __init__(self, master, current_val):
        self.new_val = None
        super().__init__(master, "Change Default Markup", make_transient=True)
        self.geometry("380x125")
        
        main_frame = Frame(self, padx=15, pady=10)
        main_frame.pack(fill="both", expand=True)
        
        Label(main_frame, text="New Default Markup Rate:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
        
        self.entry_var = StringVar(value=str(current_val))
        self.entry = Entry(main_frame, textvariable=self.entry_var, font=("Arial", 11))
        self.entry.pack(fill="x", pady=(0, 10))
        self.entry.focus_set()
        
        # Select all in entry
        self.after(50, lambda: [self.entry.select_range(0, 'end'), self.entry.icursor('end')])
        
        # Accept numeric inputs with enter
        self.entry.bind("<Return>", lambda e: self._on_save())
        self.entry.bind("<Escape>", lambda e: self._on_cancel())
        
        btn_frame = Frame(main_frame)
        btn_frame.pack(fill="x", pady=(5, 0))
        
        # styling buttons according to typical dialog styles
        btn_cancel = Button(btn_frame, text="Cancel", command=self._on_cancel, width=10)
        btn_cancel.pack(side="left", padx=5)
        
        btn_save = Button(btn_frame, text="Save", command=self._on_save, width=12)
        btn_save.pack(side="right", padx=5)
        
        self.wait_for_close()
        
    def _on_save(self):
        val_str = self.entry_var.get().strip()
        try:
            val = float(val_str)
            if val <= 0:
                raise ValueError()
        except ValueError:
            show_error("Invalid Input", "Default Markup Rate must be a positive numeric value.", parent=self)
            return
        
        self.new_val = val
        self.destroy()

    def _on_cancel(self):
        self.new_val = None
        self.destroy()

class CurrencyConfigurationDialog(BaseDialog):
    def __init__(self, master):
        from utils import CURRENCY_CONFIG_FILE, EXCHANGE_RATE_FILE, MARKUP_RATE_FILE
        self.file_path = CURRENCY_CONFIG_FILE
        self.old_exch_file = EXCHANGE_RATE_FILE
        self.old_mark_file = MARKUP_RATE_FILE
        
        self.config = self._load_data()
        self.data = self.config.get("currencies", {})
        self.is_editing = False
        
        super().__init__(master, "Currency & Markup Configuration", make_transient=False)
        self.geometry("1200x700")
        
        self.selected_curr = None
        self.curr_var = StringVar()
        self.rate_var = StringVar()
        self.markup_var = StringVar()
        self.default_markup_var = StringVar(value=str(self.config.get("default_markup", 1.10)))
        
        self._create_widgets()
        self.wait_for_close()

    def _load_data(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Migration Logic
        new_config = {"default_markup": 1.10, "currencies": {}}
        rates = {}
        markups = {}
        
        if os.path.exists(self.old_exch_file):
            try:
                with open(self.old_exch_file, 'r') as f:
                    rates = json.load(f)
            except: pass
            
        if os.path.exists(self.old_mark_file):
            try:
                with open(self.old_mark_file, 'r') as f:
                    markups = json.load(f)
            except: pass
            
        for curr, rate in rates.items():
            new_config["currencies"][curr] = {
                "rate": float(rate),
                "markup": float(markups.get(curr, 1.10))
            }
            
        for curr, markup in markups.items():
            if curr not in new_config["currencies"]:
                new_config["currencies"][curr] = {
                    "rate": 1.0,
                    "markup": float(markup)
                }
        
        # Initial Save to prevent repeated migration
        self._save_config(new_config)
        return new_config

    def _save_config(self, config=None):
        if config is None:
            config = {
                "default_markup": float(self.default_markup_var.get() or 1.10),
                "currencies": self.data
            }
        try:
            with open(self.file_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            show_error("Save Error", f"Failed to save configuration: {e}", parent=self)

    def _change_default(self):
        dialog = ChangeDefaultMarkupDialog(self, self.default_markup_var.get())
        if dialog.new_val is not None:
            self.default_markup_var.set(f"{dialog.new_val:.2f}")
            self._save_config()
            show_info("Success", "Default Markup Rate updated successfully.", parent=self)

    def _create_widgets(self):
        main_frame = Frame(self, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        header_frame = Frame(main_frame, bg="#fdfcf0", bd=2, relief="groove")
        header_frame.pack(fill="x", pady=(0, 15))
        Label(header_frame, text="CURRENCY & MARKUP CONFIGURATION", font=("Arial", 16, "bold"), fg="#b8860b", bg="#fdfcf0").pack(pady=15)

        # Default Markup Section
        def_frame = LabelFrame(main_frame, text="Global Settings", padx=10, pady=10)
        def_frame.pack(fill="x", pady=(0, 15))
        
        Label(def_frame, text="Default Markup Rate (for new entries):").pack(side="left")
        self.ent_default_markup = Entry(def_frame, textvariable=self.default_markup_var, width=10, state="readonly")
        self.ent_default_markup.pack(side="left", padx=10)
        Button(def_frame, text="Change Default", command=self._change_default, bg="#e2e8f0").pack(side="left", padx=5)

        # Treeview Section
        tree_frame = Frame(main_frame)
        tree_frame.pack(fill="both", expand=True)
        
        cols = ("curr", "rate", "markup")
        self.tree = Treeview(tree_frame, columns=cols, show="headings", height=10)
        self.tree.heading("curr", text="Currency Code")
        self.tree.heading("rate", text="Exch. Rate (to USD)")
        self.tree.heading("markup", text="Markup Multiplier")
        
        for c in cols:
            self.tree.column(c, anchor=CENTER, width=150)
            
        self.tree.pack(side="left", fill="both", expand=True)
        sb = TtkScrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._populate_tree()

        # Edit Section
        edit_frame = LabelFrame(main_frame, text="Edit Selected Currency", padx=10, pady=10)
        edit_frame.pack(fill="x", pady=15)
        
        Label(edit_frame, text="Currency Code:").grid(row=0, column=0, sticky="w", pady=5)
        self.ent_curr = Entry(edit_frame, textvariable=self.curr_var, state="readonly")
        self.ent_curr.grid(row=0, column=1, sticky="ew", padx=10)
        
        Label(edit_frame, text="Rate to USD:").grid(row=1, column=0, sticky="w", pady=5)
        self.ent_rate = Entry(edit_frame, textvariable=self.rate_var, state="readonly")
        self.ent_rate.grid(row=1, column=1, sticky="ew", padx=10)
        
        Label(edit_frame, text="Markup:").grid(row=2, column=0, sticky="w", pady=5)
        markup_entry_frame = Frame(edit_frame)
        markup_entry_frame.grid(row=2, column=1, sticky="ew", padx=10)
        self.ent_markup = Entry(markup_entry_frame, textvariable=self.markup_var, state="readonly")
        self.ent_markup.pack(side="left", fill="x", expand=True)
        Button(markup_entry_frame, text="Reset Default", font=("Arial", 8), command=lambda: self.markup_var.set(self.default_markup_var.get()) if self.is_editing else None).pack(side="left", padx=5)
        
        edit_frame.columnconfigure(1, weight=1)

        # Setup Up/Down arrow keys navigation and auto-selection
        def select_all(widget):
            widget.select_range(0, 'end')
            widget.icursor('end')

        def focus_and_select(widget):
            if str(widget.cget("state")) != "readonly":
                widget.focus_set()
                self.after(10, lambda: select_all(widget))

        # FocusIn events
        self.ent_curr.bind("<FocusIn>", lambda e: self.after(10, lambda: select_all(self.ent_curr) if str(self.ent_curr.cget("state")) != "readonly" else None))
        self.ent_rate.bind("<FocusIn>", lambda e: self.after(10, lambda: select_all(self.ent_rate) if str(self.ent_rate.cget("state")) != "readonly" else None))
        self.ent_markup.bind("<FocusIn>", lambda e: self.after(10, lambda: select_all(self.ent_markup) if str(self.ent_markup.cget("state")) != "readonly" else None))

        # Arrow key bindings
        self.ent_curr.bind("<Down>", lambda e: focus_and_select(self.ent_rate))
        self.ent_curr.bind("<Up>", lambda e: focus_and_select(self.ent_markup))

        self.ent_rate.bind("<Up>", lambda e: focus_and_select(self.ent_curr))
        self.ent_rate.bind("<Down>", lambda e: focus_and_select(self.ent_markup))

        self.ent_markup.bind("<Up>", lambda e: focus_and_select(self.ent_rate))
        self.ent_markup.bind("<Down>", lambda e: focus_and_select(self.ent_curr))

        # Action Buttons
        btn_frame = Frame(main_frame)
        btn_frame.pack(fill="x", pady=10)
        
        self.btn_save = Button(btn_frame, text="Update / Save", bg="#2ead4e", fg="white", font=("Arial", 10, "bold"), width=15, command=self._save_update)
        self.btn_save.pack(side="right", padx=5)

        self.btn_delete = Button(btn_frame, text="Delete", bg="#fed7d7", font=("Arial", 10, "bold"), width=15, command=self._delete_item)
        self.btn_delete.pack(side="right", padx=5)

        self.btn_edit = Button(btn_frame, text="Edit Selected", bg="#e2e8f0", font=("Arial", 10, "bold"), width=15, command=self._edit_selected)
        self.btn_edit.pack(side="right", padx=5)

        self.btn_add = Button(btn_frame, text="Add New", bg="#bee3f8", font=("Arial", 10, "bold"), width=15, command=self._add_new)
        self.btn_add.pack(side="right", padx=5)

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        for curr in sorted(self.data.keys()):
            d = self.data[curr]
            self.tree.insert("", "end", values=(curr, d['rate'], d['markup']))

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0], "values")
            self.selected_curr = vals[0]
            self.curr_var.set(vals[0])
            self.rate_var.set(vals[1])
            self.markup_var.set(vals[2])
            
            # Reset back to view-only mode on selection
            self.ent_curr.config(state="readonly")
            self.ent_rate.config(state="readonly")
            self.ent_markup.config(state="readonly")
            self.is_editing = False

    def _add_new(self):
        self.selected_curr = None
        self.curr_var.set("")
        self.rate_var.set("1.0")
        self.markup_var.set(self.default_markup_var.get() or "1.10")
        self.ent_curr.config(state="normal")
        self.ent_rate.config(state="normal")
        self.ent_markup.config(state="normal")
        self.is_editing = True
        self.ent_curr.focus_set()

    def _edit_selected(self):
        if not self.selected_curr:
            show_error("No Selection", "Please select a currency to edit first.", parent=self)
            return
        
        self.is_editing = True
        self.ent_rate.config(state="normal")
        self.ent_markup.config(state="normal")
        self.ent_rate.focus_set()

    def _reset_to_view_mode(self):
        self.selected_curr = None
        self.curr_var.set("")
        self.rate_var.set("")
        self.markup_var.set("")
        self.ent_curr.config(state="readonly")
        self.ent_rate.config(state="readonly")
        self.ent_markup.config(state="readonly")
        self.is_editing = False

    def _save_update(self):
        curr = self.curr_var.get().strip().upper()
        if not curr: return
        try:
            rate = float(self.rate_var.get())
            markup = float(self.markup_var.get())
        except ValueError:
            show_error("Input Error", "Rate and Markup must be numeric.", parent=self)
            return
            
        self.data[curr] = {"rate": rate, "markup": markup}
        self._save_config()
        self._populate_tree()
        self._reset_to_view_mode()
        show_info("Success", f"Currency '{curr}' updated.", parent=self)

    def _delete_item(self):
        if not self.selected_curr: return
        dialog = SourcingCancelWarningDialog(self, msg_type="delete_curr", extra_info=self.selected_curr)
        self.wait_window(dialog)
        if dialog.result:
            del self.data[self.selected_curr]
            self._save_config()
            self._populate_tree()
            self._reset_to_view_mode()

    def _on_cancel(self):
        if self.is_editing:
            dialog = SourcingCancelWarningDialog(self, msg_type="currency")
            self.wait_window(dialog)
            if not dialog.result:
                return
        self.result = None
        self.destroy()

class SourcingCancelWarningDialog(Toplevel):
    def __init__(self, parent, msg_type="sourcing", extra_info=""):
        super().__init__(parent)
        
        if msg_type == "no_moq":
            self.title("WARNING: No MOQ Assigned?")
            header_text = "WARNING: NO MOQ ASSIGNED?"
        elif msg_type == "delete_curr":
            self.title("WARNING: Confirm Delete?")
            header_text = "WARNING: CONFIRM DELETE?"
        else:
            self.title("WARNING: Exit Without Saving?")
            header_text = "WARNING: EXIT WITHOUT SAVING?"
            
        self.geometry("620x260")
        self.transient(parent)
        self.grab_set()
        self.configure(bg="#f2f2f2")
        
        self.result = False
        
        # 1. Header Frame (Yellow/Cream with solid black border)
        header_frame = Frame(self, bg="#fffde7", bd=1, relief="solid")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        Label(
            header_frame, 
            text=header_text, 
            font=("Arial", 12, "bold"), 
            fg="#856404", 
            bg="#fffde7"
        ).pack(pady=8)
        
        # 2. Main Message Box (White background with solid black border)
        msg_frame = Frame(self, bg="white", bd=1, relief="solid")
        msg_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        if msg_type == "moq":
            msg_text = (
                "MOQ data will not be saved into the system.\n\n"
                "Are you sure you want to exit without saving?\n"
                "(Click 'Yes' to discard changes and exit, 'No' to remain in MOQ Assignment)"
            )
        elif msg_type == "no_moq":
            msg_text = (
                "No MOQs have been assigned to any assemblies.\n\n"
                "If you exit now, you will not be able to perform BOM Sourcing calculations later.\n\n"
                "Are you sure you want to exit without assigning MOQs?\n"
                "(Click 'Yes' to exit, 'No' to remain in MOQ Assignment)"
            )
        elif msg_type == "verification":
            msg_text = (
                "BOM data will not be saved into the system.\n\n"
                "Are you sure you want to exit without saving?\n"
                "(Click 'Yes' to discard changes and exit, 'No' to remain in BOM Verification)"
            )
        elif msg_type == "currency":
            msg_text = (
                "Currency & Markup changes will not be saved into the system.\n\n"
                "Are you sure you want to exit without saving?\n"
                "(Click 'Yes' to discard changes and exit, 'No' to remain in Currency Configuration)"
            )
        elif msg_type == "delete_curr":
            msg_text = (
                f"Currency '{extra_info}' will be deleted from the system.\n\n"
                "Are you sure you want to delete this currency?\n"
                "(Click 'Yes' to confirm delete, 'No' to cancel)"
            )
        else:
            msg_text = (
                "Sourcing calculation will not be saved into the system.\n\n"
                "Are you sure you want to exit without saving?\n"
                "(Click 'Yes' to discard changes and exit, 'No' to remain in BOM Sourcing)"
            )
        
        Label(
            msg_frame, 
            text=msg_text, 
            font=("Arial", 10), 
            fg="black", 
            bg="white", 
            wraplength=560, 
            justify="left", 
            anchor="nw"
        ).pack(fill="both", expand=True, padx=20, pady=12)
        
        # 3. Action Buttons Frame
        btn_frame = Frame(self, bg="#f2f2f2")
        btn_frame.pack(fill="x", side="bottom", padx=20, pady=(0, 18))
        
        # Cancel (bottom-left) - Styled premium button
        btn_no = Button(
            btn_frame, 
            text="Cancel", 
            command=self.on_no, 
            width=16,
            padx=10
        )
        btn_no.pack(side="left", padx=(0, 10))
        style_premium_button(btn_no, bg_color="#1A365D", hover_bg="#0077B6")
        self.cancel_btn = btn_no
        
        # Proceed (bottom-right) - Styled premium button (Red for delete)
        yes_bg = "#d9534f" if msg_type == "delete_curr" else "#1A365D"
        yes_active_bg = "#c9302c" if msg_type == "delete_curr" else "#0077B6"
        yes_text = "Delete" if msg_type == "delete_curr" else "Proceed"
        
        btn_yes = Button(
            btn_frame, 
            text=yes_text, 
            command=self.on_yes, 
            width=18,
            padx=10
        )
        btn_yes.pack(side="right", padx=(10, 0))
        style_premium_button(btn_yes, bg_color=yes_bg, hover_bg=yes_active_bg)
        self.confirm_btn = btn_yes

        # Keyboard bindings
        self.bind("<Return>", lambda e: self.on_yes())
        self.bind("<Left>", lambda e: self._focus_cancel())
        self.bind("<Right>", lambda e: self._focus_confirm())
        
        btn_no.bind("<Return>", lambda e: self.on_no_event(e))
        btn_yes.bind("<Return>", lambda e: self.on_yes_event(e))

        # Focus highlights
        no_bg = "#1A365D"
        no_hbg = "#0077B6"
        btn_no.bind("<FocusIn>", lambda e: btn_no.configure(bg=no_hbg))
        btn_no.bind("<FocusOut>", lambda e: btn_no.configure(bg=no_bg))
        
        btn_yes.bind("<FocusIn>", lambda e: btn_yes.configure(bg=yes_active_bg))
        btn_yes.bind("<FocusOut>", lambda e: btn_yes.configure(bg=yes_bg))
        
        # Center on master
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self.on_no)
        
        btn_yes.focus_set()

    def _focus_cancel(self):
        self.cancel_btn.focus_set()

    def _focus_confirm(self):
        self.confirm_btn.focus_set()

    def on_no_event(self, event):
        self.on_no()
        return "break"

    def on_yes_event(self, event):
        self.on_yes()
        return "break"

    def on_no(self):
        self.result = False
        self.destroy()

    def on_yes(self):
        self.result = True
        self.destroy()


class BOMVerificationSessionDialog(Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("BOM Verification Session Manager")
        # Prevent the global monkeypatch from auto-zooming DURING layout construction
        self._skip_autofit = True
        self.geometry("1100x650")
        self.resizable(True, True)
        self.minsize(900, 550)
        # Keep grab_set for modal behaviour; remove transient so min/max buttons work
        self.grab_set()
        
        self.result = None # Can be "NEW", a dictionary representing session data, or None
        self.temp_file_path = None
        
        self._create_widgets()
        self._load_sessions()
        self._center_on_screen()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_on_master(self):
        self.update_idletasks()
        master = self.master
        if master and master.winfo_viewable():
            x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
            y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")

    def _center_on_screen(self):
        """Center based on screen dimensions (used when not transient)."""
        self.update_idletasks()
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w = self.winfo_width()
            h = self.winfo_height()
            x = (sw // 2) - (w // 2)
            y = (sh // 2) - (h // 2)
            # Use _orig_geometry directly to bypass patched_geometry
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _create_widgets(self):
        header = Frame(self, bg="#1A365D")
        header.pack(fill="x", side="top")
        Label(header, text="BOM Verification Sessions", font=("Segoe UI", 14, "bold"), fg="white", bg="#1A365D", pady=12).pack(side="left", padx=20)

        main_frame = Frame(self, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)
        
        # Button frame (packed first at bottom to reserve space)
        btn_frame = Frame(main_frame)
        btn_frame.pack(side="bottom", fill="x", pady=(10, 10))
        
        self.btn_new = Button(btn_frame, text="🆕 Start New", command=self._on_new, width=15)
        self.btn_new.pack(side="left", padx=5)
        style_premium_button(self.btn_new, bg_color="#1A365D", hover_bg="#0077B6")
        
        self.btn_requote = Button(btn_frame, text="🔄 Requote", command=self._on_requote, width=15)
        self.btn_requote.pack(side="left", padx=5)
        style_premium_button(self.btn_requote, bg_color="#e67e22", hover_bg="#d35400")
        
        self.btn_resume = Button(btn_frame, text="▶️ Resume Selected", command=self._on_resume, width=20)
        self.btn_resume.pack(side="left", padx=5)
        style_premium_button(self.btn_resume, bg_color="#3182ce", hover_bg="#2b6cb0")
        
        self.btn_delete = Button(btn_frame, text="❌ Delete Session", command=self._on_delete, width=15)
        self.btn_delete.pack(side="left", padx=5)
        style_premium_button(self.btn_delete, bg_color="#d9534f", hover_bg="#c9302c")
        
        self.btn_edit_saved = Button(btn_frame, text="✏️ Edit Saved BOM", command=self._on_edit_saved, width=18)
        self.btn_edit_saved.pack(side="left", padx=5)
        style_premium_button(self.btn_edit_saved, bg_color="#4a5568", hover_bg="#2d3748")
        
        self.btn_cancel = Button(btn_frame, text="Cancel", command=self._on_close, width=12)
        self.btn_cancel.pack(side="right", padx=5)
        style_premium_button(self.btn_cancel, bg_color="#718096", hover_bg="#4a5568")
        
        # Table frame (takes remaining center space)
        table_frame = Frame(main_frame)
        table_frame.pack(side="top", fill="both", expand=True)
        
        cols = ("customer", "rfq", "time", "created_by", "filename")
        self.tree = Treeview(table_frame, columns=cols, show="headings", height=10, selectmode="extended")
        self.tree.heading("customer", text="Customer")
        self.tree.heading("rfq", text="RFQ Number")
        self.tree.heading("time", text="Date & Time")
        self.tree.heading("created_by", text="Created By")
        self.tree.heading("filename", text="UUID")
        
        self.tree.column("customer", width=160, anchor="center")
        self.tree.column("rfq", width=100, anchor="center")
        self.tree.column("time", width=160, anchor="center")
        self.tree.column("created_by", width=120, anchor="center")
        self.tree.column("filename", width=200, anchor="center")
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        sb = TtkScrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        
        apply_panel_theme(self)

    def _load_sessions(self):
        from utils import TEMP_DIR, BOM_DATA_DIR
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        session_rows = []
        existing_pairs = set()
        if os.path.exists(TEMP_DIR):
            for f in os.listdir(TEMP_DIR):
                if f.endswith(".json"):
                    fpath = os.path.join(TEMP_DIR, f)
                    try:
                        with open(fpath, 'r', encoding='utf-8') as file:
                            data = json.load(file)
                            time_str = data.get("timestamp", "N/A")
                            from datetime import datetime
                            try:
                                dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                                time_str = dt.strftime("%Y-%m-%d %I:%M:%S %p")
                            except Exception:
                                pass
                            created_by = data.get("created_by", "N/A")
                            cust_info = data.get("customer_info", [None, "N/A", "N/A"])
                            cust_name = cust_info[1] if len(cust_info) > 1 else "N/A"
                            rfq_num = cust_info[2] if len(cust_info) > 2 else "N/A"
                            uuid_only = os.path.splitext(f)[0]
                            existing_pairs.add((cust_name, rfq_num))
                            session_rows.append((fpath, cust_name, rfq_num, time_str, created_by, uuid_only))
                    except Exception as e:
                        print(f"Error loading session file {f}: {e}")

        # Sort by Date & Time descending (latest session first)
        from datetime import datetime as _dt
        def _parse_session_date(row):
            for fmt in ("%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"):
                try:
                    return _dt.strptime(row[3], fmt)
                except Exception:
                    pass
            return _dt.min
        session_rows.sort(key=_parse_session_date, reverse=True)

        for (fpath, cust_name, rfq_num, time_str, created_by, uuid_only) in session_rows:
            self.tree.insert("", "end", iid=fpath, values=(cust_name, rfq_num, time_str, created_by, uuid_only))

    def _on_new(self):
        self.result = "NEW"
        self.destroy()
        
    def _on_requote(self):
        self.grab_release()
        self.withdraw()
        from requote import RequoteWizardDialog
        dlg = RequoteWizardDialog(self.master)
        self.master.wait_window(dlg)
        if not dlg.result:
            self.deiconify()
            self.grab_set()
            self.lift()
            self.focus_force()
            return
        self.result = dlg.result
        self.destroy()
        
    def _on_resume(self):
        selected = self.tree.selection()
        if not selected:
            show_error("No Selection", "Please select a session to resume, or click 'Start New'.", parent=self)
            return
            
        fpath = selected[0]
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if this is a verified BOM instead of a session file
            if "Assemblies" in data and "Customer" in data:
                # Convert verified BOM format to session format
                import pandas as pd
                cust_name = data.get("Customer", "")
                rfq_num = data.get("RFQ", "")
                commodity = data.get("Commodity", "")
                
                df_data = []
                for assy in data.get("Assemblies", []):
                    assy_num = assy.get("Assy #", "")
                    assy_model = assy.get("Assy Model", "")
                    assy_rev = assy.get("Assy Rev", "")
                    for comp in assy.get("Components", []):
                        df_data.append({
                            "Assy #": assy_num,
                            "Assy Model": assy_model,
                            "Assy Rev": assy_rev,
                            "Part": comp.get("Part", ""),
                            "Description": comp.get("Description", ""),
                            "Qty": comp.get("Qty", 1.0),
                            "UOM": comp.get("UOM", ""),
                            "MFR": comp.get("MFR", ""),
                            "MPN": comp.get("MPN", ""),
                            "Line Item": comp.get("Line Item", "")
                        })
                
                self.result = {
                    "is_edit_saved": True,
                    "customer_info": [None, cust_name, rfq_num, "", commodity],
                    "mapping": {},
                    "assembly_status": {str(assy.get("Assy #", "")): "Viewed" for assy in data.get("Assemblies", [])},
                    "df_data": df_data,
                    "temp_file_path": None
                }
            else:
                self.result = data
            self.temp_file_path = fpath
            self.destroy()
        except Exception as e:
            show_error("Error", f"Failed to load session:\n{e}", parent=self)
            
    def _on_delete(self):
        selected = self.tree.selection()
        if not selected:
            show_error("No Selection", "Please select one or more sessions to delete.", parent=self)
            return
            
        from utils import TEMP_DIR
        valid_paths = [sp for sp in selected if TEMP_DIR in sp]
        invalid_paths = [sp for sp in selected if TEMP_DIR not in sp]

        if invalid_paths and not valid_paths:
            show_error("Invalid Action", "Reverted database BOM entries cannot be deleted here. Please manage them from the Project Management Panel.", parent=self)
            return

        count = len(valid_paths)
        msg = f"Are you sure you want to permanently delete the {count} selected verification session(s)?" if count > 1 else "Are you sure you want to permanently delete this verification session?"

        if messagebox.askyesno("Confirm Delete", msg, parent=self):
            deleted_count = 0
            errors = []
            for fpath in valid_paths:
                try:
                    if os.path.exists(fpath):
                        os.remove(fpath)
                    deleted_count += 1
                except Exception as e:
                    errors.append(f"{os.path.basename(fpath)}: {e}")

            self._load_sessions()
            if errors:
                show_error("Partial Deletion Warning", f"Successfully deleted {deleted_count} session(s).\nFailed to delete:\n" + "\n".join(errors), parent=self)
                
    def _on_close(self):
        self.result = None
        self.destroy()

    def _on_edit_saved(self):
        import pandas as pd
        self.grab_release()
        self.withdraw()
        
        sub_win = Toplevel(self.master)
        sub_win.title("Select Saved BOM to Edit")
        sub_win.geometry("1200x700")
        sub_win.grab_set()
        
        from sourcing_wizard import BOMDatabaseSearchPanel
        search_panel = BOMDatabaseSearchPanel(sub_win, title="Select Saved BOM to Edit", only_assigned_moqs=False)
        search_panel.pack(fill="both", expand=True)
        if hasattr(search_panel, 'btn_assign'):
            search_panel.btn_assign.config(text="Select & Edit BOM", command=lambda: search_panel._start_sourcing("edit_saved"))
            
        def on_sub_win_close():
            try: sub_win.destroy()
            except: pass
            
        sub_win.protocol("WM_DELETE_WINDOW", on_sub_win_close)
        
        search_result = search_panel.wait_for_close()
        try: sub_win.destroy()
        except: pass
        
        if not search_result:
            self.deiconify()
            self.grab_set()
            self.lift()
            self.focus_force()
            return
            
        action, df_final_consolidated, cust_name, rfq_num, filepath, raw_data, date_str = search_result
        
        # Prepare the result dictionary representing a session
        self.result = {
            "is_edit_saved": True,
            "customer_info": [None, cust_name, rfq_num, ""],
            "mapping": {},
            "assembly_status": {str(assy): "Viewed" for assy in df_final_consolidated['Assy #'].unique() if pd.notna(assy)},
            "df_data": df_final_consolidated.to_dict(orient='records'),
            "temp_file_path": None
        }
        self.destroy()


class SourcingCancelWarningDialog(Toplevel):
    """
    Warning dialog shown when canceling or exiting sourcing workflows / windows.
    """
    def __init__(self, parent, msg_type="default", extra_info=""):
        super().__init__(parent)
        self._skip_autofit = True
        
        if msg_type == "no_moq":
            self.title("WARNING: No MOQ Assigned?")
            header_text = "WARNING: NO MOQ ASSIGNED?"
        elif msg_type == "delete_curr":
            self.title("WARNING: Confirm Delete?")
            header_text = "WARNING: CONFIRM DELETE?"
        else:
            self.title("WARNING: Exit Without Saving?")
            header_text = "WARNING: EXIT WITHOUT SAVING?"

        self.geometry("540x240")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(bg="#EBF8FF")
        self.result = False

        main_frame = Frame(self, padx=20, pady=20, bg="#EBF8FF")
        main_frame.pack(fill="both", expand=True)

        if msg_type == "verification":
            msg_text = "BOM data will not be saved into the system.\n\nAre you sure you want to exit without saving?\n(Click 'Yes' to discard changes and exit, 'No' to remain in BOM Verification)"
        elif msg_type == "moq":
            msg_text = "MOQ data will not be saved into the system.\n\nAre you sure you want to exit without saving?\n(Click 'Yes' to discard changes and exit, 'No' to remain in MOQ Assignment)"
        elif msg_type == "no_moq":
            msg_text = "No MOQs have been assigned to any assemblies.\n\nAre you sure you want to exit without assigning MOQs?"
        elif msg_type == "currency":
            msg_text = "Currency & Markup changes will not be saved.\n\nAre you sure you want to exit without saving?"
        elif msg_type == "delete_curr":
            msg_text = f"Currency '{extra_info}' will be deleted from the system.\n\nAre you sure you want to delete this currency?"
        else:
            msg_text = "Sourcing calculation will not be saved into the system.\n\nAre you sure you want to exit without saving?\n(Click 'Yes' to discard changes and exit, 'No' to remain in BOM Sourcing)"

        Label(main_frame, text=header_text, font=("Segoe UI", 12, "bold"), fg="#C53030", bg="#EBF8FF").pack(anchor="w", pady=(0, 10))
        Label(main_frame, text=msg_text, font=("Segoe UI", 10), fg="#1A365D", bg="#EBF8FF", justify="left", wraplength=480).pack(anchor="w", pady=(0, 20))

        btn_frame = Frame(main_frame, bg="#EBF8FF")
        btn_frame.pack(fill="x", side="bottom")

        btn_no = Button(btn_frame, text="No (Return to Workflow)", command=self.on_no, bg="#E2E8F0", fg="#2D3748", font=("Segoe UI", 10, "bold"), bd=0, relief="flat", cursor="hand2", padx=15, pady=6)
        btn_no.pack(side="left")

        btn_yes = Button(btn_frame, text="Yes (Exit / Discard)", command=self.on_yes, bg="#DC3545", fg="white", font=("Segoe UI", 10, "bold"), bd=0, relief="flat", cursor="hand2", padx=15, pady=6)
        btn_yes.pack(side="right")

        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except:
            pass

        self.protocol("WM_DELETE_WINDOW", self.on_no)

    def on_no(self):
        self.result = False
        self.destroy()

    def on_yes(self):
        self.result = True
        self.destroy()


class ProgressWindow(Toplevel):
    def __init__(self, parent, title="Processing", message="Please wait..."):
        super().__init__(parent)
        self._skip_autofit = True
        self.title(title)
        self.geometry("450x150")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Center on parent
        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except:
            pass
        
        self.configure(bg="#EBF8FF")
        
        self.lbl_message = Label(self, text=message, font=("Segoe UI", 10, "bold"), bg="#EBF8FF", fg="#1A365D")
        self.lbl_message.pack(pady=(20, 5), padx=20, anchor="w")
        
        from tkinter.ttk import Progressbar
        self.progress = Progressbar(self, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=10, padx=20, fill="x")
        
        self.lbl_status = Label(self, text="Starting...", font=("Segoe UI", 9), bg="#EBF8FF", fg="#4A5568")
        self.lbl_status.pack(pady=(0, 20), padx=20, anchor="w")
        
        # Disable close button to protect process integrity
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        
        self.update()
        
    def update_progress(self, current, total, status_text=None):
        percent = int((current / total) * 100) if total > 0 else 0
        self.progress["value"] = percent
        if status_text:
            self.lbl_status.config(text=f"{status_text} ({percent}%)")
        else:
            self.lbl_status.config(text=f"Progress: {current} / {total} ({percent}%)")
        self.update()


class PartialDispatchAssemblyDialog(Toplevel):
    """
    Dialog prompting users to select specific assemblies for partial dispatch,
    with built-in search, pagination, select/deselect all controls, and scrollable container
    to easily handle 100+ assemblies per RFQ.
    """
    def __init__(self, parent, rfq_num, assemblies, page_size=20):
        super().__init__(parent)
        self._skip_autofit = True
        self.title(f"Select Assemblies for Partial Dispatch - RFQ: {rfq_num}")
        self.geometry("640x560")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.result = None
        
        self.all_assemblies = assemblies
        self.page_size = page_size
        self.current_page = 1
        
        # State map: assy -> IntVar
        self.vars = {assy: IntVar(value=1) for assy in assemblies}
        
        self.configure(bg="#EBF8FF")
        
        main_frame = Frame(self, padx=20, pady=15, bg="#EBF8FF")
        main_frame.pack(fill="both", expand=True)
        
        # Header Area
        top_header = Frame(main_frame, bg="#EBF8FF")
        top_header.pack(fill="x", pady=(0, 5))
        Label(top_header, text="📦 Partial Assembly Dispatch Selection", font=("Segoe UI", 12, "bold"), fg="#1A365D", bg="#EBF8FF").pack(anchor="w")
        Label(top_header, text=f"Select assemblies to dispatch to Costing under RFQ '{rfq_num}' ({len(assemblies)} total assemblies):", font=("Segoe UI", 9), fg="#4A5568", bg="#EBF8FF").pack(anchor="w")

        # Toolbar Frame (Search + Select All/Deselect All)
        toolbar = Frame(main_frame, bg="#EBF8FF")
        toolbar.pack(fill="x", pady=6)
        
        Label(toolbar, text="🔍 Search:", font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#1A365D").pack(side="left", padx=(0, 5))
        self.search_var = StringVar()
        self.search_var.trace("w", lambda *args: self.on_search_changed())
        ent_search = Entry(toolbar, textvariable=self.search_var, font=("Segoe UI", 9), width=22)
        ent_search.pack(side="left", padx=(0, 15))
        
        btn_sel_all = Button(toolbar, text="Select All", command=self.select_all, bg="#E2E8F0", fg="#1A365D", font=("Segoe UI", 8, "bold"), bd=1, relief="solid", padx=8, pady=2, cursor="hand2")
        btn_sel_all.pack(side="left", padx=2)
        
        btn_desel_all = Button(toolbar, text="Deselect All", command=self.deselect_all, bg="#E2E8F0", fg="#1A365D", font=("Segoe UI", 8), bd=1, relief="solid", padx=8, pady=2, cursor="hand2")
        btn_desel_all.pack(side="left", padx=2)

        self.lbl_count = Label(toolbar, text="", font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#2B6CB0")
        self.lbl_count.pack(side="right")

        # Scrollable Assembly Container Frame
        self.container_frame = Frame(main_frame, bg="#FFFFFF", bd=1, relief="solid")
        self.container_frame.pack(fill="both", expand=True, pady=5)
        
        self.canvas = Canvas(self.container_frame, bg="#FFFFFF", highlightthickness=0)
        self.scrollbar = Scrollbar(self.container_frame, orient="vertical", command=self.canvas.yview)
        self.scroll_inner = Frame(self.canvas, bg="#FFFFFF")
        
        self.scroll_inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Pagination Bar
        pag_bar = Frame(main_frame, bg="#EBF8FF")
        pag_bar.pack(fill="x", pady=6)
        
        self.btn_prev = Button(pag_bar, text="◄ Previous", command=self.prev_page, bg="#E2E8F0", fg="#1A365D", font=("Segoe UI", 9, "bold"), bd=1, relief="solid", padx=10, pady=2, cursor="hand2")
        self.btn_prev.pack(side="left")
        
        self.lbl_page = Label(pag_bar, text="Page 1 of 1", font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#1A365D")
        self.lbl_page.pack(side="left", expand=True)
        
        self.btn_next = Button(pag_bar, text="Next ►", command=self.next_page, bg="#E2E8F0", fg="#1A365D", font=("Segoe UI", 9, "bold"), bd=1, relief="solid", padx=10, pady=2, cursor="hand2")
        self.btn_next.pack(side="right")

        # Action Buttons Frame
        btn_frame = Frame(main_frame, bg="#EBF8FF")
        btn_frame.pack(fill="x", side="bottom", pady=(10, 0))
        
        Button(btn_frame, text="Cancel", command=self.on_cancel, bg="#E2E8F0", fg="#2D3748", font=("Segoe UI", 10), bd=0, relief="flat", cursor="hand2", padx=15, pady=5).pack(side="left")
        Button(btn_frame, text="Dispatch Selected Assemblies", command=self.on_confirm, bg="#2EAD4E", fg="white", font=("Segoe UI", 10, "bold"), bd=0, relief="flat", cursor="hand2", padx=15, pady=5).pack(side="right")

        self.filtered_assemblies = list(assemblies)
        self.refresh_view()
        
        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except:
            pass
            
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def on_search_changed(self):
        query = self.search_var.get().strip().lower()
        if query:
            self.filtered_assemblies = [a for a in self.all_assemblies if query in a.lower()]
        else:
            self.filtered_assemblies = list(self.all_assemblies)
        self.current_page = 1
        self.refresh_view()

    def select_all(self):
        for assy in self.filtered_assemblies:
            self.vars[assy].set(1)
        self.update_count_label()

    def deselect_all(self):
        for assy in self.filtered_assemblies:
            self.vars[assy].set(0)
        self.update_count_label()

    def update_count_label(self):
        selected_count = sum(v.get() for v in self.vars.values())
        self.lbl_count.config(text=f"Selected: {selected_count} / {len(self.all_assemblies)}")

    def refresh_view(self):
        for w in self.scroll_inner.winfo_children():
            w.destroy()
            
        total_items = len(self.filtered_assemblies)
        total_pages = max(1, (total_items + self.page_size - 1) // self.page_size)
        if self.current_page > total_pages:
            self.current_page = total_pages
            
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, total_items)
        page_items = self.filtered_assemblies[start_idx:end_idx]
        
        for assy in page_items:
            row_frame = Frame(self.scroll_inner, bg="#FFFFFF", padx=10, pady=4)
            row_frame.pack(fill="x", expand=True)
            
            var = self.vars[assy]
            cb = Checkbutton(
                row_frame,
                text=f"Assembly #{assy}",
                variable=var,
                command=self.update_count_label,
                font=("Segoe UI", 10, "bold"),
                bg="#FFFFFF",
                fg="#1A365D",
                activebackground="#FFFFFF"
            )
            cb.pack(anchor="w")

        self.lbl_page.config(text=f"Page {self.current_page} of {total_pages} ({start_idx+1}-{end_idx} of {total_items})")
        self.btn_prev.config(state="normal" if self.current_page > 1 else "disabled")
        self.btn_next.config(state="normal" if self.current_page < total_pages else "disabled")
        
        self.update_count_label()
        self.canvas.yview_moveto(0)

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_view()

    def next_page(self):
        total_pages = (len(self.filtered_assemblies) + self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_view()

    def on_cancel(self):
        self.result = None
        self.destroy()

    def on_confirm(self):
        selected = [assy for assy, var in self.vars.items() if var.get() == 1]
        if not selected:
            from utils import show_error
            show_error("No Assembly Selected", "Please select at least one assembly to dispatch.", parent=self)
            return
        self.result = selected
        self.destroy()



class DummySupplierDialog(Toplevel):
    """
    Dialog allowing users to enter custom Unit Price, MOQ, Lead Time, and Supplier Name
    for items without valid quotes directly from the Sourcing UI.
    """
    def __init__(self, parent, part_number="", initial_moq=1):
        super().__init__(parent)
        self._skip_autofit = True
        self.title(f"Apply Dummy Supplier Quote - Part: {part_number}")
        self.geometry("480x320")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None # { "supplier": ..., "unit_price": ..., "moq": ..., "lead_time": ... }
        
        self.configure(bg="#EBF8FF")
        
        main_frame = Frame(self, padx=20, pady=20, bg="#EBF8FF")
        main_frame.pack(fill="both", expand=True)
        
        Label(main_frame, text=f"📦 Dummy Supplier Quote Entry", font=("Segoe UI", 12, "bold"), fg="#1A365D", bg="#EBF8FF").pack(anchor="w", pady=(0, 5))
        Label(main_frame, text=f"Part Number: {part_number}", font=("Segoe UI", 9, "bold"), fg="#4A5568", bg="#EBF8FF").pack(anchor="w", pady=(0, 15))
        
        form_frame = Frame(main_frame, bg="#EBF8FF")
        form_frame.pack(fill="x", pady=5)
        
        Label(form_frame, text="Supplier Name:", font=("Segoe UI", 10), bg="#EBF8FF", fg="#1A365D").grid(row=0, column=0, sticky="w", pady=6)
        self.ent_supplier = Entry(form_frame, font=("Segoe UI", 10), width=28)
        self.ent_supplier.insert(0, "Dummy Supplier")
        self.ent_supplier.grid(row=0, column=1, sticky="w", padx=10, pady=6)
        
        Label(form_frame, text="Unit Price ($):", font=("Segoe UI", 10, "bold"), bg="#EBF8FF", fg="#1A365D").grid(row=1, column=0, sticky="w", pady=6)
        self.ent_price = Entry(form_frame, font=("Segoe UI", 10, "bold"), width=15)
        self.ent_price.grid(row=1, column=1, sticky="w", padx=10, pady=6)
        self.ent_price.focus_set()
        
        Label(form_frame, text="MOQ (Qty):", font=("Segoe UI", 10), bg="#EBF8FF", fg="#1A365D").grid(row=2, column=0, sticky="w", pady=6)
        self.ent_moq = Entry(form_frame, font=("Segoe UI", 10), width=15)
        self.ent_moq.insert(0, str(initial_moq))
        self.ent_moq.grid(row=2, column=1, sticky="w", padx=10, pady=6)
        
        Label(form_frame, text="Lead Time (weeks):", font=("Segoe UI", 10), bg="#EBF8FF", fg="#1A365D").grid(row=3, column=0, sticky="w", pady=6)
        self.ent_lt = Entry(form_frame, font=("Segoe UI", 10), width=15)
        self.ent_lt.insert(0, "2")
        self.ent_lt.grid(row=3, column=1, sticky="w", padx=10, pady=6)

        btn_frame = Frame(main_frame, bg="#EBF8FF")
        btn_frame.pack(fill="x", side="bottom", pady=(15, 0))
        
        btn_cancel = Button(btn_frame, text="Cancel", command=self.on_cancel, bg="#E2E8F0", fg="#2D3748", font=("Segoe UI", 10), bd=0, relief="flat", cursor="hand2", padx=15, pady=4)
        btn_cancel.pack(side="left")
        
        btn_confirm = Button(btn_frame, text="Apply Quote", command=self.on_confirm, bg="#2EAD4E", fg="white", font=("Segoe UI", 10, "bold"), bd=0, relief="flat", cursor="hand2", padx=15, pady=4)
        btn_confirm.pack(side="right")
        
        self.ent_price.bind("<Return>", lambda e: self.on_confirm())
        self.ent_supplier.bind("<Return>", lambda e: self.on_confirm())

        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
        except:
            pass
            
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def on_cancel(self):
        self.result = None
        self.destroy()

    def on_confirm(self):
        from utils import show_error
        supplier = self.ent_supplier.get().strip() or "Dummy Supplier"
        price_str = self.ent_price.get().strip()
        moq_str = self.ent_moq.get().strip()
        lt_str = self.ent_lt.get().strip() or "2"
        
        try:
            unit_price = float(price_str)
            if unit_price < 0: raise ValueError()
        except ValueError:
            show_error("Invalid Unit Price", "Unit Price must be a non-negative number.", parent=self)
            return
            
        try:
            moq = int(float(moq_str))
            if moq <= 0: raise ValueError()
        except ValueError:
            show_error("Invalid MOQ", "MOQ must be a positive integer.", parent=self)
            return

        self.result = {
            "supplier": supplier,
            "unit_price": unit_price,
            "moq": moq,
            "lead_time": lt_str
        }
        self.destroy()


