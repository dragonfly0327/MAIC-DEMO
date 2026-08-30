import os
import json
import tkinter as tk
from tkinter.ttk import Combobox, Treeview, Scrollbar as TtkScrollbar
from utils import CURRENCY_CONFIG_FILE, show_info, show_error, messagebox
from dialogs import style_premium_button, apply_panel_theme

class BOMTargetPriceWizardDialog(tk.Toplevel):
    def __init__(self, parent, cust_name, rfq_num, filepath, raw_data, read_only=False, show_previous=False):
        super().__init__(parent)
        self.read_only = read_only
        self.show_previous = show_previous
        self.result = None
        self.title("Input BOM Target Price & EAU")
        self.geometry("1100x600")
        self.resizable(True, True)
        self.grab_set()

        self.cust_name = cust_name
        self.rfq_num = rfq_num
        self.filepath = filepath
        self.raw_data = raw_data

        # Load currency options and rates
        self.currencies, self.currency_rates = self._load_currencies_and_rates()

        # Parse existing target settings from BOM data
        self.target_currency = raw_data.get("Target Currency", "USD")
        if self.target_currency not in self.currencies:
            self.currencies.append(self.target_currency)
            self.currencies = sorted(list(set(self.currencies)))

        self.target_markdown_pct = float(raw_data.get("Target Markdown %", 20.0))

        # Internal state to track edits: {assy_num: {moq: value_str}}
        self.edited_target_prices = {}
        self.original_target_prices = {}
        self.edited_eau = {}
        self.original_eau = {}
        self.global_eau_var = tk.BooleanVar(value=True)
        self._load_existing_target_prices()

        # Create status images for the treeview
        self._create_status_images()

        self.selected_assembly = None
        self.grid_entries = {}  # moq -> Entry widget
        self.grid_calcs = {}    # moq -> (StringVar, Label, Label)

        self._create_widgets()
        self._center_on_master()
        apply_panel_theme(self)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Select first assembly automatically
        self._select_first_assembly()

    def _center_on_master(self):
        self.update_idletasks()
        master = self.master
        if master and master.winfo_viewable():
            x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
            y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")

    def _load_currencies_and_rates(self):
        currencies = ["USD"]
        rates = {"USD": 1.0}
        from utils import SERVER_PATH
        sourcing_app_data = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(SERVER_PATH)), "Sourcing", "AppData"))
        sourcing_currency_path = os.path.normpath(os.path.join(sourcing_app_data, "Master Data", "Currency Config.json"))
        
        if os.path.exists(sourcing_currency_path):
            try:
                with open(sourcing_currency_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                curr_data = data.get("currencies", {})
                for c, c_cfg in curr_data.items():
                    c_upper = c.upper()
                    currencies.append(c_upper)
                    try:
                        rates[c_upper] = float(c_cfg.get("rate", 1.0))
                    except:
                        rates[c_upper] = 1.0
            except Exception as e:
                print(f"Error loading Sourcing currency config: {e}")
        else:
            if os.path.exists(CURRENCY_CONFIG_FILE):
                try:
                    with open(CURRENCY_CONFIG_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    curr_data = data.get("currencies", {})
                    for c, c_cfg in curr_data.items():
                        c_upper = c.upper()
                        currencies.append(c_upper)
                        try:
                            rates[c_upper] = float(c_cfg.get("rate", 1.0))
                        except:
                            rates[c_upper] = 1.0
                except Exception as e:
                    print(f"Error loading fallback currency config: {e}")
        currencies = sorted(list(set(currencies)))
        return currencies, rates

    def _load_existing_target_prices(self):
        for assy in self.raw_data.get("Assemblies", []):
            assy_num = assy.get("Assy #")
            if assy_num:
                self.edited_target_prices[assy_num] = {}
                self.original_target_prices[assy_num] = {}
                
                # Load EAU as dict or legacy number
                self.edited_eau[assy_num] = {}
                self.original_eau[assy_num] = {}
                
                eau_raw = assy.get("EAU")
                if isinstance(eau_raw, dict):
                    for mq, ev in eau_raw.items():
                        self.edited_eau[assy_num][str(mq)] = str(ev) if ev is not None else ""
                        self.original_eau[assy_num][str(mq)] = str(ev) if ev is not None else ""
                elif eau_raw is not None and str(eau_raw).strip():
                    # Legacy fallback: copy to all assigned MOQs
                    moqs = assy.get("Assigned MOQs", [])
                    for mq in moqs:
                        self.edited_eau[assy_num][str(mq)] = str(eau_raw)
                        self.original_eau[assy_num][str(mq)] = str(eau_raw)
                
                tgt_prices = assy.get("Target Prices", {})
                for moq, val in tgt_prices.items():
                    if val is not None:
                        val_str = f"{float(val):.2f}"
                        self.edited_target_prices[assy_num][str(moq)] = val_str
                        self.original_target_prices[assy_num][str(moq)] = val_str

    def _create_widgets(self):
        # Header Info Panel
        info_frame = tk.Frame(self, bg="#dcedf5", relief="ridge", borderwidth=1)
        info_frame.pack(fill="x", padx=15, pady=(15, 10))

        tk.Label(info_frame, text="RFQ:", font=('Segoe UI', 10, 'bold'), bg="#dcedf5", fg="#1A365D").pack(side="left", padx=(15, 2), pady=8)
        tk.Label(info_frame, text=f"{self.rfq_num}", font=('Segoe UI', 10, 'bold'), bg="#dcedf5", fg="#cc0000").pack(side="left", padx=(0, 15), pady=8)
        tk.Label(info_frame, text="Customer:", font=('Segoe UI', 10, 'bold'), bg="#dcedf5", fg="#1A365D").pack(side="left", padx=(0, 2), pady=8)
        tk.Label(info_frame, text=f"{self.cust_name}", font=('Segoe UI', 10), bg="#dcedf5", fg="#1A365D").pack(side="left", padx=(0, 15), pady=8)

        from utils import get_bom_creation_date
        raw = getattr(self, 'raw_data', {})
        fp = getattr(self, 'filepath', None)
        created_at = get_bom_creation_date(raw, fp)
        proj_title = raw.get("description", "") or raw.get("project_title", "") or raw.get("email_subject", "")
        tk.Label(info_frame, text="Project / Email Subject:", font=('Segoe UI', 10, 'bold'), bg="#dcedf5", fg="#1A365D").pack(side="left", padx=(0, 2), pady=8)
        tk.Label(info_frame, text=f"{proj_title or '-'}", font=('Segoe UI', 10), bg="#dcedf5", fg="#1A365D").pack(side="left", padx=(0, 15), pady=8)
        tk.Label(info_frame, text="BOM Created:", font=('Segoe UI', 10, 'bold'), bg="#dcedf5", fg="#1A365D").pack(side="left", padx=(0, 2), pady=8)
        tk.Label(info_frame, text=f"{created_at}", font=('Segoe UI', 10), bg="#dcedf5", fg="#1A365D").pack(side="left", padx=(0, 15), pady=8)

        # Currency and Markdown Config
        config_frame = tk.Frame(self)
        config_frame.pack(fill="x", padx=15, pady=(0, 10))

        tk.Label(config_frame, text="Target Price Currency:", font=('Segoe UI', 9, 'bold')).pack(side="left", padx=(5, 5))
        self.currency_var = tk.StringVar(value=self.target_currency)
        self.currency_combo = Combobox(config_frame, textvariable=self.currency_var, values=self.currencies, state="disabled" if self.read_only else "readonly", width=10)
        self.currency_combo.pack(side="left", padx=5)
        if not self.read_only:
            self.currency_combo.bind("<<ComboboxSelected>>", self._on_currency_changed)

        tk.Label(config_frame, text="Markdown Parameter (%):", font=('Segoe UI', 9, 'bold')).pack(side="left", padx=(25, 5))
        self.markdown_var = tk.StringVar(value=f"{self.target_markdown_pct:.1f}")
        self.markdown_entry = tk.Entry(config_frame, textvariable=self.markdown_var, width=8, font=('Segoe UI', 9), state="disabled" if self.read_only else "normal")
        self.markdown_entry.pack(side="left", padx=5)
        if not self.read_only:
            self.markdown_var.trace_add("write", self._on_markdown_changed)

        self.global_eau_chk = tk.Checkbutton(config_frame, text="Apply EAU globally to all MOQs", variable=self.global_eau_var, font=('Segoe UI', 9, 'bold'), state="disabled" if self.read_only else "normal")
        self.global_eau_chk.pack(side="left", padx=(25, 5))

        # Bottom Buttons (Pack first so they stay docked at the bottom and remain visible)
        btn_frame = tk.Frame(self, pady=15)
        btn_frame.pack(fill="x", side="bottom", padx=15)

        cancel_text = "Close" if self.read_only else "Cancel"
        cancel_btn = tk.Button(btn_frame, text=cancel_text, command=self._on_cancel, width=15, bg="#1A365D", fg="white", font=("Segoe UI", 10, "bold"), bd=0, relief="flat", cursor="hand2", pady=6)
        cancel_btn.pack(side="left", padx=5)

        if self.read_only and self.show_previous:
            prev_btn = tk.Button(btn_frame, text="◄ Previous", command=self._on_previous, width=15, bg="#1A365D", fg="white", font=("Segoe UI", 10, "bold"), bd=0, relief="flat", cursor="hand2", pady=6)
            prev_btn.pack(side="left", padx=5)

        if not self.read_only:
            save_btn = tk.Button(btn_frame, text="💾 Confirm", command=self._on_save, width=18, bg="#2ead4e", fg="white", font=("Segoe UI", 10, "bold"), bd=0, relief="flat", cursor="hand2", pady=6)
            save_btn.pack(side="right", padx=5)
        else:
            save_btn = tk.Button(btn_frame, text="Finish ➔", command=self._on_finish, width=15, bg="#2ead4e", fg="white", font=("Segoe UI", 10, "bold"), bd=0, relief="flat", cursor="hand2", pady=6)
            save_btn.pack(side="right", padx=5)

        history_btn = tk.Button(btn_frame, text="View History", command=self._show_history, width=15, bg="#1A365D", fg="white", font=("Segoe UI", 10, "bold"), bd=0, relief="flat", cursor="hand2", pady=6)
        history_btn.pack(side="right", padx=5)

        style_premium_button(cancel_btn)
        style_premium_button(save_btn)
        style_premium_button(history_btn)

        # Split Body Frame (Pack second with expand=True)
        body_frame = tk.Frame(self)
        body_frame.pack(fill="both", expand=True, padx=15, pady=5)

        # Left Panel - Assemblies List
        left_frame = tk.LabelFrame(body_frame, text="Assemblies", padx=5, pady=5, width=390)
        left_frame.pack_propagate(False)
        left_frame.pack(side="left", fill="both", expand=False)

        # Legend Frame at the bottom of the Left frame (with wrapped shorter descriptions)
        legend_frame = tk.Frame(left_frame, pady=5)
        legend_frame.pack(fill="x", side="bottom")

        tk.Label(legend_frame, text="Status Bullets: [Left = TP | Right = EAU]", font=('Segoe UI', 8, 'bold'), fg="#1A365D").pack(anchor="w", padx=5, pady=(0, 2))
        tk.Label(legend_frame, text="● Green: All MOQs maintained", font=('Segoe UI', 8), fg="#2E7D32", wraplength=280, justify="left").pack(anchor="w", padx=10)
        tk.Label(legend_frame, text="● Yellow: Partially maintained", font=('Segoe UI', 8), fg="#E65100", wraplength=280, justify="left").pack(anchor="w", padx=10)
        tk.Label(legend_frame, text="● Red: Not maintained yet", font=('Segoe UI', 8), fg="#C62828", wraplength=280, justify="left").pack(anchor="w", padx=10)

        # Container Frame to host the Treeview and its horizontal & vertical scrollbars using grid
        tree_container = tk.Frame(left_frame)
        tree_container.pack(fill="both", expand=True)

        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        self.assy_tree = Treeview(tree_container, columns=("AssyNo", "Model", "Rev"), show="tree headings", selectmode="browse")
        self.assy_tree.heading("#0", text="TP | EAU Status")
        self.assy_tree.heading("AssyNo", text="Assy No")
        self.assy_tree.heading("Model", text="Model")
        self.assy_tree.heading("Rev", text="Rev")

        self.assy_tree.column("#0", width=105, anchor="center")
        self.assy_tree.column("AssyNo", width=100, anchor="w")
        self.assy_tree.column("Model", width=110, anchor="w")
        self.assy_tree.column("Rev", width=45, anchor="center")
        self.assy_tree.grid(row=0, column=0, sticky="nsew")

        # Vertical Scrollbar
        y_scroll = TtkScrollbar(tree_container, orient="vertical", command=self.assy_tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")

        # Horizontal Scrollbar
        x_scroll = TtkScrollbar(tree_container, orient="horizontal", command=self.assy_tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")

        self.assy_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.assy_tree.bind("<<TreeviewSelect>>", self._on_assembly_selected)

        # Populate Left Treeview
        for assy in self.raw_data.get("Assemblies", []):
            assy_num = assy.get("Assy #")
            if assy_num:
                img = self.get_dual_status_image(assy_num)
                self.assy_tree.insert("", "end", iid=assy_num, image=img, values=(assy_num, assy.get("Assy Model", ""), assy.get("Assy Rev", "")))

        # Right Panel - Target Price & EAU Input Grid
        self.right_frame = tk.LabelFrame(body_frame, text="Target Price & EAU Grid", padx=10, pady=10)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

    def _select_first_assembly(self):
        children = self.assy_tree.get_children()
        if children:
            self.assy_tree.selection_set(children[0])

    def _on_currency_changed(self, event=None):
        self._save_active_entries_to_state()
        old_curr = self.target_currency
        new_curr = self.currency_var.get()
        if old_curr == new_curr:
            return

        rate_old = self.currency_rates.get(old_curr, 1.0)
        rate_new = self.currency_rates.get(new_curr, 1.0)

        # Convert all target prices
        for assy_num in self.edited_target_prices:
            for moq in self.edited_target_prices[assy_num]:
                val_str = self.edited_target_prices[assy_num][moq]
                if val_str:
                    try:
                        old_val = float(val_str)
                        usd_val = old_val / rate_old if rate_old > 0 else old_val
                        new_val = usd_val * rate_new
                        self.edited_target_prices[assy_num][moq] = f"{new_val:.2f}"
                    except ValueError:
                        pass

        for assy_num in self.original_target_prices:
            for moq in self.original_target_prices[assy_num]:
                val_str = self.original_target_prices[assy_num][moq]
                if val_str:
                    try:
                        old_val = float(val_str)
                        usd_val = old_val / rate_old if rate_old > 0 else old_val
                        new_val = usd_val * rate_new
                        self.original_target_prices[assy_num][moq] = f"{new_val:.2f}"
                    except ValueError:
                        pass

        self.target_currency = new_curr

        if hasattr(self, 'grid_header_label') and self.grid_header_label.winfo_exists():
            self.grid_header_label.config(text=f"Customer Target Price ({new_curr})")

        if self.selected_assembly:
            self._render_grid_for_assembly(self.selected_assembly)

    def _on_markdown_changed(self, *args):
        if hasattr(self, 'grid_calcs'):
            for moq_str, (val_var, lbl_std_tp, lbl_src_tp) in self.grid_calcs.items():
                self._update_calculated_columns(val_var.get(), lbl_std_tp, lbl_src_tp)

    def _update_calculated_columns(self, val_str, lbl_std_tp, lbl_src_tp):
        t_curr = self.currency_var.get()
        rate = self.currency_rates.get(t_curr, 1.0)
        
        try:
            markdown_pct = float(self.markdown_var.get().strip())
        except ValueError:
            markdown_pct = 0.0

        try:
            val_str = val_str.strip()
            if val_str:
                val = float(val_str)
                if val >= 0:
                    usd_val = val / rate if rate > 0 else val
                    sourcing_val = usd_val * (1.0 - markdown_pct / 100.0)
                    lbl_std_tp.config(text=f"{usd_val:.2f}")
                    lbl_src_tp.config(text=f"{sourcing_val:.2f}")
                    return
        except ValueError:
            pass
        lbl_std_tp.config(text="-")
        lbl_src_tp.config(text="-")

    def _on_assembly_selected(self, event):
        # 1. Save current active entries to memory
        self._save_active_entries_to_state()

        # 2. Get newly selected assembly
        selected = self.assy_tree.selection()
        if not selected:
            self.selected_assembly = None
            self._clear_right_grid()
            return

        self.selected_assembly = selected[0]
        self.right_frame.config(text=f"Target Price & EAU Grid for Assembly: {self.selected_assembly}")

        # 3. Render grid for the selected assembly
        self._render_grid_for_assembly(self.selected_assembly)

    def _clear_right_grid(self):
        for widget in self.right_frame.winfo_children():
            widget.destroy()
        self.grid_entries.clear()
        self.grid_calcs.clear()

    def _render_grid_for_assembly(self, assy_num):
        self._clear_right_grid()

        # Find the assembly in raw_data to get assigned MOQs
        assy_record = next((a for a in self.raw_data.get("Assemblies", []) if a.get("Assy #") == assy_num), None)
        if not assy_record:
            tk.Label(self.right_frame, text="Assembly not found.", fg="red").pack()
            return

        assigned_moqs = assy_record.get("Assigned MOQs", [])
        if not assigned_moqs:
            tk.Label(self.right_frame, text="No MOQs assigned to this assembly.\nPlease assign MOQs first.", fg="orange", font=('Segoe UI', 10, 'bold')).pack(pady=20)
            return

        # Header titles
        grid_container = tk.Frame(self.right_frame)
        grid_container.pack(fill="x", pady=10)

        tk.Label(grid_container, text="Assigned MOQ", font=('Segoe UI', 10, 'bold'), width=12, anchor="w").grid(row=0, column=0, padx=5, pady=5)
        self.grid_header_label = tk.Label(grid_container, text=f"Customer Target Price ({self.currency_var.get()})", font=('Segoe UI', 10, 'bold'), width=25, anchor="w")
        self.grid_header_label.grid(row=0, column=1, padx=5, pady=5)
        tk.Label(grid_container, text="Annual Usage (EAU)", font=('Segoe UI', 10, 'bold'), width=18, anchor="w").grid(row=0, column=2, padx=5, pady=5)
        tk.Label(grid_container, text="Standardized TP (USD)", font=('Segoe UI', 10, 'bold'), width=20, anchor="w").grid(row=0, column=3, padx=5, pady=5)
        tk.Label(grid_container, text="Sourcing TP (USD)", font=('Segoe UI', 10, 'bold'), width=18, anchor="w").grid(row=0, column=4, padx=5, pady=5)

        self.grid_eau_vars = {}
        self.grid_eau_entries = {}
        
        # Determine if EAU is uniform across MOQs
        is_global = True
        eau_vals = [self.edited_eau.get(assy_num, {}).get(str(mq), "") for mq in assigned_moqs]
        if len(set(eau_vals)) > 1:
            is_global = False
        self.global_eau_var.set(is_global)

        # Draw rows for each MOQ
        ordered_entries = []
        grid_rows_entries = []
        for idx, moq in enumerate(assigned_moqs, start=1):
            moq_str = str(moq)
            tk.Label(grid_container, text=moq_str, font=('Segoe UI', 10), width=12, anchor="w").grid(row=idx, column=0, padx=5, pady=5)

            val_var = tk.StringVar()
            # Fetch from self.edited_target_prices if present
            existing_val = self.edited_target_prices.get(assy_num, {}).get(moq_str, "")
            val_var.set(existing_val)

            entry = tk.Entry(grid_container, textvariable=val_var, font=('Segoe UI', 10), width=18, state="disabled" if self.read_only else "normal")
            entry.grid(row=idx, column=1, padx=5, pady=5, sticky="w")
            self.grid_entries[moq_str] = entry
            ordered_entries.append(entry)

            eau_var = tk.StringVar()
            eau_var.set(self.edited_eau.get(assy_num, {}).get(moq_str, ""))
            self.grid_eau_vars[moq_str] = eau_var

            entry_eau = tk.Entry(grid_container, textvariable=eau_var, font=('Segoe UI', 10), width=15, justify="center", state="disabled" if self.read_only else "normal")
            entry_eau.grid(row=idx, column=2, padx=5, pady=5, sticky="w")
            self.grid_eau_entries[moq_str] = entry_eau
            grid_rows_entries.append((entry, entry_eau))

            def make_eau_handler(m=moq_str, ev=eau_var):
                def handler(*args):
                    val = ev.get().strip()
                    if assy_num not in self.edited_eau:
                        self.edited_eau[assy_num] = {}
                    self.edited_eau[assy_num][m] = val
                    
                    if self.global_eau_var.get():
                        for other_moq, other_var in self.grid_eau_vars.items():
                            if other_moq != m and other_var.get().strip() != val:
                                other_var.set(val)
                                self.edited_eau[assy_num][other_moq] = val
                return handler
                
            eau_var.trace_add("write", make_eau_handler())

            lbl_std_tp = tk.Label(grid_container, text="-", font=('Segoe UI', 10), width=20, anchor="w")
            lbl_std_tp.grid(row=idx, column=3, padx=5, pady=5, sticky="w")
            
            lbl_src_tp = tk.Label(grid_container, text="-", font=('Segoe UI', 10), width=18, anchor="w")
            lbl_src_tp.grid(row=idx, column=4, padx=5, pady=5, sticky="w")

            self.grid_calcs[moq_str] = (val_var, lbl_std_tp, lbl_src_tp)

            # Create live updater closure (run instantly on keystroke for calculated columns)
            def make_updater(v=val_var, lst=lbl_std_tp, lsr=lbl_src_tp):
                def updater(*args):
                    val_str = v.get().strip()
                    self._update_calculated_columns(val_str, lst, lsr)
                return updater
                
            updater_fn = make_updater()
            val_var.trace_add("write", updater_fn)
            updater_fn()  # Initial calculation
            
            # Sync target price to memory and update tree status bullets ONLY on FocusOut to prevent typing delay
            def make_focus_out_handler(moq_val=moq_str, v=val_var):
                def handler(event):
                    val_str = v.get().strip()
                    if val_str:
                        try:
                            formatted_val = f"{float(val_str):.2f}"
                            v.set(formatted_val)
                            val_str = formatted_val
                        except ValueError:
                            pass
                    if self.selected_assembly:
                        if self.selected_assembly not in self.edited_target_prices:
                            self.edited_target_prices[self.selected_assembly] = {}
                        self.edited_target_prices[self.selected_assembly][moq_val] = val_str
                        self._update_tree_status_bullet(self.selected_assembly)
                return handler
                
            entry.bind("<FocusOut>", make_focus_out_handler())
            
            # Sync EAU status bullet on FocusOut as well
            def make_eau_focus_out_handler():
                def handler(event):
                    if self.selected_assembly:
                        self._update_tree_status_bullet(self.selected_assembly)
                return handler
            entry_eau.bind("<FocusOut>", make_eau_focus_out_handler())

        # Key bindings for Arrow Key / Enter navigation in 2D Grid
        H = len(grid_rows_entries)
        W = 2 # Col 0 = Target Price, Col 1 = EAU
        
        # Helper to highlight value on focus
        def highlight_all(widget):
            widget.after(10, lambda: widget.selection_range(0, tk.END))

        def make_navigator(curr_r, curr_c):
            def navigate(event):
                keysym = event.keysym
                next_r, next_c = curr_r, curr_c
                if keysym == "Up":
                    if curr_r > 0:
                        next_r = curr_r - 1
                elif keysym == "Down" or keysym == "Return":
                    if curr_r < H - 1:
                        next_r = curr_r + 1
                elif keysym == "Left":
                    if curr_c > 0:
                        next_c = curr_c - 1
                elif keysym == "Right":
                    if curr_c < W - 1:
                        next_c = curr_c + 1
                
                if next_r != curr_r or next_c != curr_c:
                    next_widget = grid_rows_entries[next_r][next_c]
                    next_widget.focus_set()
                    highlight_all(next_widget)
                    return "break"
            return navigate

        for r in range(H):
            for c in range(W):
                widget = grid_rows_entries[r][c]
                # Bind focus highlight
                widget.bind("<FocusIn>", lambda e: highlight_all(e.widget))
                # Bind navigation
                widget.bind("<Up>", make_navigator(r, c))
                widget.bind("<Down>", make_navigator(r, c))
                widget.bind("<Left>", make_navigator(r, c))
                widget.bind("<Right>", make_navigator(r, c))
                widget.bind("<Return>", make_navigator(r, c))

        # Apply theme to the newly created grid widgets
        apply_panel_theme(self.right_frame)

    def _save_active_entries_to_state(self):
        if not self.selected_assembly:
            return

        if self.selected_assembly not in self.edited_target_prices:
            self.edited_target_prices[self.selected_assembly] = {}

        for moq, entry in self.grid_entries.items():
            val = entry.get().strip()
            self.edited_target_prices[self.selected_assembly][moq] = val

    def _on_cancel(self):
        if getattr(self, 'read_only', False):
            self.result = "CANCEL"
            self.destroy()
            return
        if messagebox.askyesno("Cancel Changes", "Are you sure you want to discard your target price edits?", parent=self):
            self.result = "CANCEL"
            self.destroy()

    def _on_previous(self):
        self.result = "PREVIOUS"
        self.destroy()

    def _on_finish(self):
        self.result = "FINISH"
        self.destroy()

    def _on_save(self):
        # Save active grid entries first
        self._save_active_entries_to_state()

        # Validate Markdown Parameter
        try:
            markdown_val = float(self.markdown_var.get().strip())
            if not (0 <= markdown_val <= 100):
                raise ValueError()
        except ValueError:
            show_error("Validation Error", "Markdown percentage must be a number between 0 and 100.", parent=self)
            return

        # Validate target prices
        for assy_num, moq_vals in self.edited_target_prices.items():
            for moq, val in moq_vals.items():
                if val:
                    try:
                        f_val = float(val)
                        if f_val < 0:
                            raise ValueError()
                    except ValueError:
                        show_error("Validation Error", f"Target price for Assembly {assy_num} MOQ {moq} must be a non-negative number.", parent=self)
                        return

        # Save to raw_data
        target_currency = self.currency_var.get()
        rate_t = self.currency_rates.get(target_currency, 1.0)

        self.raw_data["Target Currency"] = target_currency
        self.raw_data["Target Markdown %"] = markdown_val

        # Backlog changes tracking
        changed_log_entries = []

        for assy in self.raw_data.get("Assemblies", []):
            assy_num = assy.get("Assy #")
            if not assy_num:
                continue

            target_prices_dict = {}
            target_prices_usd_dict = {}

            assy_edits = self.edited_target_prices.get(assy_num, {})
            for moq, val_str in assy_edits.items():
                if val_str:
                    f_val = float(val_str)
                    target_prices_dict[moq] = f_val
                    target_prices_usd_dict[moq] = f_val / rate_t if rate_t > 0 else f_val
                else:
                    target_prices_dict[moq] = None
                    target_prices_usd_dict[moq] = None

            # Compare with original state for backlog logging
            original_edits = self.original_target_prices.get(assy_num, {})
            for moq, new_val in target_prices_dict.items():
                new_val_str = f"{new_val:.2f}" if new_val is not None else ""
                old_val_str = original_edits.get(moq, "")
                if new_val_str != old_val_str:
                    changed_log_entries.append({
                        "assy": assy_num,
                        "moq": moq,
                        "old": old_val_str or "None",
                        "new": new_val_str or "None"
                    })

            # Save EAU to BOM JSON (as a dictionary of moq -> value)
            eau_dict = {}
            assy_eau_edits = self.edited_eau.get(assy_num, {})
            for moq in assy.get("Assigned MOQs", []):
                moq_str = str(moq)
                eau_str = assy_eau_edits.get(moq_str, "").strip()
                if eau_str:
                    try:
                        eau_dict[moq_str] = int(float(eau_str))
                    except:
                        eau_dict[moq_str] = None
                else:
                    eau_dict[moq_str] = None
            assy["EAU"] = eau_dict

            # Compare EAU edits with original EAU for backlog logging
            original_eau_dict = self.original_eau.get(assy_num, {})
            for moq_str, new_eau in eau_dict.items():
                new_eau_str = str(new_eau) if new_eau is not None else ""
                old_eau_str = original_eau_dict.get(moq_str, "").strip()
                if new_eau_str != old_eau_str:
                    changed_log_entries.append({
                        "assy": assy_num,
                        "moq": moq_str,
                        "old_eau": old_eau_str or "None",
                        "new_eau": new_eau_str or "None"
                    })

            # Update BOM JSON assembly structure
            assy["Target Prices"] = target_prices_dict
            assy["Target Prices USD"] = target_prices_usd_dict

        # Append history entry for active user
        if "history" not in self.raw_data:
            self.raw_data["history"] = []
        from datetime import datetime
        now = datetime.now()
        self.raw_data["history"].append({
            "Date": now.strftime("%d.%m.%Y"),
            "Time": now.strftime("%H:%M:%S"),
            "Changed By": getattr(self, "user_name", getattr(self, "current_user", "Admin")),
            "stage": self.raw_data.get("status") or "pending_bom",
            "Field Name": "Target Price / EAU",
            "Old Value": "Previous Prices",
            "New Value": "Updated Target Prices"
        })
        self.raw_data["bom_assigned_by"] = getattr(self, "user_name", getattr(self, "current_user", "Admin"))

        # Save back to file
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(self.raw_data, f, indent=4)
        except Exception as e:
            show_error("Save Error", f"Failed to save target prices to JSON:\n{e}", parent=self)
            return

        # Centralized backlog logging
        if changed_log_entries:
            try:
                from backlog_api import log_backlog_event
                # Resolve active user
                username = "Unknown User"
                curr = self.master
                while curr:
                    if hasattr(curr, 'user_name') and curr.user_name:
                        username = curr.user_name
                        break
                    curr = getattr(curr, 'master', None)

                for change in changed_log_entries:
                    details = {
                        "customer": self.cust_name,
                        "rfq_number": self.rfq_num,
                        "assembly_number": change["assy"],
                        "moq": change["moq"],
                        "target_currency": target_currency,
                        "target_markdown_pct": markdown_val,
                        "source": "BOM Target Price Editor"
                    }
                    if "old" in change:
                        details["old_target_price"] = change["old"]
                        details["new_target_price"] = change["new"]
                    if "old_eau" in change:
                        details["old_eau"] = change["old_eau"]
                        details["new_eau"] = change["new_eau"]
                    log_backlog_event(
                        event_type="EDIT_BOM_TARGET_PRICE",
                        app_name="BOM App",
                        user_name=username,
                        details=details
                    )
            except Exception as e:
                print(f"Failed to record target price backlog events: {e}")

        show_info("Success", "Target Prices saved successfully!", parent=self.master)
        self.destroy()

    def get_assembly_status_bullet(self, assy_num):
        assy_record = next((a for a in self.raw_data.get("Assemblies", []) if a.get("Assy #") == assy_num), None)
        if not assy_record:
            return "🔴"
        assigned_moqs = assy_record.get("Assigned MOQs", [])
        if not assigned_moqs:
            return "🔴"
        
        prices = self.edited_target_prices.get(assy_num, {})
        filled_count = 0
        for moq in assigned_moqs:
            val = prices.get(str(moq), "").strip()
            try:
                if val and float(val) > 0.0:
                    filled_count += 1
            except ValueError:
                pass
                
        if filled_count == len(assigned_moqs):
            return "🟢"
        elif filled_count > 0:
            return "🟡"
        else:
            return "🔴"

    def get_eau_status_bullet(self, assy_num):
        assy_record = next((a for a in self.raw_data.get("Assemblies", []) if a.get("Assy #") == assy_num), None)
        if not assy_record:
            return "🔴"
        assigned_moqs = assy_record.get("Assigned MOQs", [])
        if not assigned_moqs:
            return "🔴"
        
        eau_edits = self.edited_eau.get(assy_num, {})
        filled_count = 0
        for moq in assigned_moqs:
            val = eau_edits.get(str(moq), "").strip()
            try:
                if val and float(val) > 0.0:
                    filled_count += 1
            except ValueError:
                pass
                
        if filled_count == len(assigned_moqs):
            return "🟢"
        elif filled_count > 0:
            return "🟡"
        else:
            return "🔴"

    def _update_tree_status_bullet(self, assy_num):
        if self.assy_tree.exists(assy_num):
            img = self.get_dual_status_image(assy_num)
            self.assy_tree.item(assy_num, image=img)

    def _create_status_images(self):
        color_map = {
            "🟢": "#2E7D32", # Green
            "🟡": "#E65100", # Yellow
            "🔴": "#C62828"  # Red
        }
        self.status_images = {}
        for tp_b, tp_hex in color_map.items():
            for eau_b, eau_hex in color_map.items():
                img = tk.PhotoImage(width=34, height=16)
                for y in range(16):
                    for x in range(34):
                        dx1 = x - 7
                        dy1 = y - 7
                        dx2 = x - 25
                        dy2 = y - 7
                        if dx1*dx1 + dy1*dy1 <= 16:
                            img.put(tp_hex, (x, y))
                        elif dx2*dx2 + dy2*dy2 <= 16:
                            img.put(eau_hex, (x, y))
                        else:
                            img.put("", (x, y))
                self.status_images[(tp_b, eau_b)] = img

    def get_dual_status_image(self, assy_num):
        tp_b = self.get_assembly_status_bullet(assy_num)
        eau_b = self.get_eau_status_bullet(assy_num)
        return self.status_images.get((tp_b, eau_b), self.status_images.get(("🔴", "🔴")))

    def _show_history(self):
        """Opens a premium dialog showing all target price & EAU change history for the selected assembly."""
        self.show_history_dialog()

    def show_history_dialog(self):
        """Shows log history of Target Price & EAU edits for current assembly."""
        if not self.selected_assembly:
            from utils import show_warning
            show_warning("No Selection", "Please select an assembly from the left panel first.", parent=self)
            return

        from datetime import datetime
        history_records = []
        try:
            from backlog_api import MASTER_BACKLOG_DIR
            import json
            jsonl_path = os.path.join(MASTER_BACKLOG_DIR, "master_backlog_events.jsonl")
            if os.path.exists(jsonl_path):
                with open(jsonl_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            evt = json.loads(line)
                            if evt.get("event_type") != "EDIT_BOM_TARGET_PRICE":
                                continue
                            d = evt.get("details", {})
                            if (d.get("rfq_number") == self.rfq_num and
                                    d.get("assembly_number") == self.selected_assembly):
                                ts = evt.get("timestamp", "")
                                try:
                                    dt_obj = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                                    date_str = dt_obj.strftime("%d.%m.%Y")
                                    time_str = dt_obj.strftime("%H:%M:%S")
                                except:
                                    date_str = ts
                                    time_str = ""
                                user = evt.get("user_name", "Unknown User")
                                app = evt.get("app_name", "")
                                moq = d.get("moq", "")
                                assy = d.get("assembly_number", "")
                                currency = d.get("target_currency", "USD")
                                
                                has_tp = "old_target_price" in d or "new_target_price" in d
                                has_eau = "old_eau" in d or "new_eau" in d
                                
                                if has_tp:
                                    old_val = d.get("old_target_price", "")
                                    new_val = d.get("new_target_price", "")
                                    history_records.append({
                                        "date": date_str,
                                        "time": time_str,
                                        "user": user,
                                        "app": app,
                                        "field": f"Assembly {assy} MOQ {moq} Target Price",
                                        "new": f"{new_val} {currency}" if new_val and new_val != "None" else "None",
                                        "old": f"{old_val} {currency}" if old_val and old_val != "None" else "None",
                                        "timestamp": ts
                                    })
                                if has_eau:
                                    old_eau = d.get("old_eau", "")
                                    new_eau = d.get("new_eau", "")
                                    history_records.append({
                                        "date": date_str,
                                        "time": time_str,
                                        "user": user,
                                        "app": app,
                                        "field": f"Assembly {assy} MOQ {moq} EAU",
                                        "new": new_eau if new_eau is not None else "None",
                                        "old": old_eau if old_eau is not None else "None",
                                        "timestamp": ts
                                    })
                        except Exception:
                            continue
        except Exception as e:
            print(f"[show_history_dialog] Could not read backlog: {e}")

        # Fallback / merge with raw_data history
        if hasattr(self, 'raw_data') and self.raw_data and isinstance(self.raw_data, dict):
            for h in self.raw_data.get("history", []):
                field_name = str(h.get("Field Name", ""))
                # Only include Target Price & EAU edits; exclude MOQ assignation edits
                if "Target Price" in field_name or "EAU" in field_name:
                    d_str = str(h.get("Date", "")).strip()
                    t_str = str(h.get("Time", "")).strip()
                    sort_ts = f"{d_str} {t_str}".strip()
                    try:
                        dt_obj = datetime.strptime(f"{d_str} {t_str}".strip(), "%d.%m.%Y %H:%M:%S")
                        sort_ts = dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        try:
                            dt_obj = datetime.strptime(d_str, "%d.%m.%Y")
                            sort_ts = dt_obj.strftime(f"%Y-%m-%d {t_str if t_str else '00:00:00'}")
                        except Exception:
                            pass
                    history_records.append({
                        "date": d_str,
                        "time": t_str,
                        "user": h.get("Changed By", "Unknown User"),
                        "app": "BOM App",
                        "field": field_name,
                        "new": str(h.get("New Value", "")),
                        "old": str(h.get("Old Value", "")),
                        "timestamp": sort_ts
                    })

        # Sort newest first
        history_records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)

        import textwrap
        from tkinter import ttk

        # --- Build premium dialog ---
        dialog = tk.Toplevel(self)
        dialog._skip_autofit = True
        dialog.title("Display Changes - Target Price & EAU")
        dialog.resizable(True, True)
        dialog.configure(bg="#EBF8FF")
        try:
            dialog.grab_set()
        except Exception:
            pass

        # Center on screen in normal/restored mode (1200x700)
        try:
            dialog.update_idletasks()
            sw = dialog.winfo_screenwidth()
            sh = dialog.winfo_screenheight()
            w, h = 1200, 700
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            dialog.geometry(f"{w}x{h}+{x}+{y}")
            dialog.minsize(900, 450)
        except Exception:
            dialog.geometry("1200x700")

        # Header banner
        banner = tk.Frame(dialog, bg="#dcedf5", pady=0)
        banner.pack(side="top", fill="x")
        tk.Label(
            banner,
            text="📋  Display Changes - Target Price & EAU",
            font=("Segoe UI", 14, "bold", "italic"),
            fg="#1A365D", bg="#dcedf5"
        ).pack(side="left", padx=15, pady=10)

        # Info row
        info_frame = tk.Frame(dialog, bg="#EBF8FF")
        info_frame.pack(side="top", fill="x", padx=15, pady=(8, 2))
        cust_str = getattr(self, 'cust_name', '')
        rfq_str = getattr(self, 'rfq_num', '')
        assy_str = getattr(self, 'selected_assembly', '')
        tk.Label(
            info_frame,
            text=f"Customer: {cust_str}   |   RFQ: {rfq_str}   |   Assembly: {assy_str}   |   Showing edits from both BOM App & Costing App",
            font=("Segoe UI", 10, "bold"),
            fg="#1A365D", bg="#EBF8FF"
        ).pack(anchor="w")

        # Warning note if empty
        if not history_records:
            note = tk.Frame(dialog, bg="#fff3cd", bd=1, relief="solid")
            note.pack(side="top", fill="x", padx=15, pady=(4, 0))
            tk.Label(
                note,
                text="⚠️  No target price or EAU change history found for this assembly.",
                font=("Segoe UI", 10),
                bg="#fff3cd", fg="#856404"
            ).pack(pady=8, padx=10)

        # Footer packed at BOTTOM FIRST to guarantee button visibility
        footer = tk.Frame(dialog, bg="#EBF8FF")
        footer.pack(side="bottom", fill="x", padx=15, pady=(4, 12))
        tk.Label(
            footer,
            text=f"Total records: {len(history_records)}   |   🔵 Blue = BOM App edit   |   🟢 Green = Costing App edit",
            font=("Segoe UI", 9),
            fg="#4a4a4a", bg="#EBF8FF"
        ).pack(side="left")
        
        close_btn = tk.Button(
            footer, text="Close",
            command=dialog.destroy,
            width=10,
            bg="#1A365D", fg="white",
            font=("Segoe UI", 10, "bold"),
            activebackground="#0077B6",
            relief="flat", bd=0, cursor="hand2"
        )
        close_btn.pack(side="right")

        # Configure treeview style with larger rowheight
        style = ttk.Style(dialog)
        style.configure("History.Treeview", font=("Segoe UI", 10), rowheight=38)
        style.configure("History.Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#dcedf5", foreground="#1A365D")
        style.map("History.Treeview", foreground=[("selected", "black")])

        # Treeview table fills remaining space above footer
        tree_frame = tk.Frame(dialog, bg="#EBF8FF")
        tree_frame.pack(side="top", fill="both", expand=True, padx=15, pady=(6, 5))

        cols = ("Date", "Time", "Changed By", "Field Name", "New Value", "Old Value")
        tree_widget = Treeview(tree_frame, columns=cols, show="headings", style="History.Treeview", selectmode="browse")

        col_widths = {
            "Date": 110,
            "Time": 90,
            "Changed By": 190,
            "Field Name": 350,
            "New Value": 220,
            "Old Value": 220
        }
        for col in cols:
            tree_widget.heading(col, text=col, anchor="w")
            tree_widget.column(col, width=col_widths.get(col, 150), minwidth=80, stretch=False, anchor="w")

        # Distinct app edit tags with background tints & text colors
        tree_widget.tag_configure("bom_odd",  background="#eff6ff", foreground="#1e40af")
        tree_widget.tag_configure("bom_even", background="#dbeafe", foreground="#1e3a8a")
        tree_widget.tag_configure("cost_odd", background="#f0fdf4", foreground="#166534")
        tree_widget.tag_configure("cost_even", background="#dcfce7", foreground="#14532d")
        tree_widget.tag_configure("separator", background="#dcdcdc")

        vsb = TtkScrollbar(tree_frame, orient="vertical",   command=tree_widget.yview)
        hsb = TtkScrollbar(tree_frame, orient="horizontal", command=tree_widget.xview)
        tree_widget.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree_widget.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        current_date = None
        for i, rec in enumerate(history_records):
            field_name = str(rec.get("field", ""))
            if "dispatch" in field_name.lower() or field_name == "Stage Dispatch":
                continue

            rec_date = rec.get("date", "")
            if current_date != rec_date:
                if current_date is not None:
                    tree_widget.insert("", "end", values=("", "", "", "", "", ""), tags=("separator",))
                current_date = rec_date

            app_text = str(rec.get("app", ""))
            user_text = str(rec.get("user", "Unknown"))
            if user_text in ("User", "Unknown User", "Unknown"):
                active_u = getattr(self, 'user_name', None) or getattr(self.master, 'user_name', None)
                if active_u:
                    user_text = active_u

            is_even = (i % 2 == 0)
            if "cost" in app_text.lower():
                user_label = f"🟢 {user_text} (Costing App)"
                row_tag = "cost_even" if is_even else "cost_odd"
            else:
                user_label = f"🔵 {user_text} (BOM App)"
                row_tag = "bom_even" if is_even else "bom_odd"

            field_wrapped = textwrap.fill(field_name, width=45)
            new_val_wrapped = textwrap.fill(str(rec.get("new", "")), width=30)
            old_val_wrapped = textwrap.fill(str(rec.get("old", "")), width=30)

            tree_widget.insert("", "end", tags=(row_tag,), values=(
                rec.get("date", ""),
                rec.get("time", ""),
                user_label,
                field_wrapped,
                new_val_wrapped,
                old_val_wrapped,
            ))

