import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

_TAG_COLORS = {
    'pending_bom':      {'background': '#fff3cd', 'foreground': '#856404'},
    'pending_sourcing': {'background': '#cce5ff', 'foreground': '#004085'},
    'pending_costing':  {'background': '#e8daef', 'foreground': '#5b2c6f'},
    'pending_npi':      {'background': '#fadbd8', 'foreground': '#78281f'},
    'pending_wi':       {'background': '#f9ebd2', 'foreground': '#7e5109'},
    'completed':        {'background': '#d4edda', 'foreground': '#155724'},
    'revert_pending':   {'background': '#ffe0b2', 'foreground': '#e65100'},
}

_STATUS_FILTER_VALUES = [
    'All', 'BOM Verification', 'Pending Sourcing & Cycle Time',
    'Pending Costing', 'Pending NPI', 'Pending WI', 'Completed', 'Revert Pending',
]

def _status_to_stage_and_tag(data):
    status = data.get('status')
    s_done_flag = data.get('sourcing_status') in ('completed', 'approved')
    c_done_flag = data.get('cycle_time_status') in ('completed', 'approved')
    if not status or status == 'pending_bom':
        if s_done_flag or c_done_flag or data.get("cycle_time_data") or data.get("nre_data"):
            status = 'pending_sourcing_and_cycle_time'
        else:
            status = 'pending_bom'
            
    if status == 'pending_bom':
        return 'BOM Verification', 'pending_bom'
    if status == 'pending_sourcing_and_cycle_time':
        s_st = data.get('sourcing_status')
        s_done = s_st in ('completed', 'approved')
        c_done = data.get('cycle_time_status') in ('completed', 'approved')
        if s_st == 'partial':
            stage = 'Partial Sourcing Dispatched'
        elif s_done and not c_done:
            stage = 'Pending Cycle Time (Sourcing Done)'
        elif c_done and not s_done:
            stage = 'Pending Sourcing (Cycle Time Done)'
        else:
            stage = 'Pending Sourcing & Cycle Time'
        return stage, 'pending_sourcing'
    if status == 'pending_costing':
        return 'Pending Costing', 'pending_costing'
    if status == 'pending_npi':
        return 'Pending NPI', 'pending_npi'
    if status == 'pending_wi':
        return 'Pending WI', 'pending_wi'
    if status == 'completed':
        return 'Completed', 'completed'
    rp = data.get('revert_pending')
    if rp and not rp.get('acknowledged'):
        target_stage = rp.get('target_stage', 'pending_bom')
        _labels = {
            "pending_bom": "BOM Verification",
            "pending_sourcing_and_cycle_time": "Pending Sourcing & Cycle Time",
            "pending_costing": "Pending Costing",
            "pending_npi": "Pending NPI",
            "pending_wi": "Pending WI",
            "completed": "Completed"
        }
        return _labels.get(target_stage, target_stage), 'revert_pending'
    return status, 'pending_bom'


