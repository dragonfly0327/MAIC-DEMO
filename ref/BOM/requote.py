import os
import json
import tkinter as tk
from tkinter import messagebox
from tkinter.ttk import Combobox, Treeview, Scrollbar as TtkScrollbar
import pandas as pd
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor

from utils import BOM_DATA_DIR, STANDARD_COLUMNS, show_info, show_error
from dialogs import style_premium_button, apply_panel_theme

class RequoteWizardDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("BOM Requote Wizard - Mix & Match Assemblies")
        self.geometry("1100x730")
        self.grab_set()
        
        self.result = None
        self.bom_records = []
        self.filtered_records = []
        self.current_page = 0
        self.page_size = 20
        
        self._create_widgets()
        self._center_on_master()
        
        # Apply standard styles
        apply_panel_theme(self)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Run concurrent multithreaded database loader
        self._load_database_records()
        
    def _center_on_master(self):
        self.update_idletasks()
        master = self.master
        if master and master.winfo_viewable():
            x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
            y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{x}+{y}")
            
    def _load_database_records(self):
        if not os.path.exists(BOM_DATA_DIR):
            self.status_bar.config(text="Database directory not found.")
            return
            
        def run_loader():
            json_files = []
            for root_dir, dirs, files in os.walk(BOM_DATA_DIR):
                for file in files:
                    if file.endswith('.json') and not file.endswith('metadata.json') and not file.endswith('assigned_moqs_metadata.json'):
                        filepath = os.path.join(root_dir, file)
                        json_files.append(filepath)
                        
            records = []
            def load_single_file(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    cust_name = data.get("Customer", "Unknown")
                    rfq_num = data.get("RFQ", "Unknown")
                    mtime = os.path.getmtime(filepath)
                    date_str = datetime.fromtimestamp(mtime).strftime("%d-%m-%Y %I:%M:%S %p")
                    return {
                        "Customer": cust_name,
                        "RFQ": rfq_num,
                        "Date": date_str,
                        "filepath": filepath,
                        "raw_data": data
                    }
                except Exception as e:
                    print(f"Error loading record {filepath}: {e}")
                    return None
            
            # Concurrently parse JSON files in parallel with dynamic workers
            max_workers = min(32, (os.cpu_count() or 1) + 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = executor.map(load_single_file, json_files)
                for res in results:
                    if res:
                        records.append(res)
                        
            # Sort records by Date descending
            try:
                records.sort(key=lambda x: datetime.strptime(x["Date"], "%d-%m-%Y %I:%M:%S %p"), reverse=True)
            except Exception as e:
                print(f"Error sorting records: {e}")
                
            self.bom_records = records
            self.after(0, self._on_loading_complete)
            
        threading.Thread(target=run_loader, daemon=True).start()

    def _on_loading_complete(self):
        # Update combo box values for target customer selection
        existing_customers = sorted(list(set(r["Customer"] for r in self.bom_records)))
        self.cb_cust.config(values=existing_customers)
        
        # Update search customer combo box values
        self.cb_search_cust.config(values=[""] + existing_customers)
        
        # Reset page and load
        self.current_page = 0
        self._filter_available_boms()
        
        # Update status bar
        self.status_bar.config(text=f"Database loaded concurrently. {len(self.bom_records)} verified BOM records found.")

    def _create_widgets(self):
        # Main Frame with margins
        main_frame = tk.Frame(self, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)
        
        # Header block
        header_frame = tk.Frame(main_frame, bg="#eef2f7", bd=1, relief="solid")
        header_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(
            header_frame, 
            text="🔄 BOM REQUOTE WIZARD", 
            font=("Arial", 14, "bold"), 
            fg="#1A365D", 
            bg="#eef2f7"
        ).pack(pady=10)
        
        # Target RFQ Info Frame (Top section)
        info_frame = tk.LabelFrame(main_frame, text="Requote Target Information (New RFQ Details)", font=("Arial", 10, "bold"), fg="#1A365D", padx=15, pady=10)
        info_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(info_frame, text="Customer Name:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=5)
        self.cust_var = tk.StringVar()
        self.cb_cust = Combobox(info_frame, textvariable=self.cust_var, width=30)
        self.cb_cust.grid(row=0, column=1, sticky="w", padx=10, pady=5)
        
        tk.Label(info_frame, text="New RFQ Number:", font=("Arial", 10, "bold")).grid(row=0, column=2, sticky="w", pady=5, padx=(20, 0))
        self.rfq_var = tk.StringVar()
        self.ent_rfq = tk.Entry(info_frame, textvariable=self.rfq_var, width=25)
        self.ent_rfq.grid(row=0, column=3, sticky="w", padx=10, pady=5)
        
        tk.Label(info_frame, text="New Project Title:", font=("Arial", 10, "bold")).grid(row=0, column=4, sticky="w", pady=5, padx=(20, 0))
        self.email_var = tk.StringVar()
        self.ent_email = tk.Entry(info_frame, textvariable=self.email_var, width=35)
        self.ent_email.grid(row=0, column=5, sticky="w", padx=10, pady=5)
        
        # Define and pack Bottom elements first so they anchor correctly at the bottom
        # Status Bar at bottom
        self.status_bar = tk.Label(main_frame, text="Initializing...", font=("Arial", 10, "bold"), anchor="center", pady=5, bg="#eef2f7", fg="#1A365D")
        self.status_bar.pack(side="bottom", fill="x", pady=(10, 0))
        
        # Bottom Actions Frame
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.pack(side="bottom", fill="x", pady=(15, 0))
        
        self.btn_confirm = tk.Button(bottom_frame, text="✅ Confirm Requote", command=self._on_confirm, width=20)
        self.btn_confirm.pack(side="right", padx=5)
        style_premium_button(self.btn_confirm, bg_color="#2b6cb0", hover_bg="#1A365D")
        
        self.btn_cancel = tk.Button(bottom_frame, text="Cancel", command=self._on_cancel, width=12)
        self.btn_cancel.pack(side="right", padx=5)
        style_premium_button(self.btn_cancel, bg_color="#718096", hover_bg="#4a5568")
        
        # Paned Window or side-by-side frames for mixing/matching
        paned = tk.PanedWindow(main_frame, orient="horizontal", sashpad=4, sashwidth=4)
        paned.pack(fill="both", expand=True)
        
        # Left Panel: Source Selection
        left_panel = tk.Frame(paned)
        paned.add(left_panel)
        
        # Left Panel Search filters
        search_f = tk.LabelFrame(left_panel, text="Search Past BOMs", font=("Arial", 9, "bold"), fg="#1A365D", padx=5, pady=5)
        search_f.pack(fill="x", pady=(0, 10))
        
        tk.Label(search_f, text="Customer:").grid(row=0, column=0, sticky="w")
        self.search_cust_var = tk.StringVar()
        self.cb_search_cust = Combobox(search_f, textvariable=self.search_cust_var, width=15)
        self.cb_search_cust.grid(row=0, column=1, sticky="w", padx=5)
        
        tk.Label(search_f, text="RFQ:").grid(row=0, column=2, sticky="w", padx=(10, 0))
        self.search_rfq_var = tk.StringVar()
        ent_search_rfq = tk.Entry(search_f, textvariable=self.search_rfq_var, width=15)
        ent_search_rfq.grid(row=0, column=3, sticky="w", padx=5)
        
        # Setup search filters callbacks
        self.cb_search_cust.bind("<<ComboboxSelected>>", lambda e: self._filter_available_boms())
        self.cb_search_cust.bind("<KeyRelease>", lambda e: self._filter_available_boms())
        ent_search_rfq.bind("<KeyRelease>", lambda e: self._filter_available_boms())
        
        # Available BOMs Tree
        tk.Label(left_panel, text="1. Select Source BOM:", font=("Arial", 9, "bold"), fg="#1A365D").pack(anchor="w")
        
        boms_frame = tk.Frame(left_panel)
        boms_frame.pack(fill="both", expand=True, pady=(2, 5))
        
        cols = ("customer", "rfq", "date")
        self.boms_tree = Treeview(boms_frame, columns=cols, show="headings", height=8)
        self.boms_tree.heading("customer", text="Customer")
        self.boms_tree.heading("rfq", text="RFQ")
        self.boms_tree.heading("date", text="Date Verified")
        
        self.boms_tree.column("customer", width=120, anchor="w")
        self.boms_tree.column("rfq", width=100, anchor="center")
        self.boms_tree.column("date", width=140, anchor="center")
        
        self.boms_tree.pack(side="left", fill="both", expand=True)
        sb1 = TtkScrollbar(boms_frame, orient="vertical", command=self.boms_tree.yview)
        self.boms_tree.config(yscrollcommand=sb1.set)
        sb1.pack(side="right", fill="y")
        
        self.boms_tree.bind("<<TreeviewSelect>>", self._on_bom_select)
        
        # Pagination Controls for BOM selection
        pag_frame = tk.Frame(left_panel, bg="#EBF8FF", pady=5)
        pag_frame.pack(fill="x", pady=(2, 5))
        
        pag_center = tk.Frame(pag_frame, bg="#EBF8FF")
        pag_center.pack(anchor="center")
        
        self.btn_first = tk.Button(pag_center, text="|<", command=self.goto_first_page, width=4)
        self.btn_first.pack(side="left", padx=2)
        style_premium_button(self.btn_first, bg_color="#3182ce", hover_bg="#2b6cb0")
        
        self.btn_prev = tk.Button(pag_center, text="<", command=self.goto_prev_page, width=4)
        self.btn_prev.pack(side="left", padx=2)
        style_premium_button(self.btn_prev, bg_color="#3182ce", hover_bg="#2b6cb0")
        
        tk.Label(pag_center, text="Page:", font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#1A365D").pack(side="left", padx=(10, 2))
        self.ent_page_num = tk.Entry(pag_center, width=4, justify="center")
        self.ent_page_num.pack(side="left", padx=2)
        self.ent_page_num.bind("<Return>", self.on_page_num_entry)
        
        self.lbl_total_pages = tk.Label(pag_center, text="of 1", font=("Segoe UI", 9, "bold"), bg="#EBF8FF", fg="#1A365D")
        self.lbl_total_pages.pack(side="left", padx=(2, 10))
        
        self.btn_next = tk.Button(pag_center, text=">", command=self.goto_next_page, width=4)
        self.btn_next.pack(side="left", padx=2)
        style_premium_button(self.btn_next, bg_color="#3182ce", hover_bg="#2b6cb0")
        
        self.btn_last = tk.Button(pag_center, text=">|", command=self.goto_last_page, width=4)
        self.btn_last.pack(side="left", padx=2)
        style_premium_button(self.btn_last, bg_color="#3182ce", hover_bg="#2b6cb0")
        
        # Assemblies in selected BOM Tree Header with Search
        assy_header_f = tk.Frame(left_panel)
        assy_header_f.pack(fill="x", pady=(5, 0))
        
        tk.Label(assy_header_f, text="2. Select Assemblies in BOM:", font=("Arial", 9, "bold"), fg="#1A365D").pack(side="left")
        
        tk.Label(assy_header_f, text="Search Assy #:", font=("Arial", 9, "bold"), fg="#1A365D").pack(side="left", padx=(15, 2))
        self.search_assy_var = tk.StringVar()
        self.ent_search_assy = tk.Entry(assy_header_f, textvariable=self.search_assy_var, width=15)
        self.ent_search_assy.pack(side="left")
        self.search_assy_var.trace_add("write", self._filter_assemblies)
        
        assy_frame = tk.Frame(left_panel)
        assy_frame.pack(fill="both", expand=True, pady=(2, 0))
        
        assy_cols = ("assy_num", "model", "rev")
        self.assy_tree = Treeview(assy_frame, columns=assy_cols, show="headings", height=6)
        self.assy_tree.heading("assy_num", text="Assembly #")
        self.assy_tree.heading("model", text="Model")
        self.assy_tree.heading("rev", text="Revision")
        
        self.assy_tree.column("assy_num", width=120, anchor="w")
        self.assy_tree.column("model", width=140, anchor="w")
        self.assy_tree.column("rev", width=60, anchor="center")
        
        self.assy_tree.pack(side="left", fill="both", expand=True)
        sb2 = TtkScrollbar(assy_frame, orient="vertical", command=self.assy_tree.yview)
        self.assy_tree.config(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y")
        
        # Center Panel: Transfer buttons
        center_panel = tk.Frame(paned, padx=10)
        paned.add(center_panel)
        
        # Spacer
        tk.Label(center_panel, text="").pack(pady=40)
        self.btn_add = tk.Button(center_panel, text="➡️ Add Selected", command=self._on_add, width=15)
        self.btn_add.pack(pady=10)
        style_premium_button(self.btn_add, bg_color="#1A365D", hover_bg="#0077B6")
        
        self.btn_remove = tk.Button(center_panel, text="⬅️ Remove", command=self._on_remove, width=15)
        self.btn_remove.pack(pady=10)
        style_premium_button(self.btn_remove, bg_color="#d9534f", hover_bg="#c9302c")
        
        # Right Panel: Selection Summary
        right_panel = tk.Frame(paned)
        paned.add(right_panel)
        
        tk.Label(right_panel, text="3. Target Assembly Mix (Requote List):", font=("Arial", 9, "bold"), fg="#1A365D").pack(anchor="w")
        
        sel_frame = tk.Frame(right_panel)
        sel_frame.pack(fill="both", expand=True, pady=(2, 0))
        
        sel_cols = ("src_cust", "src_rfq", "assy_num", "model", "rev", "filepath", "rec_idx", "assy_idx")
        self.selected_tree = Treeview(sel_frame, columns=sel_cols, show="headings", height=15)
        self.selected_tree.heading("src_cust", text="Source Customer")
        self.selected_tree.heading("src_rfq", text="Source RFQ")
        self.selected_tree.heading("assy_num", text="Assembly #")
        self.selected_tree.heading("model", text="Model")
        self.selected_tree.heading("rev", text="Rev")
        
        # Hide internal helper columns
        self.selected_tree.column("src_cust", width=120, anchor="w")
        self.selected_tree.column("src_rfq", width=100, anchor="center")
        self.selected_tree.column("assy_num", width=120, anchor="w")
        self.selected_tree.column("model", width=120, anchor="w")
        self.selected_tree.column("rev", width=60, anchor="center")
        self.selected_tree["displaycolumns"] = ("src_cust", "src_rfq", "assy_num", "model", "rev")
        
        self.selected_tree.pack(side="left", fill="both", expand=True)
        sb3 = TtkScrollbar(sel_frame, orient="vertical", command=self.selected_tree.yview)
        self.selected_tree.config(yscrollcommand=sb3.set)
        sb3.pack(side="right", fill="y")

    def goto_first_page(self):
        self.current_page = 0
        self._update_page_view()

    def goto_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_page_view()

    def goto_next_page(self):
        total_pages = self._get_total_pages()
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._update_page_view()

    def goto_last_page(self):
        total_pages = self._get_total_pages()
        self.current_page = max(0, total_pages - 1)
        self._update_page_view()

    def on_page_num_entry(self, event):
        val = self.ent_page_num.get().strip()
        if val.isdigit():
            page = int(val) - 1
            total_pages = self._get_total_pages()
            if 0 <= page < total_pages:
                self.current_page = page
                self._update_page_view()
            else:
                self.ent_page_num.delete(0, tk.END)
                self.ent_page_num.insert(0, str(self.current_page + 1))

    def _get_total_pages(self):
        count = len(self.filtered_records)
        return max(1, (count + self.page_size - 1) // self.page_size)

    def _update_page_view(self):
        # Clear tree
        for item in self.boms_tree.get_children():
            self.boms_tree.delete(item)
            
        total_pages = self._get_total_pages()
        self.current_page = min(self.current_page, total_pages - 1)
        self.current_page = max(0, self.current_page)
        
        # Update entry and label
        self.ent_page_num.delete(0, tk.END)
        self.ent_page_num.insert(0, str(self.current_page + 1))
        self.lbl_total_pages.config(text=f"of {total_pages}")
        
        # Insert page items
        start_idx = self.current_page * self.page_size
        end_idx = start_idx + self.page_size
        page_records = self.filtered_records[start_idx:end_idx]
        
        for record in page_records:
            original_idx = record["original_index"]
            self.boms_tree.insert(
                "", "end", iid=str(original_idx),
                values=(record["Customer"], record["RFQ"], record["Date"])
            )

    def _filter_available_boms(self, *args):
        search_cust = self.search_cust_var.get().lower()
        search_rfq = self.search_rfq_var.get().lower()
        
        self.filtered_records = []
        for idx, record in enumerate(self.bom_records):
            cust = record["Customer"].lower()
            rfq = record["RFQ"].lower()
            if search_cust in cust and search_rfq in rfq:
                rec_copy = record.copy()
                rec_copy["original_index"] = idx
                self.filtered_records.append(rec_copy)
                
        self.current_page = 0
        self._update_page_view()

    def _on_bom_select(self, event):
        self.search_assy_var.set("")
        self._filter_assemblies()

    def _filter_assemblies(self, *args):
        # Clear assemblies tree
        for item in self.assy_tree.get_children():
            self.assy_tree.delete(item)
            
        sel = self.boms_tree.selection()
        if not sel:
            return
            
        record_idx = int(sel[0])
        record = self.bom_records[record_idx]
        raw_data = record["raw_data"]
        
        search_query = self.search_assy_var.get().lower().strip()
        
        assemblies = raw_data.get("Assemblies", [])
        for a_idx, assy in enumerate(assemblies):
            assy_num = assy.get("Assy #", "N/A")
            model = assy.get("Assy Model", "N/A")
            rev = assy.get("Assy Rev", "N/A")
            
            if search_query and search_query not in str(assy_num).lower():
                continue
                
            self.assy_tree.insert(
                "", "end", iid=f"{record_idx}_{a_idx}",
                values=(assy_num, model, rev)
            )

    def _on_add(self):
        sel_assy = self.assy_tree.selection()
        if not sel_assy:
            show_error("No Selection", "Please select one or more assemblies from the left list to add.", parent=self)
            return
            
        for item_id in sel_assy:
            parts = item_id.split("_")
            record_idx = int(parts[0])
            assy_idx = int(parts[1])
            
            record = self.bom_records[record_idx]
            assy = record["raw_data"]["Assemblies"][assy_idx]
            
            assy_num = assy.get("Assy #", "N/A")
            model = assy.get("Assy Model", "N/A")
            rev = assy.get("Assy Rev", "N/A")
            cust = record["Customer"]
            rfq = record["RFQ"]
            filepath = record["filepath"]
            
            # Check if already added
            already_added = False
            for child in self.selected_tree.get_children():
                vals = self.selected_tree.item(child, "values")
                if vals[5] == filepath and vals[2] == assy_num:
                    already_added = True
                    break
                    
            if not already_added:
                iid = f"sel_{record_idx}_{assy_idx}_{len(self.selected_tree.get_children())}"
                self.selected_tree.insert(
                    "", "end", iid=iid,
                    values=(cust, rfq, assy_num, model, rev, filepath, record_idx, assy_idx)
                )

    def _on_remove(self):
        sel = self.selected_tree.selection()
        if not sel:
            show_error("No Selection", "Please select one or more assemblies from the right list to remove.", parent=self)
            return
        for item_id in sel:
            self.selected_tree.delete(item_id)

    def _on_confirm(self):
        cust_name = self.cust_var.get().strip()
        rfq_num = self.rfq_var.get().strip()
        email_subject = self.email_var.get().strip()
        
        if not cust_name:
            show_error("Validation Error", "Please specify a Customer Name.", parent=self)
            return
        if not rfq_num:
            show_error("Validation Error", "Please specify a new RFQ Number.", parent=self)
            return
            
        selected_items = self.selected_tree.get_children()
        if not selected_items:
            show_error("Validation Error", "Please add at least one assembly to the requote list.", parent=self)
            return
            
        all_rows = []
        assembly_names_seen = {}
        
        # Read components from files for each selected assembly
        for child in selected_items:
            vals = self.selected_tree.item(child, "values")
            cust = vals[0]
            rfq = vals[1]
            assy_num = vals[2]
            model = vals[3]
            rev = vals[4]
            filepath = vals[5]
            record_idx = int(vals[6])
            assy_idx = int(vals[7])
            
            record = self.bom_records[record_idx]
            assy_data = record["raw_data"]["Assemblies"][assy_idx]
            components = assy_data.get("Components", [])
            
            # Handle duplicate assembly names
            final_assy_num = assy_num
            if assy_num in assembly_names_seen:
                assembly_names_seen[assy_num] += 1
                final_assy_num = f"{assy_num}_{assembly_names_seen[assy_num]}"
            else:
                assembly_names_seen[assy_num] = 1
                
            for comp in components:
                row = {
                    'Assy #': final_assy_num,
                    'Assy Model': model,
                    'Assy Rev': rev,
                    'Part': comp.get('Part', ''),
                    'Description': comp.get('Description', ''),
                    'MFR': comp.get('MFR', ''),
                    'MPN': comp.get('MPN', ''),
                    'Qty': comp.get('Qty', 0.0),
                    'UOM': comp.get('UOM', ''),
                    'Line Item': comp.get('Line Item', '')
                }
                all_rows.append(row)
                
        if any(v > 1 for v in assembly_names_seen.values()):
            duplicates = [k for k, v in assembly_names_seen.items() if v > 1]
            msg = "Note: The following assemblies were selected multiple times or from different sources. To keep them separate, they have been renamed with suffixes:\n"
            for dup in duplicates:
                msg += f"- {dup} will be imported as {dup}_1, {dup}_2, etc.\n"
            show_info("Assembly Renaming", msg, parent=self)
            
        df_consolidated = pd.DataFrame(all_rows)
        
        # Ensure all STANDARD_COLUMNS exist
        for col in STANDARD_COLUMNS:
            if col not in df_consolidated.columns:
                df_consolidated[col] = ""
                
        # Reorder columns
        df_consolidated = df_consolidated[STANDARD_COLUMNS]
        
        # Build self.result dictionary representing session
        self.result = {
            "is_edit_saved": False,
            "is_requote": True,
            "customer_info": [None, cust_name, rfq_num, email_subject],
            "mapping": {},
            "assembly_status": {str(assy): "Viewed" for assy in df_consolidated['Assy #'].unique() if pd.notna(assy)},
            "df_data": df_consolidated.to_dict(orient='records'),
            "temp_file_path": None
        }
        
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