class BaseProjectManagementPanel(tk.Frame):
    def __init__(self, parent, bom_data_dir, title_prefix='', user_name=None, user_role=None, show_stats=False, module_context=None, **kwargs):
        super().__init__(parent, bg='#EBF8FF', **kwargs)
        self.bom_data_dir = bom_data_dir
        self.user_name = user_name or getattr(parent, 'user_name', 'admin')
        self.user_role = user_role or getattr(parent, 'user_role', 'Admin')
        self.show_stats = show_stats
        self.filter_criteria = None
        # module_context: 'bom', 'sourcing', 'cycle_time', or None (all)
        self.module_context = module_context
        
        # Subclasses can restrict this to list of tags: e.g. ["pending_bom"]
        self.allowed_stages = None
        
        # Column sort state: _pm_sort_col (col name), _pm_sort_state ('asc', 'desc', or None)
        self._pm_sort_col = None
        self._pm_sort_state = None
        self.raw_all_data = []
        
        self.all_data = []
        self._build_style()
        self._build_header(title_prefix)
        self._build_filter_bar()
        self._build_actions_bar()
        if self.show_stats:
            self._build_dashboard_stats()
        self._build_table()

    def _build_style(self):
        try:
            style = ttk.Style()
            style.configure('PM.Treeview.Heading', font=('Segoe UI', 10, 'bold'),
                            background='#dcedf5', foreground='#1A365D')
            style.configure('PM.Treeview', font=('Segoe UI', 10), rowheight=28)
        except Exception:
            pass

    def _build_header(self, title_prefix):
        hdr = tk.Frame(self, bg='#1A365D', height=48)
        hdr.pack(fill='x')
        title = f'{title_prefix}Project Management Dashboard'
        tk.Label(hdr, text=title, font=('Segoe UI', 13, 'bold'),
                 fg='white', bg='#1A365D').pack(side='left', padx=18, pady=10)
        
        tk.Button(hdr, text='Refresh', font=('Segoe UI', 9, 'bold'),
                  bg='#3498db', fg='white', activebackground='#217dbb',
                  activeforeground='white', cursor='hand2', bd=0, relief='flat',
                  padx=12, command=self.load_data).pack(side='right', padx=16, pady=10)

    def _build_filter_bar(self):
        fbar = tk.Frame(self, bg='#dcedf5', pady=8)
        fbar.pack(fill='x')
        tk.Label(fbar, text='Filter by Status:', font=('Segoe UI', 9, 'bold'),
                 bg='#dcedf5').pack(side='left', padx=16)
        
        self.status_var = tk.StringVar(value='All')
        
        is_boss_or_admin = (
            str(self.user_role).lower() in ("boss", "admin", "system administrator", "top management") or 
            str(self.user_name).lower() in ("boss", "admin", "sysadmin")
        )
        if not is_boss_or_admin and self.allowed_stages is not None:
            _labels = {
                "pending_bom": "BOM Verification",
                "pending_sourcing": "Pending Sourcing & Cycle Time",
                "pending_costing": "Pending Costing",
                "pending_npi": "Pending NPI",
                "pending_wi": "Pending WI"
            }
            cb_values = ['All'] + [_labels[t] for t in self.allowed_stages if t in _labels]
        else:
            cb_values = _STATUS_FILTER_VALUES
            
        cb = ttk.Combobox(fbar, textvariable=self.status_var,
                          values=cb_values, state='readonly',
                          width=35, font=('Segoe UI', 9))
        cb.pack(side='left')
        cb.bind('<<ComboboxSelected>>', lambda _: self.filter_tree())
        
        self.btn_filter = tk.Button(fbar, text="🔍 Filter Records", font=("Segoe UI", 9, "bold"),
                                   bg="#e2e8f0", fg="#4a5568", activebackground="#cbd5e0",
                                   activeforeground="#2d3748", cursor="hand2", bd=0, relief="flat",
                                   padx=12, pady=2, command=self.open_filter_dialog)
        self.btn_filter.pack(side="left", padx=10)
        style_dialog_button(self.btn_filter, bg_color="#e2e8f0", fg_color="#4a5568", active_bg="#cbd5e0")
        
        self.btn_sort = tk.Button(fbar, text="⇅ Sort Records", font=("Segoe UI", 9, "bold"),
                                 bg="#e2e8f0", fg="#4a5568", activebackground="#cbd5e0",
                                 activeforeground="#2d3748", cursor="hand2", bd=0, relief="flat",
                                 padx=12, pady=2, command=self.open_sort_dialog)
        self.btn_sort.pack(side="left", padx=5)
        style_dialog_button(self.btn_sort, bg_color="#e2e8f0", fg_color="#4a5568", active_bg="#cbd5e0")
        
        self.count_lbl = tk.Label(fbar, text='', font=('Segoe UI', 9, 'bold'),
                                  bg='#dcedf5', fg='#1A365D')
        self.count_lbl.pack(side='right', padx=16)

    def _build_actions_bar(self):
        abar = tk.Frame(self, bg='#dcedf5', pady=6)
        abar.pack(fill='x')
        
        tk.Label(abar, text='Actions:', font=('Segoe UI', 9, 'bold'),
                 bg='#dcedf5', fg='#1A365D').pack(side='left', padx=16)
        
        self.btn_view = tk.Button(abar, text='👁️ View Details', font=('Segoe UI', 9, 'bold'),
                  bg='#e2e8f0', fg='#4a5568', activebackground='#cbd5e0',
                  activeforeground='#2d3748', cursor='hand2', bd=0, relief='flat',
                  padx=12, command=self.on_view_details, state='disabled')
        self.btn_view.pack(side='left', padx=5)

        self.btn_revert = tk.Button(abar, text='🔁 Request Revert', font=('Segoe UI', 9, 'bold'),
                  bg='#e2e8f0', fg='#4a5568', activebackground='#cbd5e0',
                  activeforeground='#2d3748', cursor='hand2', bd=0, relief='flat',
                  padx=12, command=self.request_revert_workflow, state='disabled')
        self.btn_revert.pack(side='left', padx=5)
        
        self.btn_undo_revert = tk.Button(abar, text='↩️ Undo Revert', font=('Segoe UI', 9, 'bold'),
                  bg='#e2e8f0', fg='#4a5568', activebackground='#cbd5e0',
                  activeforeground='#2d3748', cursor='hand2', bd=0, relief='flat',
                  padx=12, command=self.undo_revert_workflow, state='disabled')
        self.btn_undo_revert.pack(side='left', padx=5)
        
        self.btn_history = tk.Button(abar, text='📜 Revert History', font=('Segoe UI', 9, 'bold'),
                  bg='#e2e8f0', fg='#4a5568', activebackground='#cbd5e0',
                  activeforeground='#2d3748', cursor='hand2', bd=0, relief='flat',
                  padx=12, command=self.show_revert_history, state='disabled')
        self.btn_history.pack(side='left', padx=5)
        
        self.btn_query = tk.Button(abar, text='❓ Query User', font=('Segoe UI', 9, 'bold'),
                  bg='#e2e8f0', fg='#4a5568', activebackground='#cbd5e0',
                  activeforeground='#2d3748', cursor='hand2', bd=0, relief='flat',
                  padx=12, command=self.query_pic_workflow, state='disabled')
        self.btn_query.pack(side='left', padx=5)

        self.btn_reassign_pic = tk.Button(abar, text='👤 Reassign Project PIC', font=('Segoe UI', 9, 'bold'),
                  bg='#e2e8f0', fg='#4a5568', activebackground='#cbd5e0',
                  activeforeground='#2d3748', cursor='hand2', bd=0, relief='flat',
                  padx=12, command=self.reassign_project_pic_dialog, state='disabled')
        self.btn_reassign_pic.pack(side='left', padx=5)

    # Column index map for all_data tuple (15 elements + tag + mtime)
    _PM_COL_IDX = {
        'RFQ ID': 0, 'Customer': 1, 'Assembly': 2, 'Current Stage': 3,
        'BOM Creation (Date)': 4, 'BOM Creation (Time)': 5,
        'Last Update (Date)': 6, 'Last Update (Time)': 7,
        'BOM PIC': 8, 'Sourcing PIC': 9, 'Cycle Time PIC': 10,
        'Costing PIC': 11, 'NPI PIC': 12, 'WI PIC': 13,
    }

    def _build_table(self):
        tree_frame = tk.Frame(self, bg='#ffffff')
        tree_frame.pack(fill='both', expand=True, padx=16, pady=12)
        cols = ('RFQ ID', 'Customer', 'Assembly', 'Current Stage', 'BOM Creation (Date)', 'BOM Creation (Time)', 'Last Update (Date)', 'Last Update (Time)', 'BOM PIC', 'Sourcing PIC', 'Cycle Time PIC', 'Costing PIC', 'NPI PIC', 'WI PIC')
        self.tree = ttk.Treeview(tree_frame, columns=cols, show='headings', style='PM.Treeview')
        col_widths = {
            'RFQ ID': 110, 'Customer': 150, 'Assembly': 150, 'Current Stage': 190,
            'BOM Creation (Date)': 120, 'BOM Creation (Time)': 120,
            'Last Update (Date)': 120, 'Last Update (Time)': 120,
            'BOM PIC': 120, 'Sourcing PIC': 120, 'Cycle Time PIC': 120,
            'Costing PIC': 120, 'NPI PIC': 120, 'WI PIC': 120
        }
        for col in cols:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_column(c))
            self.tree.column(col, width=col_widths.get(col, 120), minwidth=80, anchor='w')
        for tag, cfg in _TAG_COLORS.items():
            self.tree.tag_configure(tag, **cfg)

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        self.tree.pack(side='left', fill='both', expand=True)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_row_selected)

    def _sort_column(self, col):
        """Toggle 3-state column sort: ASC (▲) -> DESC (▼) -> Reset (no arrow)."""
        cols = ('RFQ ID', 'Customer', 'Assembly', 'Current Stage', 'BOM Creation (Date)',
                'BOM Creation (Time)', 'Last Update (Date)', 'Last Update (Time)',
                'BOM PIC', 'Sourcing PIC', 'Cycle Time PIC', 'Costing PIC', 'NPI PIC', 'WI PIC')
        idx = self._PM_COL_IDX.get(col, 0)
        
        if self._pm_sort_col != col:
            self._pm_sort_col = col
            self._pm_sort_state = 'asc'
        elif self._pm_sort_state == 'asc':
            self._pm_sort_state = 'desc'
        else:
            self._pm_sort_col = None
            self._pm_sort_state = None

        if self._pm_sort_state is None:
            if hasattr(self, 'raw_all_data') and self.raw_all_data:
                self.all_data = list(self.raw_all_data)
        else:
            rev = (self._pm_sort_state == 'desc')
            def _key(row):
                val = str(row[idx]).lower()
                try:
                    return (0, float(val))
                except (ValueError, TypeError):
                    return (1, val)
            self.all_data.sort(key=_key, reverse=rev)

        arrow = ' ▲' if self._pm_sort_state == 'asc' else (' ▼' if self._pm_sort_state == 'desc' else '')
        for c in cols:
            if c == self._pm_sort_col and self._pm_sort_state is not None:
                self.tree.heading(c, text=c + arrow)
            else:
                self.tree.heading(c, text=c)
        self.filter_tree()

    def open_sort_dialog(self):
        """Open the Sort Records dialog for PM records."""
        try:
            from treeview_sort import SortRecordsDialog
        except ImportError:
            import sys
            _shared_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
            if _shared_dir not in sys.path:
                sys.path.insert(0, _shared_dir)
            from treeview_sort import SortRecordsDialog

        cols = ['RFQ ID', 'Customer', 'Assembly', 'Current Stage', 'BOM Creation (Date)',
                'BOM Creation (Time)', 'Last Update (Date)', 'Last Update (Time)',
                'BOM PIC', 'Sourcing PIC', 'Cycle Time PIC', 'Costing PIC', 'NPI PIC', 'WI PIC']
        
        curr_rules = getattr(self, "_pm_sort_rules", [])

        dlg = SortRecordsDialog(self, cols, current_sort_rules=curr_rules)
        self.wait_window(dlg)
        if dlg.result_sort_rules:
            self._pm_sort_rules = dlg.result_sort_rules

            def _get_val(row, col_name):
                idx = self._PM_COL_IDX.get(col_name, 0)
                v = str(row[idx]).lower()
                try: return (0, float(v))
                except (ValueError, TypeError): return (1, v)

            for col_name, direction in reversed(self._pm_sort_rules):
                rev = (direction == 'desc')
                self.all_data.sort(key=lambda r: _get_val(r, col_name), reverse=rev)
        else:
            self._pm_sort_rules = []
            if hasattr(self, 'raw_all_data') and self.raw_all_data:
                self.all_data = list(self.raw_all_data)

        rule_map = {col: (direction, idx + 1) for idx, (col, direction) in enumerate(getattr(self, "_pm_sort_rules", []))}
        for c in cols:
            indicator = ""
            if c in rule_map:
                direction, priority = rule_map[c]
                arrow = ' ▲' if direction == 'asc' else ' ▼'
                if len(self._pm_sort_rules) > 1:
                    indicator = f"{arrow} ({priority})"
                else:
                    indicator = f"{arrow}"
            self.tree.heading(c, text=c + indicator)
        self.filter_tree()
        self.filter_tree()

    def resolve_assigned_pics(self, data):
        pics = []
        status = data.get("status") or "pending_bom"
        if status == "pending_bom":
            p = data.get("bom_assigned_by") or data.get("dispatched_by")
            if p: pics.append(p)
        elif status == "pending_sourcing_and_cycle_time":
            s_pic = data.get("sourcing_assigned_by") or data.get("sourcing_dispatched_by")
            c_pic = data.get("cycle_time_assigned_by") or data.get("cycle_time_dispatched_by")
            if s_pic: pics.append(s_pic)
            if c_pic and c_pic not in pics: pics.append(c_pic)
        elif status == "pending_costing":
            p = data.get("costing_assigned_by") or data.get("costing_dispatched_by")
            if p: pics.append(p)
        elif status == "pending_npi":
            p = data.get("npi_assigned_by") or data.get("npi_dispatched_by")
            if p: pics.append(p)
        elif status == "pending_wi":
            p = data.get("wi_assigned_by") or data.get("wi_dispatched_by")
            if p: pics.append(p)

        history = data.get("history", []) or data.get("audit_trail", []) or data.get("revert_history", [])
        for entry in history:
            if isinstance(entry, dict):
                stg = entry.get("stage") or entry.get("target_stage") or entry.get("from_stage")
                u = entry.get("Changed By") or entry.get("user") or entry.get("requested_by") or entry.get("dispatched_by")
                if u:
                    if not stg or stg == status or status == "pending_bom" or not pics:
                        if u not in pics:
                            pics.append(u)

        if not pics:
            try:
                from revert_workflow import get_system_pics
                config = get_system_pics(status)
                default_pics = config.get("to", []) + config.get("cc", [])
                for d in default_pics:
                    if d and d not in pics:
                        pics.append(d)
            except:
                pass

        try:
            from revert_workflow import get_pic_name
            resolved = []
            for p in pics:
                real_p = get_pic_name(p)
                if real_p and real_p not in resolved:
                    resolved.append(real_p)
            if not resolved:
                return "Unassigned"
            else:
                return ", ".join(resolved)
        except:
            return ", ".join(pics) if pics else "Unassigned"

    def load_data(self):
        """Loads all BOM project data in a background thread to avoid blocking the UI."""
        import threading
        if hasattr(self, 'status_bar'):
            self.status_bar.config(text="🔄 Loading project data, please wait...")

        def _worker():
            all_data = []
            row_meta_cache = {}  # rfq_id -> {has_revert_pending, revert_history_len}

            if not os.path.exists(self.bom_data_dir):
                self.after(0, self._on_load_complete, all_data, row_meta_cache)
                return

            # ---- Pre-load lookup files ONCE (avoid per-row disk reads) ----
            # Read user_directory.json directly — avoids importing revert_workflow
            # which triggers smtplib import (DNS lookup, can hang 60+ seconds)
            _shared_dir = os.path.normpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
            _user_dir = {}
            try:
                _ud_file = os.path.join(_shared_dir, "user_directory.json")
                if os.path.exists(_ud_file):
                    with open(_ud_file, 'r', encoding='utf-8-sig') as _f:
                        _user_dir = json.load(_f)
            except Exception:
                _user_dir = {}

            _sig_data = {}
            try:
                _sig_file = os.path.normpath(os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "WI", "Master Data", "signatures.json"))
                if os.path.exists(_sig_file):
                    with open(_sig_file, 'r', encoding='utf-8') as _sf:
                        _sig_data = json.load(_sf)
            except Exception:
                _sig_data = {}

            def _resolve_pic_fast(username):
                """Fast PIC name resolution handling multi-user lists and pre-cached dicts."""
                if not username:
                    return ""
                parts = [p.strip() for p in str(username).split(",") if p.strip()]
                res_names = []
                for p in parts:
                    if p.lower() in ("admin", "sysadmin"):
                        res_names.append("Ai Tink" if p.lower() == "admin" else "Sysadmin")
                        continue
                    matched = False
                    for name in _user_dir.keys():
                        if name.lower() == p.lower():
                            res_names.append(name)
                            matched = True
                            break
                    if not matched:
                        for name in _sig_data.keys():
                            if name.lower() == p.lower():
                                res_names.append(p.title())
                                matched = True
                                break
                    if not matched:
                        res_names.append(p.title() if p.islower() else p)
                return ", ".join(res_names)

            def _resolve_stage_pic(data, stage_key):
                pics = []
                if stage_key == "pending_bom":
                    p = data.get("bom_assigned_by") or data.get("dispatched_by")
                    if p: pics.append(p)
                elif stage_key == "pending_sourcing":
                    p = data.get("sourcing_assigned_by") or data.get("sourcing_dispatched_by")
                    if p: pics.append(p)
                elif stage_key == "pending_cycle_time":
                    p = data.get("cycle_time_assigned_by") or data.get("cycle_time_dispatched_by")
                    if p: pics.append(p)
                elif stage_key == "pending_costing":
                    p = data.get("costing_assigned_by") or data.get("costing_dispatched_by")
                    if p: pics.append(p)
                elif stage_key == "pending_npi":
                    p = data.get("npi_assigned_by") or data.get("npi_dispatched_by")
                    if p: pics.append(p)
                elif stage_key == "pending_wi":
                    p = data.get("wi_assigned_by") or data.get("wi_dispatched_by")
                    if p: pics.append(p)

                if pics:
                    resolved = []
                    for p in pics:
                        rp = _resolve_pic_fast(p)
                        if rp and rp not in resolved:
                            resolved.append(rp)
                    if resolved:
                        return ", ".join(resolved)

                history = data.get("history", []) or data.get("audit_trail", []) or data.get("revert_history", [])
                for entry in history:
                    if isinstance(entry, dict):
                        stg = entry.get("stage") or entry.get("target_stage") or entry.get("from_stage")
                        u = entry.get("Changed By") or entry.get("user") or entry.get("requested_by") or entry.get("dispatched_by")
                        if u and (stg == stage_key):
                            if u not in pics:
                                pics.append(u)

                if pics:
                    resolved = []
                    for p in pics:
                        rp = _resolve_pic_fast(p)
                        if rp and rp not in resolved:
                            resolved.append(rp)
                    if resolved:
                        return ", ".join(resolved)

                try:
                    from revert_workflow import get_system_pics
                    cfg = get_system_pics(stage_key)
                    default_pics = cfg.get("to", [])
                    resolved = []
                    for d in default_pics:
                        if d:
                            rp = _resolve_pic_fast(d)
                            if rp and rp not in resolved and rp != "Ai Tink":
                                resolved.append(rp)
                    if resolved:
                        return ", ".join(resolved)
                except: pass

                return "Sysadmin" if stage_key == "pending_bom" else "Unassigned"
            # ---- End of pre-load setup ----

            is_boss_or_admin = (
                str(self.user_role).lower() in ("boss", "admin", "system administrator", "top management") or
                str(self.user_name).lower() in ("boss", "admin", "sysadmin")
            )

            for root_dir, dirs, files in os.walk(self.bom_data_dir):
                for filename in files:
                    if not filename.endswith('.json') or filename.endswith('metadata.json'):
                        continue
                    filepath = os.path.join(root_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8-sig') as fh:
                            data = json.load(fh)
                        rfq_id   = data.get('RFQ', filename.replace('.json', ''))
                        customer = data.get('Customer', 'Unknown')
                        stage, tag = _status_to_stage_and_tag(data)

                        if not is_boss_or_admin and self.allowed_stages is not None:
                            if tag not in self.allowed_stages:
                                continue

                        revert_pending = data.get("revert_pending")
                        has_revert_pending = False
                        if revert_pending and not revert_pending.get("acknowledged", False):
                            current_status = data.get("status") or "pending_bom"
                            target_stage = revert_pending.get("target_stage")
                            if current_status != target_stage:
                                revert_pending["acknowledged"] = True
                                try:
                                    with open(filepath, 'w', encoding='utf-8') as wf:
                                        json.dump(data, wf, indent=4)
                                except:
                                    pass
                            else:
                                has_revert_pending = True

                        revert_history_len = len(data.get("revert_history", []))
                        row_meta_cache[rfq_id] = {
                            "has_revert_pending": has_revert_pending,
                            "revert_history_len": revert_history_len
                        }

                        assy_list = [a.get('Assy #', '') for a in data.get('Assemblies', [])]
                        assy_str  = ', '.join(filter(None, assy_list))
                        if len(assy_str) > 40:
                            assy_str = assy_str[:37] + '...'
                        mtime    = os.path.getmtime(filepath)
                        dt_obj   = datetime.fromtimestamp(mtime)
                        date_val = dt_obj.strftime("%d.%m.%Y")
                        time_val = dt_obj.strftime("%I:%M %p")

                        bom_pic = _resolve_stage_pic(data, "pending_bom")
                        sourcing_pic = _resolve_stage_pic(data, "pending_sourcing")
                        cycle_time_pic = _resolve_stage_pic(data, "pending_cycle_time")
                        costing_pic = _resolve_stage_pic(data, "pending_costing")
                        npi_pic = _resolve_stage_pic(data, "pending_npi")
                        wi_pic = _resolve_stage_pic(data, "pending_wi")

                        try:
                            from utils import get_bom_creation_date
                            bom_creation_full = get_bom_creation_date(data, filepath)
                        except:
                            bom_creation_full = datetime.fromtimestamp(mtime).strftime("%d.%m.%Y (%I:%M %p)")

                        if " (" in bom_creation_full:
                            bom_date, bom_time = bom_creation_full.split(" (")
                            bom_time = bom_time.replace(")", "")
                        else:
                            bom_date = bom_creation_full
                            bom_time = ""

                        all_data.append((rfq_id, customer, assy_str, stage, bom_date, bom_time, date_val, time_val, bom_pic, sourcing_pic, cycle_time_pic, costing_pic, npi_pic, wi_pic, tag, mtime))
                    except Exception as exc:
                        print(f'[PM Panel] Error reading {filepath}: {exc}')

            _STAGE_ORDER = {
                'pending_bom': 0, 'pending_sourcing': 1, 'pending_costing': 2,
                'pending_npi': 3, 'pending_wi': 4, 'revert_pending': 5, 'completed': 6,
            }
            all_data.sort(key=lambda row: (_STAGE_ORDER.get(row[14], 6), -row[15]))
            q.put((all_data, row_meta_cache))

        import queue
        q = queue.Queue()
        threading.Thread(target=_worker, daemon=True).start()

        def _poll_queue():
            try:
                res = q.get_nowait()
                self._on_load_complete(res[0], res[1])
            except queue.Empty:
                try:
                    self.after(50, _poll_queue)
                except Exception:
                    pass

        try:
            self.after(50, _poll_queue)
        except Exception:
            pass

    def _on_load_complete(self, all_data, row_meta_cache):
        """Called on the main thread after background load completes."""
        self.all_data = all_data
        self._row_meta_cache = row_meta_cache
        self.raw_all_data = list(all_data)
        self.filter_tree()

    def _build_dashboard_stats(self):
        self.dash_frame = tk.Frame(self, bg='#ffffff', bd=1, relief='solid')
        self.dash_frame.pack(side='bottom', fill='x', padx=16, pady=(0, 10))
        
        # Inner layout frame (2 columns: Stage Breakdown on left, Monthly Volume on right)
        inner = tk.Frame(self.dash_frame, bg='#ffffff', padx=12, pady=8)
        inner.pack(fill='x')
        
        # Left Panel - Stage Distribution
        self.stage_panel = tk.Frame(inner, bg='#ffffff')
        self.stage_panel.pack(side='left', fill='both', expand=True, padx=(0, 15))
        
        lbl_stage_title = tk.Label(self.stage_panel, text="📊 Stage Distribution & Percentages", 
                                   font=("Segoe UI", 10, "bold"), fg="#1A365D", bg="#ffffff")
        lbl_stage_title.pack(anchor="w")
        
        # Canvas for distribution bar
        self.stage_canvas = tk.Canvas(self.stage_panel, height=18, bg="#E2E8F0", highlightthickness=0)
        self.stage_canvas.pack(fill="x", pady=(4, 4))
        
        # Legend / Badges Frame
        self.stage_legend_frame = tk.Frame(self.stage_panel, bg="#ffffff")
        self.stage_legend_frame.pack(fill="x")
        
        # Divider Line
        divider = tk.Frame(inner, bg="#CBD5E0", width=1)
        divider.pack(side="left", fill="y", padx=10)
        
        # Right Panel - Monthly Volume
        self.month_panel = tk.Frame(inner, bg='#ffffff')
        self.month_panel.pack(side='right', fill='both', expand=True, padx=(15, 0))
        
        lbl_month_title = tk.Label(self.month_panel, text="📅 Monthly RFQ Volume Trend", 
                                   font=("Segoe UI", 10, "bold"), fg="#1A365D", bg="#ffffff")
        lbl_month_title.pack(anchor="w")
        
        # Canvas for monthly volume bar chart
        self.month_canvas = tk.Canvas(self.month_panel, height=18, bg="#E2E8F0", highlightthickness=0)
        self.month_canvas.pack(fill="x", pady=(4, 4))
        
        # Month Legend / Badges Frame
        self.month_legend_frame = tk.Frame(self.month_panel, bg="#ffffff")
        self.month_legend_frame.pack(fill="x")

    def update_dashboard_stats(self, displayed_rows=None):
        if not hasattr(self, 'dash_frame'):
            return
            
        rows = displayed_rows if displayed_rows is not None else self.all_data
        total_rfqs = len(rows)
        
        # Clear legends
        for w in self.stage_legend_frame.winfo_children():
            w.destroy()
        for w in self.month_legend_frame.winfo_children():
            w.destroy()
        self.stage_canvas.delete("all")
        self.month_canvas.delete("all")
        
        if total_rfqs == 0:
            tk.Label(self.stage_legend_frame, text="No RFQ records available", font=("Segoe UI", 9, "italic"), fg="#718096", bg="#ffffff").pack(anchor="w")
            tk.Label(self.month_legend_frame, text="No volume data available", font=("Segoe UI", 9, "italic"), fg="#718096", bg="#ffffff").pack(anchor="w")
            return

        # 1. Calculate Stage & PIC Breakdown
        stage_colors = {
            'pending_bom': '#3182CE',                          # Vibrant Blue
            'pending_sourcing_and_cycle_time': '#DD6B20',      # Vibrant Orange
            'pending_sourcing': '#DD6B20',                     # Vibrant Orange
            'pending_cycle_time': '#319795',                   # Vibrant Teal
            'pending_costing': '#805AD5',                      # Vibrant Purple
            'pending_npi': '#D69E2E',                          # Vibrant Gold
            'pending_wi': '#2B6CB0',                           # Deep Blue
            'revert_pending': '#E53E3E',                       # Vibrant Red
            'completed': '#38A169'                             # Vibrant Green
        }
        
        stage_labels = {
            'pending_bom': 'BOM Verification',
            'pending_sourcing_and_cycle_time': 'Pending Sourcing & Cycle Time',
            'pending_sourcing': 'Pending Sourcing',
            'pending_cycle_time': 'Pending Cycle Time',
            'pending_costing': 'Pending Costing',
            'pending_npi': 'Pending NPI',
            'pending_wi': 'Pending WI',
            'revert_pending': 'Revert Pending',
            'completed': 'Completed'
        }
        
        stage_counts = {}
        stage_pic_counts = {}

        for row in rows:
            tag = row[14] if len(row) > 14 and row[14] else "pending_bom"
            stage_name = str(row[3]).strip()

            # Determine working PIC portion for this stage
            if "bom" in stage_name.lower():
                pic_val = row[8]
            elif "sourcing" in stage_name.lower():
                pic_val = row[9]
            elif "cycle" in stage_name.lower():
                pic_val = row[10]
            elif "costing" in stage_name.lower():
                pic_val = row[11]
            elif "npi" in stage_name.lower():
                pic_val = row[12]
            elif "wi" in stage_name.lower():
                pic_val = row[13]
            else:
                pic_val = row[8]

            stage_counts[tag] = stage_counts.get(tag, 0) + 1
            if tag not in stage_pic_counts:
                stage_pic_counts[tag] = {}
            
            p_str = str(pic_val).strip() if pic_val and str(pic_val).strip() != "" else "-"
            stage_pic_counts[tag][p_str] = stage_pic_counts[tag].get(p_str, 0) + 1
            
        # Draw Stage Distribution Canvas Bar
        canvas_width = self.stage_canvas.winfo_width() or 450
        canvas_height = 18
        current_x = 0
        
        for tag, count in stage_counts.items():
            pct = count / total_rfqs
            bar_w = int(pct * canvas_width)
            color = stage_colors.get(tag, '#A0AEC0')
            if bar_w > 0:
                self.stage_canvas.create_rectangle(current_x, 0, current_x + bar_w, canvas_height, fill=color, outline='')
                current_x += bar_w
                
        # Fill legend badges with stage percentage & individual working PIC breakdown
        for tag, count in stage_counts.items():
            pct = (count / total_rfqs) * 100
            color = stage_colors.get(tag, '#A0AEC0')
            name = stage_labels.get(tag, tag.replace("_", " ").title())
            
            pic_parts = []
            if tag in stage_pic_counts:
                for pic, p_cnt in stage_pic_counts[tag].items():
                    pic_parts.append(f"{pic}: {p_cnt}")
            pic_str = f" → PIC: {', '.join(pic_parts)}" if pic_parts else ""

            badge_f = tk.Frame(self.stage_legend_frame, bg="#ffffff")
            badge_f.pack(side="top", anchor="w", pady=1)
            
            dot = tk.Label(badge_f, text="●", font=("Segoe UI", 9, "bold"), fg=color, bg="#ffffff")
            dot.pack(side="left")
            txt = tk.Label(badge_f, text=f"{name}: {count} ({pct:.1f}%){pic_str}", font=("Segoe UI", 8, "bold"), fg="#2D3748", bg="#ffffff")
            txt.pack(side="left", padx=(4, 0))

        # 2. Calculate Monthly Volume Trend
        month_counts = {}
        for row in rows:
            date_str = row[4] # e.g. "20.07.2026"
            try:
                dt = datetime.strptime(date_str, "%d.%m.%Y")
                m_key = dt.strftime("%b %Y") # e.g. "Jul 2026"
            except:
                m_key = "Unknown"
            month_counts[m_key] = month_counts.get(m_key, 0) + 1
            
        # Draw Monthly Volume Canvas Bar
        m_canvas_w = self.month_canvas.winfo_width() or 450
        m_current_x = 0
        month_palette = ['#3182CE', '#319795', '#D69E2E', '#DD6B20', '#E53E3E', '#805AD5']
        
        for idx, (m_key, m_count) in enumerate(month_counts.items()):
            pct = m_count / total_rfqs
            bar_w = int(pct * m_canvas_w)
            color = month_palette[idx % len(month_palette)]
            if bar_w > 0:
                self.month_canvas.create_rectangle(m_current_x, 0, m_current_x + bar_w, canvas_height, fill=color, outline='')
                m_current_x += bar_w
                
        # Fill Month Legend Badges
        for idx, (m_key, m_count) in enumerate(month_counts.items()):
            pct = (m_count / total_rfqs) * 100
            color = month_palette[idx % len(month_palette)]
            
            badge_f = tk.Frame(self.month_legend_frame, bg="#ffffff")
            badge_f.pack(side="left", padx=(0, 10), pady=1)
            
            dot = tk.Label(badge_f, text="■", font=("Segoe UI", 9), fg=color, bg="#ffffff")
            dot.pack(side="left")
            txt = tk.Label(badge_f, text=f"{m_key}: {m_count} ({pct:.1f}%)", font=("Segoe UI", 8, "bold"), fg="#2D3748", bg="#ffffff")
            txt.pack(side="left", padx=(2, 0))

    def filter_tree(self):
        self.tree.delete(*self.tree.get_children())
        filt = self.status_var.get()
        
        # Multi-value filter logic
        f_rfq = [v.lower() for v in (self.filter_criteria.get('rfq', []) if self.filter_criteria else [])]
        f_cust = [v.lower() for v in (self.filter_criteria.get('customer', []) if self.filter_criteria else [])]
        f_assy = [v.lower() for v in (self.filter_criteria.get('assembly', []) if self.filter_criteria else [])]
        f_stage = [v.lower() for v in (self.filter_criteria.get('stage', []) if self.filter_criteria else [])]
        f_bom_date = [v.lower() for v in (self.filter_criteria.get('bom_date', []) if self.filter_criteria else [])]
        f_last_update = [v.lower() for v in (self.filter_criteria.get('last_update', []) if self.filter_criteria else [])]
        f_user = [v.lower() for v in (self.filter_criteria.get('user', []) if self.filter_criteria else [])]
        
        is_filtering = any([f_rfq, f_cust, f_assy, f_stage, f_bom_date, f_last_update, f_user])
        if hasattr(self, 'btn_filter'):
            if is_filtering:
                self.btn_filter.config(text="🔍 Filter Records (Active)", bg="#fffde7", fg="#856404")
            else:
                self.btn_filter.config(text="🔍 Filter Records", bg="#e2e8f0", fg="#4a5568")
                
        count = 0
        visible_rows = []
        for row in self.all_data:
            stage = row[3]
            show = (
                filt == 'All'
                or filt in stage
                or (filt == 'Pending Sourcing & Cycle Time' and ('Sourcing' in stage or 'Cycle Time' in stage))
                or (filt == 'Revert Pending' and 'Revert Pending' in stage)
            )
            if not show:
                continue
                
            # Apply search criteria filters
            if f_rfq and not any(v in str(row[0]).lower() for v in f_rfq): continue
            if f_cust and not any(v in str(row[1]).lower() for v in f_cust): continue
            if f_assy and not any(v in str(row[2]).lower() for v in f_assy): continue
            if f_stage and not any(v in str(row[3]).lower() for v in f_stage): continue
            if f_bom_date and not any(v in str(row[4]).lower() for v in f_bom_date): continue
            if f_last_update and not any(v in str(row[6]).lower() for v in f_last_update): continue
            if f_user and not any(v in str(row[8]).lower() for v in f_user): continue
            
            self.tree.insert('', 'end', values=row[:14], tags=(row[14],))
            visible_rows.append(row)
            count += 1
            
        try:
            self.count_lbl.config(text=f'Total Records: {count}')
        except Exception:
            pass
        # Defer dashboard stats update so the treeview renders first
        self.after_idle(lambda rows=visible_rows: self.update_dashboard_stats(rows))

    def on_row_selected(self, event=None):
        sel = self.tree.selection()
        if not sel:
            self.btn_view.config(state="disabled", bg="#e2e8f0", fg="#4a5568")
            self.btn_revert.config(state="disabled", bg="#e2e8f0", fg="#4a5568")
            self.btn_undo_revert.config(state="disabled", bg="#e2e8f0", fg="#4a5568")
            self.btn_history.config(state="disabled", bg="#e2e8f0", fg="#4a5568")
            self.btn_query.config(state="disabled", bg="#e2e8f0", fg="#4a5568")
            if hasattr(self, 'btn_reassign_pic'):
                self.btn_reassign_pic.config(state="disabled", bg="#e2e8f0", fg="#4a5568")
            return

        item_vals = self.tree.item(sel[0], "values")
        rfq_id = item_vals[0]
        stage_name = item_vals[3]

        # Use cached metadata — no disk read on every click
        meta = getattr(self, '_row_meta_cache', {}).get(rfq_id, {})
        has_revert_pending = meta.get("has_revert_pending", False)
        revert_history_len = meta.get("revert_history_len", 0)

        self.btn_view.config(state="normal", bg="#008080", fg="white")

        ctx = getattr(self, 'module_context', None)
        is_at_bom = "BOM Verification" in stage_name
        is_at_sourcing_ct = any(k in stage_name for k in ("Sourcing", "Cycle Time"))

        if ctx == 'bom':
            can_revert = not is_at_bom
        elif ctx in ('sourcing', 'cycle_time'):
            can_revert = not is_at_sourcing_ct
        else:
            can_revert = not is_at_bom

        if can_revert:
            self.btn_revert.config(state="normal", bg="#e74c3c", fg="white")
        else:
            self.btn_revert.config(state="disabled", bg="#e2e8f0", fg="#4a5568")

        if has_revert_pending:
            self.btn_undo_revert.config(state="normal", bg="#319795", fg="white")
        else:
            self.btn_undo_revert.config(state="disabled", bg="#e2e8f0", fg="#4a5568")

        if revert_history_len > 0:
            self.btn_history.config(state="normal", bg="#3182ce", fg="white")
        else:
            self.btn_history.config(state="disabled", bg="#e2e8f0", fg="#4a5568")

        if "Completed" in stage_name:
            self.btn_query.config(state="disabled", bg="#e2e8f0", fg="#4a5568")
        else:
            self.btn_query.config(state="normal", bg="#dd6b20", fg="white")

        if hasattr(self, 'btn_reassign_pic'):
            user_role = str(getattr(self, 'user_role', '') or getattr(self, 'role', '')).lower()
            user_name = str(getattr(self, 'user_name', '') or getattr(self, 'username', '')).lower()
            top_win = self.winfo_toplevel()
            if not user_role or user_role == 'user':
                user_role = str(getattr(top_win, 'user_role', '') or getattr(top_win, 'role', '')).lower()
            if not user_name:
                user_name = str(getattr(top_win, 'user_name', '') or getattr(top_win, 'username', '')).lower()

            is_admin = (
                user_role in ("admin", "boss", "system administrator", "top management", "manager") or
                user_name in ("admin", "boss", "sysadmin")
            )
            if is_admin:
                self.btn_reassign_pic.config(state="normal", bg="#8e44ad", fg="white")
            else:
                self.btn_reassign_pic.config(state="disabled", bg="#e2e8f0", fg="#4a5568")

    def reassign_project_pic_dialog(self):
        user_role = str(getattr(self, 'user_role', '') or getattr(self, 'role', '')).lower()
        user_name = str(getattr(self, 'user_name', '') or getattr(self, 'username', '')).lower()
        top_win = self.winfo_toplevel()
        if not user_role or user_role == 'user':
            user_role = str(getattr(top_win, 'user_role', '') or getattr(top_win, 'role', '')).lower()
        if not user_name:
            user_name = str(getattr(top_win, 'user_name', '') or getattr(top_win, 'username', '')).lower()

        is_admin = (
            user_role in ("admin", "boss", "system administrator", "top management", "manager") or
            user_name in ("admin", "boss", "sysadmin")
        )
        if not is_admin:
            try:
                from revert_workflow import messagebox
                messagebox.showwarning("Access Denied", "Reassigning project PICs is restricted to Admin and above roles.", parent=self)
            except: pass
            return

        sel = self.tree.selection()
        if not sel:
            return
        item_vals = self.tree.item(sel[0], "values")
        rfq_id = item_vals[0]
        customer = item_vals[1]
        stage_name = item_vals[3]
        current_assigned_str = item_vals[8]

        try:
            from revert_workflow import ReassignProjectPICDialog
        except ImportError:
            import sys
            pm_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Project Management"))
            if pm_dir not in sys.path:
                sys.path.insert(0, pm_dir)
            from revert_workflow import ReassignProjectPICDialog

        dlg = ReassignProjectPICDialog(self, rfq_id, customer, stage_name, current_assigned_str, self.bom_data_dir)
        self.winfo_toplevel().wait_window(dlg)
        if getattr(dlg, "updated", False):
            self.load_data()

    def on_view_details(self):
        sel = self.tree.selection()
        if not sel:
            return
        item_vals = self.tree.item(sel[0], "values")
        rfq_id = item_vals[0]
        customer = item_vals[1]
        self.view_workflow(rfq_id, customer)

    def view_workflow(self, rfq_id, customer):
        pass

    def open_filter_dialog(self):
        unique_options = {
            'rfq': sorted(list(set(str(row[0]).strip() for row in self.all_data if str(row[0]).strip())), key=lambda x: x.lower()),
            'customer': sorted(list(set(str(row[1]).strip() for row in self.all_data if str(row[1]).strip())), key=lambda x: x.lower()),
            'assembly': sorted(list(set(str(row[2]).strip() for row in self.all_data if str(row[2]).strip())), key=lambda x: x.lower()),
            'stage': sorted(list(set(str(row[3]).strip() for row in self.all_data if str(row[3]).strip())), key=lambda x: x.lower()),
            'bom_date': sorted(list(set(str(row[4]).strip() for row in self.all_data if str(row[4]).strip())), key=lambda x: x.lower(), reverse=True),
            'last_update': sorted(list(set(str(row[6]).strip() for row in self.all_data if str(row[6]).strip())), key=lambda x: x.lower(), reverse=True),
            'user': sorted(list(set(str(row[8]).strip() for row in self.all_data if str(row[8]).strip())), key=lambda x: x.lower()),
        }
        dialog = ProjectManagementFilterDialog(self, initial_filter=self.filter_criteria, unique_options=unique_options)
        if dialog.result is not None:
            self.filter_criteria = dialog.result
            self.filter_tree()

        else:
            self.filter_criteria = None
            if hasattr(self, 'populate_tree'):
                self.populate_tree()
            elif hasattr(self, 'refresh_projects'):
                self.refresh_projects()
    def get_user_directory(self):
        users = {}
        shared_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
        user_dir_file = os.path.normpath(os.path.join(shared_dir, "user_directory.json"))
        if os.path.exists(user_dir_file):
            try:
                with open(user_dir_file, 'r', encoding='utf-8-sig') as f:
                    users = json.load(f)
            except Exception as e:
                print(f"Error loading user directory: {e}")
        return users

    def request_revert_workflow(self):
        sel = self.tree.selection()
        if not sel:
            return
            
        item_vals = self.tree.item(sel[0], "values")
        rfq_id = item_vals[0]
        customer = item_vals[1]
        stage_name = item_vals[3]
        
        stage_clean = stage_name.replace("Revert Pending -> ", "").strip()
        
        STAGE_NAMES_TO_CODES = {
            "BOM Verification": "pending_bom",
            "Pending Sourcing & Cycle Time": "pending_sourcing_and_cycle_time",
            "Pending Sourcing (Cycle Time Done)": "pending_sourcing_and_cycle_time",
            "Pending Cycle Time (Sourcing Done)": "pending_sourcing_and_cycle_time",
            "Pending Costing": "pending_costing",
            "Pending NPI": "pending_npi",
            "Pending WI": "pending_wi",
            "Completed": "completed"
        }
        stage_code = STAGE_NAMES_TO_CODES.get(stage_clean, "pending_bom")
        
        selector = RevertTargetStageSelectorDialog(self, stage_clean, module_context=getattr(self, 'module_context', None))
        self.winfo_toplevel().wait_window(selector)
        if not selector.selected_stage_code:
            return
            
        target_stage_code = selector.selected_stage_code
        target_stage_name = selector.selected_stage_name
        
        import sys
        shared_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
        if shared_dir not in sys.path:
            sys.path.append(shared_dir)
            
        from revert_workflow import request_revert, send_revert_email, EmailComposerDialog, get_user_email
        
        users = self.get_user_directory()
        available_recipients = {name: info.get("email", "") for name, info in users.items()}
        
        from revert_workflow import get_system_pics
        pics_config = get_system_pics(target_stage_code)
        target_to_names = pics_config.get("to", [])
        target_cc_names = pics_config.get("cc", [])
        
        target_to_emails = [available_recipients.get(n, get_user_email(n)) for n in target_to_names]
        target_cc_emails = [available_recipients.get(n, get_user_email(n)) for n in target_cc_names]
        
        # Cross-system CC: for Sourcing or Cycle Time reverts, always CC BOTH systems' PICs
        ctx = getattr(self, 'module_context', None)
        if ctx in ('sourcing', 'cycle_time'):
            for stage_key in ('pending_sourcing', 'pending_cycle_time'):
                peer_config = get_system_pics(stage_key)
                for name in peer_config.get("to", []) + peer_config.get("cc", []):
                    email = available_recipients.get(name, get_user_email(name))
                    if email and email not in target_cc_emails:
                        target_cc_emails.append(email)
        
        top_win = self.winfo_toplevel()
        requested_by = getattr(top_win, "user_name", getattr(top_win, "username", "Module User"))
        sender_email = available_recipients.get(requested_by, get_user_email(requested_by))
        if sender_email and sender_email not in target_cc_emails:
            target_cc_emails.append(sender_email)
        
        subject = f"[ContinuumX] Revert Request — RFQ {rfq_id} ({customer}) — Return to {target_stage_name}"
        body_template = """Dear {recipient},

A workflow revert has been requested for RFQ: """ + rfq_id + """ (Customer: """ + customer + """).

From Stage: """ + stage_clean + """
Returned To Stage: """ + target_stage_name + """
Requested By: """ + requested_by + """

Comments / Reason for Revert:
{comments}

💡 Note on data continuity: All manually-entered quotes, supplier pairings, and pricing are preserved. You will be prompted to load them upon re-opening the RFQ in your module.
"""
        
        composer = EmailComposerDialog(
            self,
            sender_name=requested_by,
            sender_email=sender_email,
            recipient_name=target_to_names,
            recipient_email=target_to_emails,
            subject=subject,
            body_template=body_template,
            default_cc=target_cc_emails,
            available_recipients=available_recipients
        )
        self.winfo_toplevel().wait_window(composer)
        if composer.result:
            res_dict = composer.result
            to_emails = res_dict.get("to_emails", target_to_emails)
            cc_emails = res_dict.get("cc_emails", target_cc_emails)
            comments = res_dict.get("comments", "")
            custom_subject = res_dict.get("subject", subject)

            res = request_revert(rfq_id, customer, target_stage_code, comments, requested_by, self.bom_data_dir)
            success = res[0] if isinstance(res, tuple) else bool(res)
            if success:
                send_revert_email(
                    recipients=to_emails if to_emails else target_to_emails,
                    rfq_id=rfq_id,
                    customer=customer,
                    from_stage=stage_clean,
                    to_stage=target_stage_code,
                    reason=comments,
                    requested_by=requested_by,
                    cc_recipients=cc_emails,
                    subject=custom_subject
                )
                messagebox.showinfo("Success", f"Revert request submitted successfully back to {target_stage_name} stage.", parent=self)
                self.load_data()

    def undo_revert_workflow(self):
        sel = self.tree.selection()
        if not sel:
            return
        item_vals = self.tree.item(sel[0], "values")
        rfq_id = item_vals[0]
        customer = item_vals[1]
        
        from revert_workflow import undo_revert
        top_win = self.winfo_toplevel()
        user = getattr(top_win, "user_name", getattr(top_win, "username", "Module User"))
        res = undo_revert(rfq_id, customer, user, self.bom_data_dir)
        success = res[0] if isinstance(res, tuple) else bool(res)
        if success:
            messagebox.showinfo("Success", "Revert request successfully cancelled and reverted back to original workflow stage.", parent=self)
            self.load_data()

    def show_revert_history(self):
        sel = self.tree.selection()
        if not sel:
            return
        item_vals = self.tree.item(sel[0], "values")
        rfq_id = item_vals[0]
        customer = item_vals[1]
        
        cust_folder = customer.replace(" ", "_")
        bom_filepath = os.path.normpath(os.path.join(self.bom_data_dir, cust_folder, f"{rfq_id.replace(' ', '_')}.json"))
        if os.path.exists(bom_filepath):
            try:
                with open(bom_filepath, 'r', encoding='utf-8-sig') as f:
                    bdata = json.load(f)
                history_data = bdata.get("revert_history", [])
                dlg = RevertHistoryDialog(self, rfq_id, history_data)
                self.winfo_toplevel().wait_window(dlg)
            except Exception as e:
                messagebox.showerror("Error", f"Could not read revert history:\n{e}", parent=self)

    def query_pic_workflow(self):
        sel = self.tree.selection()
        if not sel:
            return
        item_vals = self.tree.item(sel[0], "values")
        rfq_id = item_vals[0]
        customer = item_vals[1]
        stage_name = item_vals[3]
        
        STAGE_NAMES_TO_CODES = {
            "BOM Verification": "pending_bom",
            "Pending Sourcing & Cycle Time": "pending_sourcing_and_cycle_time",
            "Pending Sourcing (Cycle Time Done)": "pending_sourcing_and_cycle_time",
            "Pending Cycle Time (Sourcing Done)": "pending_sourcing_and_cycle_time",
            "Pending Costing": "pending_costing",
            "Pending NPI": "pending_npi",
            "Pending WI": "pending_wi",
            "Completed": "completed"
        }
        clean_stage = stage_name.replace("Revert Pending -> ", "").strip()
        stage_code = STAGE_NAMES_TO_CODES.get(clean_stage, "pending_bom")

        STAGE_CODE_TO_COL_IDX = {
            "pending_bom": 8,
            "pending_sourcing_and_cycle_time": 9,
            "pending_sourcing": 9,
            "pending_cycle_time": 10,
            "pending_costing": 11,
            "pending_npi": 12,
            "pending_wi": 13
        }

        # 1. Read assigned TO PIC(s) for the current stage from treeview row or project file
        row_pic_str = ""
        col_idx = STAGE_CODE_TO_COL_IDX.get(stage_code)
        if col_idx is not None and len(item_vals) > col_idx:
            row_pic_str = item_vals[col_idx]

        target_to_names = []
        if row_pic_str and row_pic_str != "-":
            target_to_names = [p.strip() for p in row_pic_str.split(",") if p.strip() and p.strip() != "-"]

        # Fallback to project file directly if row_pic_str was empty or "-"
        if not target_to_names and hasattr(self, 'bom_data_dir') and self.bom_data_dir:
            cust_folder = customer.replace(" ", "_")
            bom_filepath = os.path.normpath(os.path.join(self.bom_data_dir, cust_folder, f"{rfq_id.replace(' ', '_')}.json"))
            if os.path.exists(bom_filepath):
                try:
                    with open(bom_filepath, 'r', encoding='utf-8') as f:
                        pdata = json.load(f)
                    pic_val = (
                        pdata.get(f"{stage_code}_assigned_by") or
                        pdata.get(f"{stage_code}_dispatched_by") or
                        pdata.get("dispatched_by")
                    )
                    if pic_val:
                        target_to_names = [p.strip() for p in str(pic_val).split(",") if p.strip()]
                except Exception as ex:
                    print(f"Error loading project file for query: {ex}")

        from revert_workflow import get_system_pics, get_user_directory, get_user_email, send_stuck_query_email, EmailComposerDialog, get_smtp_settings

        users = self.get_user_directory() if hasattr(self, 'get_user_directory') else get_user_directory()
        available_recipients = {name: info.get("email", "") for name, info in users.items()}

        pics_config = get_system_pics(stage_code)
        if not target_to_names:
            target_to_names = pics_config.get("to", [])

        target_cc_names = pics_config.get("cc", [])

        target_to_emails = [available_recipients.get(n, get_user_email(n)) for n in target_to_names]
        target_cc_emails = [available_recipients.get(n, get_user_email(n)) for n in target_cc_names]

        top_win = self.winfo_toplevel()
        sender_name = getattr(self, "user_name", getattr(self, "username", getattr(top_win, "user_name", getattr(top_win, "username", "Module User"))))
        
        _, _, system_sender_email, _ = get_smtp_settings()
        sender_email = system_sender_email or available_recipients.get(sender_name, get_user_email(sender_name))
        user_email = available_recipients.get(sender_name, get_user_email(sender_name))
        if user_email and user_email != system_sender_email and user_email not in target_cc_emails:
            target_cc_emails.append(user_email)

        subject = f"[ContinuumX] Stuck Stage Query — RFQ {rfq_id} ({customer}) — Action Required"
        body_template = """Dear {recipient},

An inquiry has been made regarding the pending project currently stuck at your stage:

RFQ Number: """ + rfq_id + """
Customer: """ + customer + """
Current Stage: """ + stage_name + """
Queried By: """ + sender_name + """

Query / Comments:
{comments}

Please review the status and proceed with the necessary actions.
"""
        
        composer = EmailComposerDialog(
            self,
            sender_name=sender_name,
            sender_email=sender_email,
            recipient_name=target_to_names,
            recipient_email=target_to_emails,
            subject=subject,
            body_template=body_template,
            default_cc=target_cc_names,
            available_recipients=available_recipients
        )
        self.winfo_toplevel().wait_window(composer)

        if composer.result:
            res_dict = composer.result
            to_emails = res_dict.get("to_emails", target_to_emails)
            cc_emails = res_dict.get("cc_emails", target_cc_emails)
            comments = res_dict.get("comments", "")
            custom_subject = res_dict.get("subject", subject)

            recip_display = ", ".join(to_emails) if to_emails else "PIC"
            send_stuck_query_email(
                recipients=to_emails,
                rfq_id=rfq_id,
                customer=customer,
                stage_name=stage_name,
                query_text=comments,
                requested_by=sender_name,
                cc_recipients=cc_emails
            )
            messagebox.showinfo("Success", f"Stuck stage query sent successfully to '{recip_display}'!", parent=self)


class RevertTargetStageSelectorDialog(tk.Toplevel):
    def __init__(self, parent_widget, current_stage_name, module_context=None):
        super().__init__(parent_widget)
        self.title("Select Revert Target Stage")
        self.geometry("450x220")
        self.configure(bg="#EBF8FF")
        self.transient(parent_widget)
        self.grab_set()
        
        self.selected_stage_code = None
        self.selected_stage_name = None
        
        # Center dialog
        self.update_idletasks()
        width = 450
        height = 220
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")
        
        tk.Label(self, text="🔄 Select Stage to Revert To", font=("Segoe UI", 12, "bold"), fg="#1A365D", bg="#EBF8FF").pack(pady=(15, 10))
        tk.Label(self, text=f"Current Stage: {current_stage_name}", font=("Segoe UI", 10, "bold"), fg="#4A5568", bg="#EBF8FF").pack(pady=2)
        
        stages_order = [
            ("pending_bom", "BOM Verification"),
            ("pending_sourcing_and_cycle_time", "Pending Sourcing & Cycle Time"),
            ("pending_costing", "Pending Costing"),
            ("pending_npi", "Pending NPI"),
            ("pending_wi", "Pending WI")
        ]
        
        current_idx = -1
        for i, (code, name) in enumerate(stages_order):
            if code == current_stage_name or name.lower() in current_stage_name.lower():
                current_idx = i
                break
        if current_idx == -1:
            if "sourcing" in current_stage_name.lower() or "cycle time" in current_stage_name.lower():
                current_idx = 1
            elif "costing" in current_stage_name.lower():
                current_idx = 2
            elif "npi" in current_stage_name.lower():
                current_idx = 3
            elif "wi" in current_stage_name.lower():
                current_idx = 4
            elif "completed" in current_stage_name.lower():
                current_idx = 5

        self.available_stages = []
        if current_idx > 0:
            for i in range(current_idx):
                self.available_stages.append(stages_order[i])
        else:
            self.available_stages = [("pending_bom", "BOM Verification")]
            
        stage_display_names = [name for _, name in self.available_stages]
        
        self.stage_var = tk.StringVar()
        self.cb_stage = ttk.Combobox(self, textvariable=self.stage_var, values=stage_display_names, state="readonly", width=45, font=("Segoe UI", 10))
        self.cb_stage.pack(padx=20, pady=10)
        if stage_display_names:
            self.cb_stage.current(len(stage_display_names) - 1)
            
        btn_frame = tk.Frame(self, bg="#EBF8FF")
        btn_frame.pack(fill="x", side="bottom", pady=15, padx=20)
        
        tk.Button(btn_frame, text="Cancel", command=self.destroy, font=("Segoe UI", 10, "bold"), bg="#E2E8F0").pack(side="left")
        tk.Button(btn_frame, text="Next ➡️", command=self.on_proceed, font=("Segoe UI", 10, "bold"), bg="#2B6CB0", fg="white").pack(side="right")
        
    def on_proceed(self):
        val = self.stage_var.get()
        if not val:
            messagebox.showwarning("Selection Required", "Please select a target stage.", parent=self)
            return
        for code, name in self.available_stages:
            if name == val:
                self.selected_stage_code = code
                self.selected_stage_name = name
                break
        self.destroy()


class RevertHistoryDialog(tk.Toplevel):
    def __init__(self, parent, rfq_id, history_data):
        super().__init__(parent)
        self.title(f"Revert History Logs - RFQ {rfq_id}")
        self.geometry("780x420")
        self.configure(bg="#EBF8FF")
        self.transient(parent)
        self.grab_set()
        
        # Center dialog
        self.update_idletasks()
        width = 780
        height = 420
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")
        
        tk.Label(self, text=f"📜 Revert History Log for RFQ {rfq_id}", font=("Segoe UI", 12, "bold"), fg="#1A365D", bg="#EBF8FF").pack(pady=12)
        
        tbl_frame = tk.Frame(self)
        tbl_frame.pack(fill="both", expand=True, padx=20, pady=(5, 15))
        
        cols = ("Timestamp", "Requested By", "From Stage", "To Stage", "Reason")
        tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=10)
        col_widths = {"Timestamp": 160, "Requested By": 120, "From Stage": 130, "To Stage": 130, "Reason": 220}
        
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=col_widths.get(col, 150), anchor="w")
            
        tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(tbl_frame, orient="vertical", command=tree.yview)
        tree.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        
        stage_names_map = {
            "pending_bom": "BOM Verification",
            "pending_sourcing_and_cycle_time": "Sourcing & Cycle Time",
            "pending_costing": "Costing",
            "pending_npi": "NPI Verification",
            "pending_wi": "Work Instruction (WI)",
            "completed": "Completed"
        }
        
        sorted_history = list(history_data)
        try:
            sorted_history.sort(key=lambda x: datetime.strptime(x.get("timestamp", ""), "%Y-%m-%d %I:%M:%S %p"), reverse=True)
        except Exception:
            pass
            
        for entry in sorted_history:
            ts = entry.get("timestamp", "")
            req_by = entry.get("requested_by", "")
            from_code = entry.get("from_stage", "")
            to_code = entry.get("to_stage", "")
            reason = entry.get("reason", "")
            
            from_name = stage_names_map.get(from_code, from_code)
            to_name = stage_names_map.get(to_code, to_code)
            
            tag = "undo" if entry.get("is_undo", False) else "revert"
            
            tree.insert("", "end", values=(ts, req_by, from_name, to_name, reason), tags=(tag,))
            
        tree.tag_configure("revert", background="#fff5f5")
        tree.tag_configure("undo", background="#f0fff4")
        
        tk.Button(self, text="Close", command=self.destroy, width=12, font=("Segoe UI", 10, "bold")).pack(pady=10)


def style_dialog_button(btn, bg_color="#1A365D", fg_color="white", active_bg="#0077B6"):
    btn.configure(
        bg=bg_color,
        fg=fg_color,
        activebackground=active_bg,
        activeforeground=fg_color,
        font=("Segoe UI", 9, "bold"),
        bd=0,
        relief="flat",
        cursor="hand2",
        padx=12,
        pady=5
    )
    def on_enter(e):
        if btn.cget("state") != "disabled":
            btn.configure(bg=active_bg)
    def on_leave(e):
        if btn.cget("state") != "disabled":
            btn.configure(bg=bg_color)
    btn.bind("<Enter>", on_enter, add="+")
    btn.bind("<Leave>", on_leave, add="+")


class MultiValueInputDialog(tk.Toplevel):
    def __init__(self, master, title, initial_values=None, available_options=None):
        super().__init__(master)
        self.title(title)
        self.resizable(True, True)
        self.configure(bg="#EBF8FF")
        self.transient(master)
        self.grab_set()
        
        self.initial_values = initial_values or []
        self.available_options = available_options or []
        self.result = None
        
        self._build_ui()
        
        # Set geometry AFTER widgets are built so Tkinter doesn't shrink to minimum
        self.update_idletasks()
        w = 750
        h = 500
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        
    def _build_ui(self):
        # Dialog buttons frame — packed first at bottom so it stays fixed
        btn_frame = tk.Frame(self, bg="#EBF8FF", padx=15, pady=10)
        btn_frame.pack(fill="x", side="bottom")
        
        btn_cancel = tk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=12)
        btn_cancel.pack(side="left")
        btn_clear = tk.Button(btn_frame, text="Clear", command=self._on_clear, width=12)
        btn_clear.pack(side="left", padx=10)
        btn_confirm = tk.Button(btn_frame, text="Confirm", command=self._on_confirm, width=14)
        btn_confirm.pack(side="right")
        
        style_dialog_button(btn_cancel, bg_color="#E2E8F0", fg_color="#2D3748", active_bg="#CBD5E0")
        style_dialog_button(btn_clear, bg_color="#E2E8F0", fg_color="#2D3748", active_bg="#CBD5E0")
        style_dialog_button(btn_confirm, bg_color="#1A365D")

        split_frame = tk.Frame(self, bg="#EBF8FF", padx=15, pady=12)
        split_frame.pack(fill="both", expand=True)
        
        # LEFT PANE: Unique options listbox
        left_frame = tk.LabelFrame(split_frame, text="Available Values", font=("Segoe UI", 11, "bold"), fg="#1A365D", bg="#EBF8FF", padx=10, pady=8)
        left_frame.pack(side="left", fill="both", expand=True)
        
        search_frame = tk.Frame(left_frame, bg="#EBF8FF")
        search_frame.pack(fill="x", pady=(0, 6))
        tk.Label(search_frame, text="Search:", font=("Segoe UI", 11), bg="#EBF8FF", fg="#1A365D").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Segoe UI", 11))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.search_var.trace_add("write", lambda *args: self._filter_options())
        
        list_container = tk.Frame(left_frame, bg="#EBF8FF")
        list_container.pack(fill="both", expand=True, pady=5)
        
        self.listbox = tk.Listbox(list_container, selectmode="extended", font=("Segoe UI", 11), bd=1, relief="solid")
        list_scroll_y = ttk.Scrollbar(list_container, orient="vertical", command=self.listbox.yview)
        list_scroll_x = ttk.Scrollbar(list_container, orient="horizontal", command=self.listbox.xview)
        self.listbox.configure(yscrollcommand=list_scroll_y.set, xscrollcommand=list_scroll_x.set)
        list_scroll_y.pack(side="right", fill="y")
        list_scroll_x.pack(side="bottom", fill="x")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", self._add_selected)
        
        for opt in self.available_options:
            self.listbox.insert(tk.END, opt)
            
        btn_add_sel = tk.Button(left_frame, text="Add Selected ➡️", command=self._add_selected)
        btn_add_sel.pack(anchor="e", pady=(6, 0))
        style_dialog_button(btn_add_sel, bg_color="#2C5282")
        
        # RIGHT PANE: Current filter values text area
        right_frame = tk.LabelFrame(split_frame, text="Filter List (One per line)", font=("Segoe UI", 11, "bold"), fg="#1A365D", bg="#EBF8FF", padx=10, pady=8)
        right_frame.pack(side="right", fill="both", expand=True, padx=(12, 0))
        
        text_container = tk.Frame(right_frame, bg="#EBF8FF")
        text_container.pack(fill="both", expand=True, pady=5)
        
        self.text_area = tk.Text(text_container, font=("Segoe UI", 11), bd=1, relief="solid")
        text_scroll = ttk.Scrollbar(text_container, orient="vertical", command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=text_scroll.set)
        self.text_area.pack(side="left", fill="both", expand=True)
        text_scroll.pack(side="right", fill="y")
        
        if self.initial_values:
            self.text_area.insert("1.0", "\n".join(self.initial_values))
        
    def _filter_options(self):
        term = self.search_var.get().lower()
        self.listbox.delete(0, tk.END)
        for opt in self.available_options:
            if term in str(opt).lower():
                self.listbox.insert(tk.END, opt)
                
    def _add_selected(self, event=None):
        indices = self.listbox.curselection()
        if not indices:
            return
        current_text = self.text_area.get("1.0", "end-1c")
        current_lines = [line.strip() for line in current_text.split("\n") if line.strip()]
        current_set = set(current_lines)
        added = False
        for idx in indices:
            val = self.listbox.get(idx)
            if val not in current_set:
                current_lines.append(val)
                current_set.add(val)
                added = True
        if added:
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", "\n".join(current_lines))
            
    def _on_clear(self):
        self.text_area.delete("1.0", "end")
        
    def _on_confirm(self):
        content = self.text_area.get("1.0", "end-1c")
        self.result = [line.strip() for line in content.split("\n") if line.strip()]
        self.destroy()
        
    def _on_cancel(self):
        self.result = None
        self.destroy()


class ProjectManagementFilterDialog(tk.Toplevel):
    def __init__(self, master, initial_filter=None, unique_options=None):
        super().__init__(master)
        self.title("Filter Project Management Records")
        self.resizable(True, True)
        self.configure(bg="#EBF8FF")
        self.transient(master)
        self.grab_set()
        
        initial_filter = initial_filter or {}
        unique_options = unique_options or {}
        self.unique_options = unique_options
        
        self.f_rfq = initial_filter.get('rfq', [])
        self.f_customer = initial_filter.get('customer', [])
        self.f_assembly = initial_filter.get('assembly', [])
        self.f_stage = initial_filter.get('stage', [])
        self.f_bom_date = initial_filter.get('bom_date', [])
        self.f_last_update = initial_filter.get('last_update', [])
        self.f_user = initial_filter.get('user', [])
        
        self.v_rfq = tk.StringVar(value=self._fmt_val(self.f_rfq))
        self.v_customer = tk.StringVar(value=self._fmt_val(self.f_customer))
        self.v_assembly = tk.StringVar(value=self._fmt_val(self.f_assembly))
        self.v_stage = tk.StringVar(value=self._fmt_val(self.f_stage))
        self.v_bom_date = tk.StringVar(value=self._fmt_val(self.f_bom_date))
        self.v_last_update = tk.StringVar(value=self._fmt_val(self.f_last_update))
        self.v_user = tk.StringVar(value=self._fmt_val(self.f_user))
        
        self.result = None
        
        self._build_ui()
        self.update_idletasks()
        w = 620
        h = 500
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        # self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(580, 480)
        
        self._wait_var = tk.IntVar()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.wait_variable(self._wait_var)
        
    def _fmt_val(self, vals):
        if not vals: return ""
        if len(vals) == 1: return vals[0]
        return f"<{len(vals)} values selected>"
        
    def _build_ui(self):
        main_frame = tk.Frame(self, bg="#EBF8FF", padx=20, pady=12)
        main_frame.pack(fill="both", expand=True)
        
        tk.Label(main_frame, text="Search Criteria", font=("Segoe UI", 13, "bold"), fg="#1A365D", bg="#EBF8FF").pack(anchor="w", pady=(0, 8))
        
        self._add_row(main_frame, "RFQ ID:", self.v_rfq, "rfq")
        self._add_row(main_frame, "Customer:", self.v_customer, "customer")
        self._add_row(main_frame, "Assembly:", self.v_assembly, "assembly")
        self._add_row(main_frame, "Current Stage:", self.v_stage, "stage")
        self._add_row(main_frame, "BOM Creation Date:", self.v_bom_date, "bom_date")
        self._add_row(main_frame, "Last Update Date:", self.v_last_update, "last_update")
        self._add_row(main_frame, "Assigned User:", self.v_user, "user")
        
        tk.Label(main_frame, text="* Use the ⫘ button next to fields to input multiple values.", font=("Segoe UI", 9, "italic"), fg="#555", bg="#EBF8FF").pack(anchor="w", pady=(8, 0))
        
        btn_frame = tk.Frame(main_frame, bg="#EBF8FF")
        btn_frame.pack(fill="x", pady=(10, 0))
        
        btn_cancel = tk.Button(btn_frame, text="Cancel", command=self._on_cancel, width=10)
        btn_cancel.pack(side="left")
        btn_clear = tk.Button(btn_frame, text="Clear All", command=self._on_clear_all, width=10)
        btn_clear.pack(side="left", padx=10)
        btn_exec = tk.Button(btn_frame, text="Execute Filter", command=self._on_execute, width=15)
        btn_exec.pack(side="right")
        
        style_dialog_button(btn_cancel, bg_color="#E2E8F0", fg_color="#2D3748", active_bg="#CBD5E0")
        style_dialog_button(btn_clear, bg_color="#E2E8F0", fg_color="#2D3748", active_bg="#CBD5E0")
        style_dialog_button(btn_exec, bg_color="#1A365D")
        
        # Return key executes filter
        self.bind("<Return>", lambda e: self._on_execute())
        
    def _add_row(self, parent, label, var, key):
        row = tk.Frame(parent, bg="#EBF8FF")
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, width=20, anchor="w", font=("Segoe UI", 11, "bold"), fg="#1A365D", bg="#EBF8FF").pack(side="left")
        ent = tk.Entry(row, textvariable=var, font=("Segoe UI", 11))
        ent.pack(side="left", fill="x", expand=True, padx=5)
        tk.Button(row, text="⫘", command=lambda: self._multi_input(key, var), width=3, bg="#EBF8FF", cursor="hand2", font=("Segoe UI", 11)).pack(side="left")
        
    def _multi_input(self, key, var):
        curr_vals = getattr(self, f"f_{key}")
        if not curr_vals and var.get() and not var.get().startswith("<"):
            curr_vals = [var.get()]
        options = self.unique_options.get(key, [])
        dialog = MultiValueInputDialog(self, f"Multi-Selection for {key.replace('_', ' ').title()}", curr_vals, available_options=options)
        self.wait_window(dialog)
        if dialog.result is not None:
            setattr(self, f"f_{key}", dialog.result)
            var.set(self._fmt_val(dialog.result))
            
        else:
            self.filter_criteria = None
            if hasattr(self, 'populate_tree'):
                self.populate_tree()
            elif hasattr(self, 'refresh_projects'):
                self.refresh_projects()
    def _on_clear_all(self):
        for k in ['rfq', 'customer', 'assembly', 'stage', 'bom_date', 'last_update', 'user']:
            getattr(self, f"v_{k}").set("")
            setattr(self, f"f_{k}", [])
            
    def _on_execute(self):
        # Update raw filter lists with single values from entry boxes if not multi-value formatted
        for k in ['rfq', 'customer', 'assembly', 'stage', 'bom_date', 'last_update', 'user']:
            val = getattr(self, f"v_{k}").get().strip()
            if val and not val.startswith("<"):
                setattr(self, f"f_{k}", [val])
            elif not val:
                setattr(self, f"f_{k}", [])
                
        self.result = {
            'rfq': getattr(self, "f_rfq"),
            'customer': getattr(self, "f_customer"),
            'assembly': getattr(self, "f_assembly"),
            'stage': getattr(self, "f_stage"),
            'bom_date': getattr(self, "f_bom_date"),
            'last_update': getattr(self, "f_last_update"),
            'user': getattr(self, "f_user"),
        }
        self._wait_var.set(1)
        self.destroy()
        
    def _on_cancel(self):
        self.result = None
        self._wait_var.set(1)
        self.destroy()
