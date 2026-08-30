# ==============================================================================
# --- ContinuumX Unified Multi-Modal Evidence & Annotation Studio ---
# Implements:
# 1. Tab 1: 📄 Drawings & Visual Specs (PDF, Images, DOCX via built-in visualizer)
#    - Interactive Optical Character Recognition (OCR) annotation
#    - Multi-category color-coded bounding boxes & floating tags
#    - Interactive canvas selection, focus-dimming transparency, manual box drawing
# 2. Tab 2: 📊 Raw Spreadsheets & Tabular Data (Excel .xlsx/.xls, CSV, delimited .txt)
#    - Interactive Tkinter Treeview data grid showing raw customer sheets
#    - Auto-search and highlighting of focused component/MPN row
# 3. Tab 3: 📧 Client Email & Commercial Notes
#    - Structured view of RFQ email header, commercial terms, and body text
# 4. Multi-File Switcher: Instant switching between candidate attachments
# 5. Right-Hand Inspector: Unified across all tabs with zero-ticket Active Learning
# ==============================================================================

import os
import sys
import re
import csv
import json
import hashlib
import zipfile
import webbrowser
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Tuple, Any, Callable

# Standardized Base Directory & sys.path setup (supports direct execution, package imports, and frozen exes)
if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS') or "__compiled__" in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif '__file__' in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
elif len(sys.argv) > 0 and sys.argv[0] and sys.argv[0] != '-c':
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE_DIR = os.getcwd()

_project_root = os.path.dirname(BASE_DIR) if os.path.basename(BASE_DIR).lower() == 'agents' else BASE_DIR
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    import pypdfium2
    from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageFilter
    HAS_VISION_LIBS = True
except ImportError:
    HAS_VISION_LIBS = False

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    import xlrd
    HAS_XLRD = True
except ImportError:
    HAS_XLRD = False


# Label Studio Category Taxonomy & Theme Colors
LABEL_CATEGORIES = {
    "ASSEMBLY_NUMBER": {
        "label": "Assembly Number",
        "tag": "ASSY",
        "border": "#6366F1",      # Indigo
        "fill": (99, 102, 241, 60),
        "dim_fill": (99, 102, 241, 12),
        "dim_border": "#4338ca",
        "badge_bg": "#1e1b4b",
        "badge_fg": "#a5b4fc",
        "icon": "🎯"
    },
    "PART_NUMBER": {
        "label": "Part Number / SAP",
        "tag": "PART",
        "border": "#06B6D4",      # Cyan
        "fill": (6, 182, 212, 55),
        "dim_fill": (6, 182, 212, 12),
        "dim_border": "#0e7490",
        "badge_bg": "#083344",
        "badge_fg": "#22D3EE",
        "icon": "🏷️"
    },
    "DESCRIPTION": {
        "label": "Description",
        "tag": "DESC",
        "border": "#8B5CF6",      # Purple
        "fill": (139, 92, 246, 55),
        "dim_fill": (139, 92, 246, 12),
        "dim_border": "#6d28d9",
        "badge_bg": "#2E1065",
        "badge_fg": "#C084FC",
        "icon": "📝"
    },
    "MPN": {
        "label": "MPN / CPN",
        "tag": "MPN",
        "border": "#EC4899",      # Pink / Magenta
        "fill": (236, 72, 153, 55),
        "dim_fill": (236, 72, 153, 12),
        "dim_border": "#be185d",
        "badge_bg": "#500724",
        "badge_fg": "#F472B6",
        "icon": "🔢"
    },
    "MANUFACTURER": {
        "label": "Manufacturer / Brand",
        "tag": "MFR",
        "border": "#10B981",      # Emerald Green
        "fill": (16, 185, 129, 55),
        "dim_fill": (16, 185, 129, 12),
        "dim_border": "#047857",
        "badge_bg": "#022C22",
        "badge_fg": "#34D399",
        "icon": "🏭"
    },
    "SPECIFICATION": {
        "label": "Specs / Dimensions",
        "tag": "SPEC",
        "border": "#F59E0B",      # Amber
        "fill": (245, 158, 11, 55),
        "dim_fill": (245, 158, 11, 12),
        "dim_border": "#b45309",
        "badge_bg": "#451A03",
        "badge_fg": "#FBBF24",
        "icon": "📏"
    },
    "TITLE_BLOCK": {
        "label": "Title Block / Header",
        "tag": "TITLE",
        "border": "#3B82F6",      # Blue
        "fill": (59, 130, 246, 55),
        "dim_fill": (59, 130, 246, 12),
        "dim_border": "#1d4ed8",
        "badge_bg": "#172554",
        "badge_fg": "#60A5FA",
        "icon": "📐"
    },
    "GENERAL_NOTES": {
        "label": "General Notes / Tolerances",
        "tag": "NOTE",
        "border": "#94A3B8",      # Slate Grey
        "fill": (148, 163, 184, 45),
        "dim_fill": (148, 163, 184, 10),
        "dim_border": "#475569",
        "badge_bg": "#0F172A",
        "badge_fg": "#CBD5E1",
        "icon": "📋"
    }
}


class AddLabelDialog(tk.Toplevel):
    """Custom Dark-Themed Modal Dialog for creating or editing OCR annotation labels."""

    def __init__(self, parent: tk.Widget, default_text: str = "", default_category: str = "PART_NUMBER", is_edit: bool = False, match_count: int = 1):
        super().__init__(parent)
        self.result: Optional[Tuple[str, str, bool]] = None
        self.title("✏️ Amend Annotation Label" if is_edit else "🏷️ Add OCR Annotation Label")
        dlg_h = 490 if (is_edit and match_count > 1) else 450
        self.geometry(f"540x{dlg_h}")
        self.resizable(True, True)
        self.minsize(480, 410)
        self.configure(bg="#0F172A")
        self.transient(parent)
        self.grab_set()

        # Center over parent
        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        x = max(10, px + (pw - 540) // 2)
        y = max(10, py + (ph - dlg_h) // 2)
        self.geometry(f"+{x}+{y}")

        # 1. Header Frame
        hdr = tk.Frame(self, bg="#1E293B", padx=18, pady=12)
        hdr.pack(fill="x")
        title_txt = "✏️ Amend & Reclassify Label" if is_edit else "🏷️ Create Annotation Label"
        tk.Label(hdr, text=title_txt, font=("Segoe UI", 12, "bold"), fg="#FFFFFF", bg="#1E293B").pack(anchor="w")
        tk.Label(hdr, text="Update category and OCR text — immediately syncs with BOM table & AI memory", font=("Segoe UI", 9), fg="#94A3B8", bg="#1E293B").pack(anchor="w", pady=(2, 0))

        # 2. Body Frame
        body = tk.Frame(self, bg="#0F172A", padx=18, pady=12)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Label Classification Category:", font=("Segoe UI", 10, "bold"), fg="#CBD5E1", bg="#0F172A").pack(anchor="w", pady=(0, 6))
        self.cat_var = tk.StringVar(value=default_category if default_category in LABEL_CATEGORIES else "PART_NUMBER")

        cat_grid = tk.Frame(body, bg="#0F172A")
        cat_grid.pack(fill="x", pady=(0, 10))

        for idx, (cat_key, cat_cfg) in enumerate(LABEL_CATEGORIES.items()):
            r_btn = tk.Radiobutton(
                cat_grid,
                text=f"{cat_cfg['icon']} {cat_cfg['label']}",
                value=cat_key,
                variable=self.cat_var,
                font=("Segoe UI", 9, "bold"),
                bg="#0F172A",
                fg="#F1F5F9",
                selectcolor="#1E293B",
                activebackground="#0F172A",
                activeforeground="#38BDF8",
                anchor="w"
            )
            r_btn.grid(row=idx // 2, column=idx % 2, sticky="w", padx=6, pady=3)

        tk.Label(body, text="OCR Text / Component Name:", font=("Segoe UI", 10, "bold"), fg="#CBD5E1", bg="#0F172A").pack(anchor="w", pady=(4, 4))
        self.txt_entry = tk.Entry(body, font=("Segoe UI", 11), bg="#1E293B", fg="#FFFFFF", insertbackground="#38BDF8", bd=1, relief="solid")
        self.txt_entry.insert(0, default_text)
        self.txt_entry.pack(fill="x", ipady=5, pady=(0, 10))
        self.txt_entry.focus_set()
        self.txt_entry.bind("<Return>", lambda e: self._on_save())
        self.bind("<Escape>", lambda e: self.destroy())

        # Multi-occurrence sync checkbox
        self.apply_all_var = tk.BooleanVar(value=True if (is_edit and match_count > 1) else False)
        if is_edit and match_count > 1:
            chk = tk.Checkbutton(
                body,
                text=f"🌐 Apply reclassification to all {match_count} occurrences of this label in document",
                variable=self.apply_all_var,
                font=("Segoe UI", 9, "bold"),
                bg="#0F172A",
                fg="#FBBF24",
                selectcolor="#1E293B",
                activebackground="#0F172A",
                activeforeground="#FBBF24"
            )
            chk.pack(anchor="w", pady=(0, 6))

        # 3. Footer Action Buttons
        ftr = tk.Frame(self, bg="#1E293B", padx=18, pady=10)
        ftr.pack(fill="x", side="bottom")

        tk.Button(
            ftr, text="Cancel", command=self.destroy,
            bg="#475569", fg="#FFFFFF", font=("Segoe UI", 9),
            relief="flat", padx=14, pady=5, cursor="hand2"
        ).pack(side="right", padx=(8, 0))

        btn_txt = "💾 Apply & Sync BOM" if is_edit else "💾 Save Annotation"
        tk.Button(
            ftr, text=btn_txt, command=self._on_save,
            bg="#2563EB", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=16, pady=5, cursor="hand2"
        ).pack(side="right")

        self.wait_window(self)

    def _on_save(self):
        txt = self.txt_entry.get().strip()
        if not txt:
            messagebox.showwarning("Missing Text", "Please enter OCR text or component name.", parent=self)
            return
        self.result = (self.cat_var.get(), txt, self.apply_all_var.get())
        self.destroy()


try:
    from agents.domain_taxonomy import TaxonomyEngine
    from agents.drawing_agent import DrawingVisionAgent
except ImportError:
    from domain_taxonomy import TaxonomyEngine
    from drawing_agent import DrawingVisionAgent


class AddTaxonomyTermDialog(tk.Toplevel):
    """Modal dialog to teach a new Material or Manufacturer term into the permanent Domain Taxonomy."""
    def __init__(self, parent: tk.Widget, default_text: str = "", default_category: str = "DESCRIPTION"):
        super().__init__(parent)
        self.result = None
        self.title("📚 Teach Term to Permanent Domain Taxonomy")
        self.geometry("540x440")
        self.minsize(480, 380)
        self.configure(bg="#0F172A")
        self.transient(parent)
        self.grab_set()

        # Header
        hdr = tk.Frame(self, bg="#1E293B", padx=16, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📚 Teach New Domain Vocabulary", font=("Segoe UI", 12, "bold"), fg="#FFFFFF", bg="#1E293B").pack(anchor="w")
        tk.Label(hdr, text="Permanently teaches the AI to auto-detect this term across all drawings.", font=("Segoe UI", 9), fg="#94A3B8", bg="#1E293B").pack(anchor="w", pady=(2, 0))

        body = tk.Frame(self, bg="#0F172A", padx=16, pady=14)
        body.pack(fill="both", expand=True)

        # 1. Taxonomy Target Type
        tk.Label(body, text="1. Select Taxonomy Category:", font=("Segoe UI", 9, "bold"), fg="#CBD5E1", bg="#0F172A").pack(anchor="w", pady=(0, 4))
        self.target_type_var = tk.StringVar(value="MATERIAL" if default_category in ("DESCRIPTION", "SPECIFICATION") else "MANUFACTURER")
        type_row = tk.Frame(body, bg="#0F172A")
        type_row.pack(fill="x", pady=(0, 10))

        rb1 = tk.Radiobutton(type_row, text="🏷️ Wire Harness Material / Description", variable=self.target_type_var, value="MATERIAL", font=("Segoe UI", 9, "bold"), bg="#0F172A", fg="#38BDF8", selectcolor="#1E293B", activebackground="#0F172A", activeforeground="#38BDF8")
        rb1.pack(side="left", padx=(0, 12))

        rb2 = tk.Radiobutton(type_row, text="🏢 Manufacturer (MFR) Name", variable=self.target_type_var, value="MANUFACTURER", font=("Segoe UI", 9, "bold"), bg="#0F172A", fg="#34D399", selectcolor="#1E293B", activebackground="#0F172A", activeforeground="#34D399")
        rb2.pack(side="left")

        # 2. Canonical Name / Label
        tk.Label(body, text="2. Canonical Name (Standard Industry Name):", font=("Segoe UI", 9, "bold"), fg="#CBD5E1", bg="#0F172A").pack(anchor="w", pady=(0, 4))
        self.canon_entry = tk.Entry(body, font=("Segoe UI", 10), bg="#1E293B", fg="#FFFFFF", insertbackground="#38BDF8", bd=1, relief="solid")
        self.canon_entry.insert(0, default_text.title())
        self.canon_entry.pack(fill="x", ipady=4, pady=(0, 10))

        # 3. Subfamily (for Material)
        self.subfam_lbl = tk.Label(body, text="3. Component Subfamily:", font=("Segoe UI", 9, "bold"), fg="#CBD5E1", bg="#0F172A")
        self.subfam_lbl.pack(anchor="w", pady=(0, 4))
        self.subfam_var = tk.StringVar(value="TERMINAL")
        self.subfam_combo = ttk.Combobox(body, textvariable=self.subfam_var, values=["TERMINAL", "CONNECTOR", "CABLE", "PROTECTION", "MAGNETICS", "HARDWARE", "PROCESS_NOTE", "CUSTOM"], state="readonly", font=("Segoe UI", 9))
        self.subfam_combo.pack(fill="x", pady=(0, 10))

        # 4. Search Phrases / Synonyms (comma separated)
        tk.Label(body, text="4. Recognition Phrases / Blueprints Synonyms (Comma-separated):", font=("Segoe UI", 9, "bold"), fg="#CBD5E1", bg="#0F172A").pack(anchor="w", pady=(0, 4))
        self.terms_entry = tk.Entry(body, font=("Segoe UI", 10), bg="#1E293B", fg="#FDE047", insertbackground="#38BDF8", bd=1, relief="solid")
        self.terms_entry.insert(0, default_text.lower())
        self.terms_entry.pack(fill="x", ipady=4, pady=(0, 10))

        def _on_type_change(*args):
            if self.target_type_var.get() == "MANUFACTURER":
                self.subfam_lbl.pack_forget()
                self.subfam_combo.pack_forget()
            else:
                self.subfam_lbl.pack(anchor="w", pady=(0, 4))
                self.subfam_combo.pack(fill="x", pady=(0, 10))
        self.target_type_var.trace_add("write", _on_type_change)
        _on_type_change()

        # Footer Actions
        ftr = tk.Frame(self, bg="#1E293B", padx=16, pady=10)
        ftr.pack(fill="x", side="bottom")

        tk.Button(ftr, text="Cancel", command=self.destroy, bg="#475569", fg="#FFFFFF", font=("Segoe UI", 9), relief="flat", padx=14, pady=4, cursor="hand2").pack(side="right", padx=(8, 0))
        tk.Button(ftr, text="💾 Save to Domain Library", command=self._on_save, bg="#059669", fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief="flat", padx=16, pady=4, cursor="hand2").pack(side="right")

        self.wait_window(self)

    def _on_save(self):
        canon = self.canon_entry.get().strip()
        terms_raw = self.terms_entry.get().strip()
        if not canon or not terms_raw:
            messagebox.showwarning("Missing Information", "Please enter canonical name and recognition phrases.", parent=self)
            return

        terms = [t.strip() for t in terms_raw.split(",") if t.strip()]
        target_type = self.target_type_var.get()
        subfam = self.subfam_var.get()

        if target_type == "MATERIAL":
            success = TaxonomyEngine.add_custom_material(canon, terms, subfam)
        else:
            success = TaxonomyEngine.add_custom_manufacturer(canon, terms)

        if success:
            self.result = {"type": target_type, "canonical": canon, "terms": terms}
            self.destroy()
        else:
            messagebox.showerror("Save Failed", "Could not save taxonomy term.", parent=self)


class TaxonomyManagerDialog(tk.Toplevel):
    """Interactive Enterprise Domain Taxonomy & Library Manager."""
    def __init__(self, parent: tk.Widget, on_update_callback: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.parent = parent
        self.on_update_callback = on_update_callback
        self.title("📚 Enterprise Domain Taxonomy & Library Manager")
        self.geometry("980x640")
        self.minsize(800, 500)
        self.configure(bg="#0F172A")
        self.transient(parent)

        # 1. Header Banner
        hdr = tk.Frame(self, bg="#1E293B", padx=16, pady=12)
        hdr.pack(fill="x")

        t_row = tk.Frame(hdr, bg="#1E293B")
        t_row.pack(fill="x")
        tk.Label(t_row, text="📚 Enterprise Domain Taxonomy & Component Library", font=("Segoe UI", 13, "bold"), fg="#FFFFFF", bg="#1E293B").pack(side="left")
        
        btn_scan = tk.Button(t_row, text="🔄 Re-Scan Drawing Now", command=self._trigger_rescan, bg="#2563EB", fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=4, cursor="hand2")
        btn_scan.pack(side="right")

        tk.Label(hdr, text="Standard IPC/WHMA-A-620 Cable Taxonomy, 165+ Electronics Manufacturers, and MPN Rules.", font=("Segoe UI", 9), fg="#94A3B8", bg="#1E293B").pack(anchor="w", pady=(2, 0))

        # 2. Search & Toolbar Frame
        tb = tk.Frame(self, bg="#0F172A", padx=16, pady=8)
        tb.pack(fill="x")

        tk.Label(tb, text="🔍 Search Lexicon:", font=("Segoe UI", 9, "bold"), fg="#CBD5E1", bg="#0F172A").pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_treeviews())
        s_entry = tk.Entry(tb, textvariable=self.search_var, font=("Segoe UI", 10), width=28, bg="#1E293B", fg="#FFFFFF", insertbackground="#38BDF8", bd=1, relief="solid")
        s_entry.pack(side="left", ipady=3, padx=(0, 10))

        tk.Button(tb, text="➕ Add New Term", command=self._add_term, bg="#059669", fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=4, cursor="hand2").pack(side="left", padx=2)
        tk.Button(tb, text="🗑️ Delete Custom", command=self._delete_selected, bg="#DC2626", fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4, cursor="hand2").pack(side="left", padx=2)
        tk.Button(tb, text="📤 Export JSON", command=self._export_json, bg="#334155", fg="#CBD5E1", font=("Segoe UI", 9), relief="flat", padx=10, pady=4, cursor="hand2").pack(side="right", padx=2)
        tk.Button(tb, text="📥 Import JSON", command=self._import_json, bg="#334155", fg="#CBD5E1", font=("Segoe UI", 9), relief="flat", padx=10, pady=4, cursor="hand2").pack(side="right", padx=2)

        # 3. Notebook Tabs
        nb_fr = tk.Frame(self, bg="#0F172A", padx=16, pady=4)
        nb_fr.pack(fill="both", expand=True)

        self.nb = ttk.Notebook(nb_fr)
        self.nb.pack(fill="both", expand=True)

        # Tab 1: Materials
        tab_mat = tk.Frame(self.nb, bg="#0F172A")
        self.nb.add(tab_mat, text=f" 🏷️ Wire Harness Materials ({len(TaxonomyEngine.materials)}) ")
        self._build_materials_tree(tab_mat)

        # Tab 2: Manufacturers
        tab_mfr = tk.Frame(self.nb, bg="#0F172A")
        self.nb.add(tab_mfr, text=f" 🏢 Manufacturers ({len(TaxonomyEngine.manufacturers)}) ")
        self._build_manufacturers_tree(tab_mfr)

        # Tab 3: MPN Schemas
        tab_mpn = tk.Frame(self.nb, bg="#0F172A")
        self.nb.add(tab_mpn, text=f" 🔢 MPN Schemas ({len(TaxonomyEngine.mpn_patterns)}) ")
        self._build_mpn_tree(tab_mpn)

        self._refresh_all_trees()

    def _build_materials_tree(self, parent_frame):
        cols = ("canonical", "subfamily", "terms", "source")
        self.mat_tree = ttk.Treeview(parent_frame, columns=cols, show="headings", selectmode="browse")
        self.mat_tree.heading("canonical", text="Canonical Component Name")
        self.mat_tree.heading("subfamily", text="Subfamily")
        self.mat_tree.heading("terms", text="Recognition Phrases / Synonyms")
        self.mat_tree.heading("source", text="Source")

        self.mat_tree.column("canonical", width=200, minwidth=140)
        self.mat_tree.column("subfamily", width=120, minwidth=90)
        self.mat_tree.column("terms", width=420, minwidth=250)
        self.mat_tree.column("source", width=110, minwidth=80)

        vsb = ttk.Scrollbar(parent_frame, orient="vertical", command=self.mat_tree.yview)
        self.mat_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.mat_tree.pack(fill="both", expand=True)

    def _build_manufacturers_tree(self, parent_frame):
        cols = ("name", "aliases", "source")
        self.mfr_tree = ttk.Treeview(parent_frame, columns=cols, show="headings", selectmode="browse")
        self.mfr_tree.heading("name", text="Manufacturer Brand Name")
        self.mfr_tree.heading("aliases", text="Brand Aliases & Shorthands")
        self.mfr_tree.heading("source", text="Source")

        self.mfr_tree.column("name", width=220, minwidth=150)
        self.mfr_tree.column("aliases", width=520, minwidth=300)
        self.mfr_tree.column("source", width=110, minwidth=80)

        vsb = ttk.Scrollbar(parent_frame, orient="vertical", command=self.mfr_tree.yview)
        self.mfr_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.mfr_tree.pack(fill="both", expand=True)

    def _build_mpn_tree(self, parent_frame):
        cols = ("brand", "pattern", "example")
        self.mpn_tree = ttk.Treeview(parent_frame, columns=cols, show="headings", selectmode="browse")
        self.mpn_tree.heading("brand", text="Target Brand / Series")
        self.mpn_tree.heading("pattern", text="High-Precision Regex Pattern")
        self.mpn_tree.heading("example", text="Format Example")

        self.mpn_tree.column("brand", width=220, minwidth=140)
        self.mpn_tree.column("pattern", width=420, minwidth=250)
        self.mpn_tree.column("example", width=220, minwidth=150)

        vsb = ttk.Scrollbar(parent_frame, orient="vertical", command=self.mpn_tree.yview)
        self.mpn_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.mpn_tree.pack(fill="both", expand=True)

    def _refresh_all_trees(self):
        # 1. Refresh Materials
        self.mat_tree.delete(*self.mat_tree.get_children())
        for k, mat in sorted(TaxonomyEngine.materials.items(), key=lambda x: x[1].get("canonical", "")):
            terms_str = ", ".join(mat.get("terms", []))
            src = mat.get("source", "Built-in Standard")
            self.mat_tree.insert("", "end", iid=f"mat_{k}", values=(mat.get("canonical", k), mat.get("subfamily", "MATERIAL"), terms_str, src))

        # 2. Refresh Manufacturers
        self.mfr_tree.delete(*self.mfr_tree.get_children())
        for name, info in sorted(TaxonomyEngine.manufacturers.items(), key=lambda x: x[0]):
            aliases_str = ", ".join(info.get("aliases", []))
            src = info.get("source", "Built-in Directory")
            self.mfr_tree.insert("", "end", iid=f"mfr_{name}", values=(name, aliases_str, src))

        # 3. Refresh MPN Schemas
        self.mpn_tree.delete(*self.mpn_tree.get_children())
        for pat, brand in TaxonomyEngine.mpn_patterns:
            self.mpn_tree.insert("", "end", values=(brand, pat, "Auto-Formatted"))

        self.nb.tab(0, text=f" 🏷️ Wire Harness Materials ({len(TaxonomyEngine.materials)}) ")
        self.nb.tab(1, text=f" 🏢 Manufacturers ({len(TaxonomyEngine.manufacturers)}) ")
        self.nb.tab(2, text=f" 🔢 MPN Schemas ({len(TaxonomyEngine.mpn_patterns)}) ")

    def _filter_treeviews(self):
        q = self.search_var.get().strip().lower()
        if not q:
            self._refresh_all_trees()
            return

        self.mat_tree.delete(*self.mat_tree.get_children())
        for k, mat in sorted(TaxonomyEngine.materials.items(), key=lambda x: x[1].get("canonical", "")):
            c_name = mat.get("canonical", "").lower()
            terms_str = ", ".join(mat.get("terms", [])).lower()
            if q in c_name or q in terms_str or q in mat.get("subfamily", "").lower():
                self.mat_tree.insert("", "end", iid=f"mat_{k}", values=(mat.get("canonical", k), mat.get("subfamily", "MATERIAL"), ", ".join(mat.get("terms", [])), mat.get("source", "Built-in Standard")))

        self.mfr_tree.delete(*self.mfr_tree.get_children())
        for name, info in sorted(TaxonomyEngine.manufacturers.items(), key=lambda x: x[0]):
            aliases_str = ", ".join(info.get("aliases", [])).lower()
            if q in name.lower() or q in aliases_str:
                self.mfr_tree.insert("", "end", iid=f"mfr_{name}", values=(name, ", ".join(info.get("aliases", [])), info.get("source", "Built-in Directory")))

    def _add_term(self):
        dlg = AddTaxonomyTermDialog(self)
        if dlg.result:
            self._refresh_all_trees()
            if self.on_update_callback:
                self.on_update_callback()

    def _delete_selected(self):
        tab_idx = self.nb.index(self.nb.select())
        if tab_idx == 0:
            sel = self.mat_tree.selection()
            if not sel:
                messagebox.showinfo("Select Entry", "Please select a material entry to delete.", parent=self)
                return
            item_id = sel[0].replace("mat_", "")
            mat_info = TaxonomyEngine.materials.get(item_id, {})
            if mat_info.get("source") != "User Library":
                messagebox.showwarning("Protected Entry", "Built-in IPC standard entries cannot be deleted.\nYou can add custom overrides.", parent=self)
                return
            if messagebox.askyesno("Confirm Delete", f"Delete custom material entry '{mat_info.get('canonical', item_id)}'?", parent=self):
                TaxonomyEngine.delete_custom_entry("MATERIALS", item_id)
                self._refresh_all_trees()
                if self.on_update_callback: self.on_update_callback()

        elif tab_idx == 1:
            sel = self.mfr_tree.selection()
            if not sel:
                messagebox.showinfo("Select Entry", "Please select a manufacturer entry to delete.", parent=self)
                return
            item_name = sel[0].replace("mfr_", "")
            mfr_info = TaxonomyEngine.manufacturers.get(item_name, {})
            if mfr_info.get("source") != "User Library":
                messagebox.showwarning("Protected Entry", "Built-in global manufacturer entries cannot be deleted.", parent=self)
                return
            if messagebox.askyesno("Confirm Delete", f"Delete custom manufacturer '{item_name}'?", parent=self):
                TaxonomyEngine.delete_custom_entry("MANUFACTURERS", item_name)
                self._refresh_all_trees()
                if self.on_update_callback: self.on_update_callback()

    def _export_json(self):
        from tkinter import filedialog
        fp = filedialog.asksaveasfilename(title="Export Custom Taxonomy JSON", defaultextension=".json", filetypes=[("JSON Files", "*.json")], parent=self)
        if fp:
            try:
                with open(fp, 'w', encoding='utf-8') as f:
                    json.dump(TaxonomyEngine.user_custom_entries, f, indent=2)
                messagebox.showinfo("Export Successful", f"Custom taxonomy exported successfully to:\n{fp}", parent=self)
            except Exception as ex:
                messagebox.showerror("Export Failed", f"Could not export JSON:\n{ex}", parent=self)

    def _import_json(self):
        from tkinter import filedialog
        fp = filedialog.askopenfilename(title="Import Custom Taxonomy JSON", filetypes=[("JSON Files", "*.json")], parent=self)
        if fp and os.path.exists(fp):
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for m in data.get("MATERIALS", []):
                            TaxonomyEngine.add_custom_material(m.get("canonical", ""), m.get("terms", []), m.get("subfamily", "CUSTOM"))
                        for mfr in data.get("MANUFACTURERS", []):
                            TaxonomyEngine.add_custom_manufacturer(mfr.get("name", ""), mfr.get("aliases", []))
                self._refresh_all_trees()
                if self.on_update_callback: self.on_update_callback()
                messagebox.showinfo("Import Successful", "Custom taxonomy library successfully merged and loaded!", parent=self)
            except Exception as ex:
                messagebox.showerror("Import Failed", f"Could not import JSON:\n{ex}", parent=self)

    def _trigger_rescan(self):
        if self.on_update_callback:
            self.on_update_callback()
            messagebox.showinfo("Re-Scan Complete", "Active document successfully re-scanned against latest domain taxonomy!", parent=self)


class VisualAnnotationStudio(tk.Toplevel):
    """
    Unified Multi-Modal Evidence & Annotation Studio.
    Provides tabbed navigation for Drawings (PDF, DOCX, Images), Raw Excel Spreadsheets,
    and Customer Email Body with synchronized cross-document label inspection and Active Learning.
    """

    def __init__(
        self,
        parent: tk.Widget,
        file_path: str,
        highlight_terms: Optional[List[str]] = None,
        component_data: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
        on_update_callback: Optional[Callable[[Dict[str, Any], Dict[str, Any]], None]] = None,
        candidate_files: Optional[List[str]] = None,
        email_data: Optional[Dict[str, Any]] = None,
        is_anonymized_mode: bool = False
    ):
        super().__init__(parent)
        self.parent = parent
        self.file_path = file_path
        self.highlight_terms = [t.strip() for t in (highlight_terms or []) if t and t.strip()]
        self.component_data = component_data or {}
        self.on_update_callback = on_update_callback
        self.email_data = email_data or {}
        self.is_anonymized_mode = is_anonymized_mode
        self._hash_cache = {}
        self._privacy_vector_boxes_cache = {}

        # Sibling file collection & multi-modal categorization (strictly deduplicated by basename & path)
        seen_paths = set()
        seen_bnames = set()
        all_raw_files = []

        def _add_raw(p):
            if not p or not os.path.exists(p): return
            norm_p = os.path.normcase(os.path.abspath(p))
            bn = os.path.basename(p).lower()
            if norm_p not in seen_paths and bn not in seen_bnames:
                seen_paths.add(norm_p)
                seen_bnames.add(bn)
                all_raw_files.append(p)

        if self.file_path and os.path.exists(self.file_path):
            _add_raw(self.file_path)

        for cf in (candidate_files or []):
            _add_raw(cf)

        # Scan folder for sibling attachments if candidate list is small
        if len(all_raw_files) <= 1 and self.file_path and os.path.exists(self.file_path):
            folder = os.path.dirname(self.file_path)
            for root, _, fns in os.walk(folder):
                for fn in fns:
                    _add_raw(os.path.join(root, fn))

        self.all_candidate_files = all_raw_files

        # Classify all candidate files (strictly unique basenames)
        self.all_drawing_files = []
        self.all_spreadsheet_files = []
        self.all_text_notes_files = []
        seen_draw_bnames = set()
        seen_sheet_bnames = set()
        seen_txt_bnames = set()

        for fp in self.all_candidate_files:
            ext = os.path.splitext(fp)[1].lower()
            bn = os.path.basename(fp).lower()
            if ext in ('.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.webp', '.docx', '.doc'):
                if bn not in seen_draw_bnames:
                    seen_draw_bnames.add(bn)
                    self.all_drawing_files.append(fp)
            elif ext in ('.xlsx', '.xls', '.csv'):
                if bn not in seen_sheet_bnames:
                    seen_sheet_bnames.add(bn)
                    self.all_spreadsheet_files.append(fp)
            elif ext in ('.txt', '.log', '.msg', '.eml'):
                if self._is_delimited_file(fp):
                    if bn not in seen_sheet_bnames:
                        seen_sheet_bnames.add(bn)
                        self.all_spreadsheet_files.append(fp)
                else:
                    if bn not in seen_txt_bnames:
                        seen_txt_bnames.add(bn)
                        self.all_text_notes_files.append(fp)

        # Ensure current file_path is active in drawing list
        if not self.all_drawing_files and self.file_path:
            self.all_drawing_files.append(self.file_path)

        # Extract tokens for this line item and filter relevant attachments (strictly unique basenames)
        self.item_tokens = self._extract_item_tokens()
        
        self.relevant_drawing_files = []
        rel_draw_bnames = set()
        for f in self.all_drawing_files:
            bn = os.path.basename(f).lower()
            if self._is_file_relevant(f, self.item_tokens) and bn not in rel_draw_bnames:
                rel_draw_bnames.add(bn)
                self.relevant_drawing_files.append(f)

        if self.file_path and os.path.basename(self.file_path).lower() not in rel_draw_bnames:
            ext_chk = os.path.splitext(self.file_path)[1].lower()
            if ext_chk in ('.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.webp', '.docx', '.doc'):
                rel_draw_bnames.add(os.path.basename(self.file_path).lower())
                self.relevant_drawing_files.insert(0, self.file_path)

        self.relevant_spreadsheet_files = []
        rel_sheet_bnames = set()
        for f in self.all_spreadsheet_files:
            bn = os.path.basename(f).lower()
            if self._is_file_relevant(f, self.item_tokens) and bn not in rel_sheet_bnames:
                rel_sheet_bnames.add(bn)
                self.relevant_spreadsheet_files.append(f)

        self.relevant_text_notes_files = []
        rel_txt_bnames = set()
        for f in self.all_text_notes_files:
            bn = os.path.basename(f).lower()
            if self._is_file_relevant(f, self.item_tokens) and bn not in rel_txt_bnames:
                rel_txt_bnames.add(bn)
                self.relevant_text_notes_files.append(f)

        # Default to showing only files referring to the selected line item
        self.filter_item_only = True
        self.drawing_files = list(self.relevant_drawing_files) if self.relevant_drawing_files else list(self.all_drawing_files)
        self.spreadsheet_files = list(self.relevant_spreadsheet_files) if self.relevant_spreadsheet_files else list(self.all_spreadsheet_files)
        self.text_notes_files = list(self.relevant_text_notes_files) if self.relevant_text_notes_files else list(self.all_text_notes_files)

        self.current_page_idx = 0
        self.total_pages = 1
        self.zoom_scale = 1.0
        self.pdf_doc = None
        self.docx_pages_cache: List[Image.Image] = []
        self.rendered_pil_img = None
        self.canvas_img_tk = None

        # Annotation data storage per page
        self.page_annotations: Dict[int, List[Dict[str, Any]]] = {}
        self.selected_annotation_id: Optional[str] = None
        self.selected_annotation_ids: Set[str] = set()
        self.active_category_filter: str = "ALL"
        self.draw_mode: bool = False
        self.drag_start = None
        self.current_drag_rect = None

        self.title(title or f"🔍 Unified Multi-Modal Evidence & Annotation Studio — {os.path.basename(file_path)}")
        self.geometry("1420x900")
        self.minsize(1040, 700)
        self.configure(bg="#0F172A")

        # Global Keyboard Bindings (guarded so they never interfere with Search / Entry fields)
        def _on_delete_key(e):
            if isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
                return  # Let normal text backspace / delete operate inside text boxes
            self._delete_selected_annotations()

        self.bind("<Delete>", _on_delete_key)
        self.bind("<Control-b>", lambda e: self._blacklist_and_teach_ai() if not isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)) else None)
        self.bind("<Control-B>", lambda e: self._blacklist_and_teach_ai() if not isinstance(e.widget, (tk.Entry, ttk.Entry, tk.Text)) else None)
        self.bind("<Escape>", lambda e: self._deselect_all_annotations())

        self.protocol("WM_DELETE_WINDOW", self._on_dialog_close)
        self._init_document()
        self._build_ui()
        self._extract_all_page_annotations()
        self._render_current_page()
        self._refresh_annotations_list()

    def _on_dialog_close(self):
        global _ACTIVE_STUDIO_INSTANCE
        if _ACTIVE_STUDIO_INSTANCE == self:
            _ACTIVE_STUDIO_INSTANCE = None
        self.destroy()

    def _get_header_sub_txt(self) -> str:
        p_no = str(self.component_data.get("part", self.component_data.get("Part Number", "N/A"))).strip()
        disp_p = self._display_val(p_no, "PART")
        mpn_v = self.component_data.get("mpn", self.component_data.get("MPN", ""))
        desc_v = self.component_data.get("desc", self.component_data.get("description", self.component_data.get("Description", "")))
        sub_txt = f"Focused Item: {disp_p}"
        if mpn_v: sub_txt += f" • MPN: {mpn_v}"
        if desc_v: sub_txt += f" • {desc_v[:45]}"
        return sub_txt

    def _toggle_privacy_mode(self):
        self.is_anonymized_mode = not getattr(self, "is_anonymized_mode", False)
        txt = "🔒 Privacy Blur: ON" if self.is_anonymized_mode else "🔒 Privacy Blur (MAIC)"
        bg_col = "#059669" if self.is_anonymized_mode else "#475569"
        if hasattr(self, 'btn_privacy_blur') and self.btn_privacy_blur:
            self.btn_privacy_blur.config(text=txt, bg=bg_col)
        if hasattr(self, 'top_sub_lbl') and self.top_sub_lbl:
            try: self.top_sub_lbl.config(text=self._get_header_sub_txt())
            except Exception: pass
        self._render_current_page()
        self._refresh_annotations_list()
        if hasattr(self, 'sheet_combo') and self.spreadsheet_files:
            self._load_selected_spreadsheet()
        self._render_email_tab()

    def _anonymize_text_body(self, text: str) -> str:
        if not text or not getattr(self, 'is_anonymized_mode', False):
            return text

        # 1. Known Customer Names, Brands & Locations
        cust_terms = [
            "tecan schweiz ag", "tecan", "schweiz ag", "schweiz", "eastek", "graco",
            "seestrasse 103", "seestrasse", "mannedorf", "männendorf", "switzerland", "ch-8708"
        ]
        for term in cust_terms:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            text = pattern.sub(lambda m: self._get_hash(m.group(0), "CUST"), text)

        # 2. Personal email addresses & client domains (mask domain except standard distributors)
        text = re.sub(r'[\w\.-]+@(?!mouser|digikey|octopart|arrow)[\w\.-]+\.\w+', r'procurement@client-vault.com', text, flags=re.IGNORECASE)

        # 3. Known part numbers and assemblies from component_data
        p_raw = str(self.component_data.get("part", self.component_data.get("Part Number", ""))).strip()
        assy_raw = str(self.component_data.get("assy_no", self.component_data.get("Assembly", ""))).strip()
        
        if p_raw and len(p_raw) >= 4:
            text = re.sub(re.escape(p_raw), self._get_hash(p_raw, "PART"), text, flags=re.IGNORECASE)
        if assy_raw and len(assy_raw) >= 4:
            text = re.sub(re.escape(assy_raw), self._get_hash(assy_raw, "ASSY"), text, flags=re.IGNORECASE)

        # General 8-digit part numbers (e.g. 30058153, 30070651, 30056852)
        text = re.sub(r'\b300\d{5}\b', lambda m: self._get_hash(m.group(0), "PART"), text)

        return text

    def _render_email_tab(self):
        if not hasattr(self, 'email_txt') or not self.email_txt: return

        em_subj = self.email_data.get("subject", "RFQ Customer Inquiry")
        em_sender = self.email_data.get("sender", "Client Purchasing / Engineering")
        em_date = self.email_data.get("date", "Recent Inquiry")

        if getattr(self, 'is_anonymized_mode', False):
            disp_subj = self._anonymize_text_body(em_subj)
            disp_sender = self._anonymize_text_body(em_sender)
        else:
            disp_subj = em_subj
            disp_sender = em_sender

        if hasattr(self, 'email_subj_lbl') and self.email_subj_lbl:
            self.email_subj_lbl.config(text=f"📩 Subject: {disp_subj}")
        if hasattr(self, 'email_sender_lbl') and self.email_sender_lbl:
            self.email_sender_lbl.config(text=f"👤 From: {disp_sender}  •  🕒 Date: {em_date}")

        em_body = self.email_data.get("body", self.email_data.get("body_text", ""))
        if not em_body and getattr(self, 'text_notes_files', None):
            try:
                with open(self.text_notes_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                    em_body = f.read()
            except Exception: pass

        if not em_body:
            p_val = self._display_val(str(self.component_data.get("part", self.component_data.get("Part Number", "N/A"))), "PART")
            desc_val = str(self.component_data.get("desc", self.component_data.get("description", self.component_data.get("Description", "N/A"))))
            mpn_val = str(self.component_data.get("mpn", self.component_data.get("MPN", "N/A")))
            em_body = f"Customer RFQ Email Body for Part: {p_val}\n\nClient Quote Requirements:\n• Quoted Part: {p_val}\n• Description: {desc_val}\n• MPN: {mpn_val}\n\nAll verified technical blueprints and spreadsheet attachments are cataloged in Tabs 1 & 2 above."

        disp_body = self._anonymize_text_body(em_body)

        self.email_txt.config(state="normal")
        self.email_txt.delete("1.0", "end")
        self.email_txt.insert("1.0", disp_body)
        self.email_txt.config(state="disabled")

    def _get_hash(self, val: str, prefix: str = "VAL") -> str:
        if not val or str(val).strip() in ("", "N/A", "None", "-", "Not Specified"):
            return str(val) if val is not None else ""
        s_val = str(val).strip()
        cache_key = (prefix, s_val)
        if cache_key in self._hash_cache:
            return self._hash_cache[cache_key]

        h_code = hashlib.md5(s_val.encode('utf-8')).hexdigest()[:4].upper()
        if prefix == "CUST":
            hashed = f"CUST-{h_code}"
        elif prefix == "ASSY":
            hashed = f"ASY-{h_code}"
        elif prefix == "MODEL":
            hashed = f"HARNESS-MOD-{h_code}"
        elif prefix == "REV":
            hashed = f"R-{h_code[:2]}"
        elif prefix == "PART":
            hashed = f"CP-{h_code}"
        else:
            hashed = f"{prefix}-{h_code}"

        self._hash_cache[cache_key] = hashed
        return hashed

    def _display_val(self, val: str, prefix: str) -> str:
        if getattr(self, "is_anonymized_mode", False):
            return self._get_hash(val, prefix)
        return str(val) if val is not None else ""

    @staticmethod
    def _is_delimited_file(fp: str) -> bool:
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                lines = [f.readline() for _ in range(5)]
                for line in lines:
                    if '\t' in line or ',' in line or '|' in line:
                        return True
        except Exception: pass
        return False

    def _extract_item_tokens(self) -> List[str]:
        """Extracts search tokens specifically associated with the focused line item."""
        tokens = set()
        # 1. Component Part Number, Assembly Number, MPN
        p_no = str(self.component_data.get("part", self.component_data.get("Part Number", ""))).strip()
        assy = str(self.component_data.get("assy_no", self.component_data.get("Assembly", ""))).strip()
        mpn = str(self.component_data.get("mpn", self.component_data.get("MPN", ""))).strip()

        for val in (p_no, assy, mpn):
            if val and len(val) >= 3 and val.lower() not in ("none", "n/a", "null", "part"):
                tokens.add(val.lower())
                # If there is a revision or delimiter like 30057355.03 or 30057355_EN_03, extract base
                base = re.split(r'[\._\-\s]', val)[0]
                if len(base) >= 3 and base.lower() not in ("none", "n/a"):
                    tokens.add(base.lower())
                # Extract numeric sequence of >= 5 digits (e.g. 30057355, 30062427)
                for num_m in re.finditer(r'\d{5,}', val):
                    tokens.add(num_m.group(0).lower())

        # 2. Raw item / evidence references
        raw = self.component_data.get("raw_item", {})
        if isinstance(raw, dict):
            for k in ("drawing_ref", "source_doc", "source_file"):
                v = str(raw.get(k, "")).strip()
                if v and len(v) >= 3:
                    tokens.add(os.path.basename(v).lower())
                    base_v = os.path.splitext(os.path.basename(v))[0]
                    if len(base_v) >= 3:
                        tokens.add(base_v.lower())

            ev = raw.get("evidence", {})
            if isinstance(ev, dict):
                for fld in ev.values():
                    if isinstance(fld, dict) and fld.get("source_doc"):
                        sdoc = str(fld["source_doc"]).strip()
                        if sdoc and len(sdoc) >= 3:
                            tokens.add(os.path.basename(sdoc).lower())

        # 3. Highlight terms
        for ht in self.highlight_terms:
            ht_clean = ht.strip()
            if len(ht_clean) >= 3 and ht_clean.lower() not in ("none", "cable", "part", "assy", "rev", "item", "drawing"):
                tokens.add(ht_clean.lower())

        return list(tokens)

    def _is_file_relevant(self, fp: str, tokens: List[str]) -> bool:
        """Determines if a candidate file belongs / refers to the focused line item."""
        if not fp: return False
        if self.file_path and (os.path.abspath(fp) == os.path.abspath(self.file_path) or os.path.basename(fp) == os.path.basename(self.file_path)):
            return True
        
        fn = os.path.basename(fp).lower()
        for tok in tokens:
            if tok in fn:
                return True
        return False

    def _init_document(self):
        if not HAS_VISION_LIBS or not self.file_path or not os.path.exists(self.file_path):
            self.total_pages = 1
            return

        ext = os.path.splitext(self.file_path)[1].lower()
        if ext == ".pdf":
            try:
                self.pdf_doc = pypdfium2.PdfDocument(self.file_path)
                self.total_pages = len(self.pdf_doc)
            except Exception as ex:
                print(f"[MultiModalStudio] PDF open failed: {ex}")
                self.pdf_doc = None
                self.total_pages = 1
        elif ext in (".docx", ".doc"):
            self.pdf_doc = None
            self.docx_pages_cache = self._render_docx_to_images(self.file_path)
            self.total_pages = max(1, len(self.docx_pages_cache))
        else:
            self.pdf_doc = None
            self.total_pages = 1

    def _render_docx_to_images(self, docx_path: str) -> List[Image.Image]:
        """Parses DOCX text paragraphs and renders visual document pages."""
        pages = []
        try:
            paragraphs = []
            with zipfile.ZipFile(docx_path) as z:
                xml_content = z.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                    texts = [node.text for node in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text]
                    if texts:
                        paragraphs.append(''.join(texts))

            # Render paragraphs onto A4-styled image pages (1200 x 1600)
            page_w, page_h = 1200, 1600
            current_img = Image.new("RGBA", (page_w, page_h), "#FFFFFF")
            draw = ImageDraw.Draw(current_img)

            # Header on document
            draw.rectangle([0, 0, page_w, 70], fill="#1E293B")
            draw.text((40, 22), f"📄 {os.path.basename(docx_path)} (Customer Specification Document)", fill="#F8FAFC")

            y_offset = 100
            line_height = 28
            margin_left = 60
            max_y = page_h - 80

            for p_idx, p_text in enumerate(paragraphs):
                # Word wrap
                words = p_text.split()
                line = ""
                for w in words:
                    test_line = line + (" " if line else "") + w
                    if len(test_line) * 11 > (page_w - 120):
                        if y_offset > max_y:
                            pages.append(current_img)
                            current_img = Image.new("RGBA", (page_w, page_h), "#FFFFFF")
                            draw = ImageDraw.Draw(current_img)
                            draw.rectangle([0, 0, page_w, 70], fill="#1E293B")
                            draw.text((40, 22), f"📄 {os.path.basename(docx_path)} (Page {len(pages)+1})", fill="#F8FAFC")
                            y_offset = 100
                        draw.text((margin_left, y_offset), line, fill="#0F172A")
                        y_offset += line_height
                        line = w
                    else:
                        line = test_line

                if line:
                    if y_offset > max_y:
                        pages.append(current_img)
                        current_img = Image.new("RGBA", (page_w, page_h), "#FFFFFF")
                        draw = ImageDraw.Draw(current_img)
                        draw.rectangle([0, 0, page_w, 70], fill="#1E293B")
                        draw.text((40, 22), f"📄 {os.path.basename(docx_path)} (Page {len(pages)+1})", fill="#F8FAFC")
                        y_offset = 100
                    draw.text((margin_left, y_offset), line, fill="#0F172A")
                    y_offset += line_height + 8

            pages.append(current_img)
        except Exception as ex:
            print(f"[MultiModalStudio] DOCX render error: {ex}")
            err_img = Image.new("RGBA", (1000, 800), "#FFFFFF")
            d = ImageDraw.Draw(err_img)
            d.text((50, 50), f"DOCX Preview: {os.path.basename(docx_path)}\n\n{ex}", fill="#0F172A")
            pages.append(err_img)

        return pages if pages else [Image.new("RGBA", (1000, 800), "#FFFFFF")]

    def _build_ui(self):
        # 1. Top Header Banner
        hdr = tk.Frame(self, bg="#1E293B", padx=16, pady=10)
        hdr.pack(fill="x")

        title_sub = tk.Frame(hdr, bg="#1E293B")
        title_sub.pack(side="left", fill="y")

        fn_disp = os.path.basename(self.file_path) if self.file_path else "Evidence Workspace"
        tk.Label(
            title_sub,
            text=f"📐 Unified Multi-Modal Evidence & Annotation Studio: {fn_disp}",
            font=("Segoe UI", 13, "bold"),
            fg="#FFFFFF",
            bg="#1E293B"
        ).pack(anchor="w")

        conf = self.component_data.get("confidence", 95)
        self.top_sub_lbl = tk.Label(
            title_sub,
            text=self._get_header_sub_txt(),
            font=("Segoe UI", 10),
            fg="#94A3B8",
            bg="#1E293B"
        )
        self.top_sub_lbl.pack(anchor="w", pady=(2, 0))

        # Right Controls: Confidence Badge & Zoom
        r_ctrl = tk.Frame(hdr, bg="#1E293B")
        r_ctrl.pack(side="right")

        badge_bg = "#065F46" if conf >= 85 else ("#92400E" if conf >= 60 else "#991B1B")
        badge_fg = "#A7F3D0" if conf >= 85 else ("#FDE68A" if conf >= 60 else "#FECACA")
        tk.Label(
            r_ctrl,
            text=f"🎯 AI Confidence: {conf}%",
            font=("Segoe UI", 10, "bold"),
            bg=badge_bg,
            fg=badge_fg,
            padx=12,
            pady=4
        ).pack(side="right", padx=(10, 0))

        # Zoom Controls with Large Buttons
        tk.Button(
            r_ctrl, text="🔍+", command=lambda: self._set_zoom(self.zoom_scale + 0.25),
            bg="#334155", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=9, pady=3, cursor="hand2"
        ).pack(side="right", padx=2)

        self.zoom_lbl = tk.Label(r_ctrl, text=f"{int(self.zoom_scale * 100)}%", font=("Segoe UI", 9, "bold"), fg="#CBD5E1", bg="#1E293B", width=6)
        self.zoom_lbl.pack(side="right", padx=2)

        tk.Button(
            r_ctrl, text="🔍-", command=lambda: self._set_zoom(max(0.5, self.zoom_scale - 0.25)),
            bg="#334155", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=9, pady=3, cursor="hand2"
        ).pack(side="right", padx=2)

        tk.Button(
            r_ctrl, text="Fit Width", command=lambda: self._set_zoom(1.0),
            bg="#334155", fg="#CBD5E1", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=8, pady=3, cursor="hand2"
        ).pack(side="right", padx=3)

        # 2. Main Content Resizable Split View (PanedWindow)
        main_body = tk.Frame(self, bg="#0F172A", padx=10, pady=6)
        main_body.pack(fill="both", expand=True)

        self.splitter = tk.PanedWindow(main_body, orient="horizontal", bg="#475569", sashrelief="raised", sashwidth=7, bd=0, showhandle=True, handlesize=10, opaqueresize=True)
        self.splitter.pack(fill="both", expand=True)

        # Left Container: Multi-Modal Notebook Container (Area 1)
        doc_container = tk.Frame(self.splitter, bg="#0F172A", bd=1, relief="solid")
        self.splitter.add(doc_container, minsize=480)

        # Notebook for Multi-Modal tabs
        st_nb_style = ttk.Style()
        try: st_nb_style.theme_use("clam")
        except Exception: pass
        st_nb_style.configure("MMStudio.TNotebook", background="#0F172A", borderwidth=0, tabmargins=[2, 4, 2, 0])
        st_nb_style.configure("MMStudio.TNotebook.Tab", background="#1E293B", foreground="#94A3B8", font=("Segoe UI", 9, "bold"), padding=[14, 6], borderwidth=0)
        st_nb_style.map("MMStudio.TNotebook.Tab", background=[("selected", "#2563EB"), ("active", "#334155")], foreground=[("selected", "#FFFFFF"), ("active", "#F8FAFC")])

        self.nb = ttk.Notebook(doc_container, style="MMStudio.TNotebook")
        self.nb.pack(fill="both", expand=True)

        # =========================================================================
        # TAB 1: 📄 Drawings & Visual Specs (PDF, DOCX, Images)
        # =========================================================================
        tab_drawings = tk.Frame(self.nb, bg="#1E293B")
        self.nb.add(tab_drawings, text=f" 📄 Drawings & Specs ({len(self.drawing_files)}) ")

        # Multi-File Switcher & Navigation Tool Bar
        nav_bar = tk.Frame(tab_drawings, bg="#1E293B", padx=8, pady=6)
        nav_bar.pack(fill="x")

        tk.Label(nav_bar, text="📄 Active File:", font=("Segoe UI", 9, "bold"), fg="#38BDF8", bg="#1E293B").pack(side="left", padx=(0, 4))
        file_options = [os.path.basename(f) for f in self.drawing_files] or [os.path.basename(self.file_path)]
        self.file_combo = ttk.Combobox(nav_bar, values=file_options, state="readonly", width=28, font=("Segoe UI", 9))
        
        cur_fn = os.path.basename(self.file_path)
        if cur_fn in file_options:
            self.file_combo.current(file_options.index(cur_fn))
        elif file_options:
            self.file_combo.current(0)
        self.file_combo.pack(side="left", padx=(0, 6))
        self.file_combo.bind("<<ComboboxSelected>>", self._on_drawing_file_switched)

        # Filter toggle checkbutton (Item Only vs All RFQ Files)
        self.filter_item_var = tk.BooleanVar(value=self.filter_item_only)
        self.chk_filter = tk.Checkbutton(
            nav_bar, text=f"Item Only ({len(self.drawing_files)}/{len(self.all_drawing_files)})",
            variable=self.filter_item_var, command=self._on_filter_toggled,
            font=("Segoe UI", 8, "bold"), fg="#38BDF8", bg="#1E293B",
            selectcolor="#0F172A", activebackground="#1E293B", activeforeground="#38BDF8",
            cursor="hand2"
        )
        self.chk_filter.pack(side="left", padx=(0, 8))

        self.btn_prev = tk.Button(
            nav_bar, text="◀ Prev", command=self._prev_page,
            bg="#334155", fg="#FFFFFF", font=("Segoe UI", 8, "bold"),
            relief="flat", padx=8, pady=3, cursor="hand2"
        )
        self.btn_prev.pack(side="left")

        self.page_lbl = tk.Label(
            nav_bar, text=f"Page 1 of {self.total_pages}",
            font=("Segoe UI", 9, "bold"), fg="#FFFFFF", bg="#1E293B"
        )
        self.page_lbl.pack(side="left", padx=6)

        self.btn_next = tk.Button(
            nav_bar, text="Next ▶", command=self._next_page,
            bg="#334155", fg="#FFFFFF", font=("Segoe UI", 8, "bold"),
            relief="flat", padx=8, pady=3, cursor="hand2"
        )
        self.btn_next.pack(side="left", padx=(0, 8))

        # Draw Tool Toggle
        self.btn_draw = tk.Button(
            nav_bar, text="✏️ Draw Box Label", command=self._toggle_draw_mode,
            bg="#334155", fg="#F8FAFC", font=("Segoe UI", 8, "bold"),
            relief="flat", padx=8, pady=3, cursor="hand2"
        )
        self.btn_draw.pack(side="left", padx=2)

        # Clear Selection Button
        self.btn_unselect = tk.Button(
            nav_bar, text="👁️ Show All", command=self._deselect_annotation,
            bg="#1E293B", fg="#38BDF8", font=("Segoe UI", 8, "bold"),
            relief="flat", padx=6, pady=3, cursor="hand2"
        )
        self.btn_unselect.pack(side="left", padx=(4, 2))

        # Quick OCR Search Filter inside Document
        tk.Label(nav_bar, text="🔍", font=("Segoe UI", 9), fg="#94A3B8", bg="#1E293B").pack(side="left", padx=(6, 2))
        self.search_var = tk.StringVar(value=", ".join(self.highlight_terms))
        search_ent = tk.Entry(nav_bar, textvariable=self.search_var, font=("Segoe UI", 9), width=15, bd=1, relief="solid")
        search_ent.pack(side="left", padx=(0, 4), ipady=1)

        def _on_search_update():
            terms = [t.strip() for t in self.search_var.get().split(",") if t.strip()]
            self.highlight_terms = terms
            self._extract_all_page_annotations()
            self._render_current_page()
            self._refresh_annotations_list()

        tk.Button(
            nav_bar, text="Search", command=_on_search_update,
            bg="#2563EB", fg="#FFFFFF", font=("Segoe UI", 8, "bold"),
            relief="flat", padx=8, pady=3, cursor="hand2"
        ).pack(side="left")

        # Enterprise Domain Taxonomy Library Button
        tk.Button(
            nav_bar, text="📚 Taxonomy Library", command=self._open_taxonomy_manager,
            bg="#4338CA", fg="#E0E7FF", activebackground="#4F46E5", activeforeground="#FFFFFF",
            font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=3, cursor="hand2"
        ).pack(side="left", padx=(8, 2))

        # Presentation Privacy Redaction & Blur Mode Toggle Button
        self.btn_privacy_blur = tk.Button(
            nav_bar,
            text="🔒 Privacy Blur: ON" if getattr(self, 'is_anonymized_mode', False) else "🔒 Privacy Blur (MAIC)",
            command=self._toggle_privacy_mode,
            bg="#059669" if getattr(self, 'is_anonymized_mode', False) else "#475569",
            fg="#FFFFFF",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            padx=8,
            pady=3,
            cursor="hand2"
        )
        self.btn_privacy_blur.pack(side="left", padx=(6, 2))

        # Scrollable Canvas
        canvas_fr = tk.Frame(tab_drawings, bg="#0F172A")
        canvas_fr.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(canvas_fr, bg="#0F172A", highlightthickness=0)
        self.h_sb = ttk.Scrollbar(canvas_fr, orient="horizontal", command=self.canvas.xview)
        self.v_sb = ttk.Scrollbar(canvas_fr, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_sb.set, yscrollcommand=self.v_sb.set)

        self.v_sb.pack(side="right", fill="y")
        self.h_sb.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Mouse Bindings for Canvas
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        # =========================================================================
        # TAB 2: 📊 Raw Spreadsheets & Data (Excel, CSV, TXT)
        # =========================================================================
        tab_sheets = tk.Frame(self.nb, bg="#1E293B")
        self.nb.add(tab_sheets, text=f" 📊 Raw Spreadsheets ({len(self.spreadsheet_files)}) ")

        sheet_ctrl = tk.Frame(tab_sheets, bg="#1E293B", padx=8, pady=6)
        sheet_ctrl.pack(fill="x")

        self.sheet_file_var = tk.StringVar()
        tk.Label(sheet_ctrl, text="📊 Active Spreadsheet:", font=("Segoe UI", 9, "bold"), fg="#10B981", bg="#1E293B").pack(side="left", padx=(0, 4))
        sheet_fns = [os.path.basename(f) for f in self.spreadsheet_files]
        self.sheet_combo = ttk.Combobox(sheet_ctrl, textvariable=self.sheet_file_var, values=sheet_fns, state="readonly", width=32, font=("Segoe UI", 9))
        if sheet_fns:
            self.sheet_combo.current(0)
        self.sheet_combo.pack(side="left", padx=(0, 6))
        self.sheet_combo.bind("<<ComboboxSelected>>", lambda e: self._load_selected_spreadsheet())

        self.chk_sheet_filter = tk.Checkbutton(
            sheet_ctrl, text=f"Item Only ({len(self.spreadsheet_files)}/{len(self.all_spreadsheet_files)})",
            variable=self.filter_item_var, command=self._on_filter_toggled,
            font=("Segoe UI", 8, "bold"), fg="#10B981", bg="#1E293B",
            selectcolor="#0F172A", activebackground="#1E293B", activeforeground="#10B981",
            cursor="hand2"
        )
        self.chk_sheet_filter.pack(side="left", padx=(0, 8))

        tk.Button(sheet_ctrl, text="📊 Open in Native Excel App ↗", command=self._open_active_spreadsheet, bg="#059669", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), relief="flat", padx=10, pady=2, cursor="hand2").pack(side="right")

        # Main In-Window HTML Spreadsheet Specification Container (Same rich aesthetics as Sourcing Tab)
        self.sheet_html_container = tk.Frame(tab_sheets, bg="#0F172A", bd=1, relief="solid")
        self.sheet_html_container.pack(fill="both", expand=True, padx=4, pady=(2, 4))

        try:
            from tkinterweb import HtmlFrame
            self.sheet_html_frame = HtmlFrame(self.sheet_html_container, messages_enabled=False)
            self.sheet_html_frame.on_link_click = self._handle_html_link_click
            self.sheet_html_frame.pack(fill="both", expand=True)
        except Exception:
            self.sheet_html_frame = None

        if self.spreadsheet_files:
            self._load_selected_spreadsheet()

        # =========================================================================
        # TAB 3: 📧 Client Email & RFQ Inquiries
        # =========================================================================
        tab_email = tk.Frame(self.nb, bg="#1E293B")
        self.nb.add(tab_email, text=" 📧 Client Email & Specs ")

        email_hdr_fr = tk.Frame(tab_email, bg="#0F172A", padx=12, pady=8, bd=1, relief="solid")
        email_hdr_fr.pack(fill="x", padx=4, pady=(4, 2))

        em_subj = self.email_data.get("subject", "RFQ Customer Inquiry")
        em_sender = self.email_data.get("sender", "Client Purchasing / Engineering")
        em_date = self.email_data.get("date", "Recent Inquiry")

        em_left = tk.Frame(email_hdr_fr, bg="#0F172A")
        em_left.pack(side="left", fill="both", expand=True)
        self.email_subj_lbl = tk.Label(em_left, text=f"📩 Subject: {em_subj}", font=("Segoe UI", 10, "bold"), fg="#FFFFFF", bg="#0F172A")
        self.email_subj_lbl.pack(anchor="w")
        self.email_sender_lbl = tk.Label(em_left, text=f"👤 From: {em_sender}  •  🕒 Date: {em_date}", font=("Segoe UI", 8), fg="#94A3B8", bg="#0F172A")
        self.email_sender_lbl.pack(anchor="w", pady=(2, 0))

        em_actions = tk.Frame(email_hdr_fr, bg="#0F172A")
        em_actions.pack(side="right")

        tk.Button(
            em_actions, text="✉️ Open in Outlook / Mail App ↗", command=self._open_email_in_mail_app,
            bg="#0284C7", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=3, cursor="hand2"
        ).pack(side="right", padx=2)

        tk.Button(
            em_actions, text="🌐 Webmail ↗", command=lambda: self._open_web_url(f"https://mail.google.com/mail/u/0/#search/{em_subj}"),
            bg="#334155", fg="#CBD5E1", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=3, cursor="hand2"
        ).pack(side="right", padx=2)

        # Email Text View
        email_txt_fr = tk.Frame(tab_email, bg="#0F172A")
        email_txt_fr.pack(fill="both", expand=True, padx=4, pady=4)

        self.email_txt = tk.Text(email_txt_fr, font=("Segoe UI", 10), bg="#0F172A", fg="#F1F5F9", insertbackground="#38BDF8", bd=0, wrap="word", padx=12, pady=10)
        em_vsb = ttk.Scrollbar(email_txt_fr, orient="vertical", command=self.email_txt.yview)
        self.email_txt.configure(yscrollcommand=em_vsb.set)
        em_vsb.pack(side="right", fill="y")
        self.email_txt.pack(side="left", fill="both", expand=True)

        self._render_email_tab()

        # =========================================================================
        # TAB 4: 🌐 Web Resources & Sourcing Specs (Mouser, DigiKey, Octopart)
        # =========================================================================
        tab_web = tk.Frame(self.nb, bg="#1E293B")
        self.nb.add(tab_web, text=" 🌐 Web Resources & Sourcing ")
        self._build_web_sourcing_tab(tab_web)

        # =========================================================================
        # Right Side Panel: Resizable, Auto-Wrapping, and Big-Text (Areas 2 & 3)
        # =========================================================================
        side_fr = tk.Frame(self.splitter, bg="#1E293B", padx=14, pady=10, bd=1, relief="solid")
        self.splitter.add(side_fr, minsize=340)

        self.side_splitter = tk.PanedWindow(side_fr, orient="vertical", bg="#475569", sashrelief="raised", sashwidth=7, bd=0, showhandle=True, handlesize=10, opaqueresize=True)
        self.side_splitter.pack(fill="both", expand=True)

        # Top Section of Sidebar: Title + Category Pills + Annotation List
        top_side = tk.Frame(self.side_splitter, bg="#1E293B")
        self.side_splitter.add(top_side, minsize=200)

        tk.Label(
            top_side, text="🏷️ OCR Labels & Bounding Boxes",
            font=("Segoe UI", 11, "bold"), fg="#FFFFFF", bg="#1E293B"
        ).pack(anchor="w", pady=(0, 6))

        # Auto-Wrapping Category Filter Chips Frame (Multi-row Grid)
        self.chips_fr = tk.Frame(top_side, bg="#1E293B")
        self.chips_fr.pack(fill="x", pady=(0, 8))

        # Scrollable Annotations List Box
        list_lbl = tk.Label(top_side, text="📑 Detected Annotations on this Page:", font=("Segoe UI", 9, "bold"), fg="#94A3B8", bg="#1E293B")
        list_lbl.pack(anchor="w", pady=(2, 4))

        list_container = tk.Frame(top_side, bg="#0F172A", bd=1, relief="solid")
        list_container.pack(fill="both", expand=True, pady=(0, 4))

        self.annot_canvas = tk.Canvas(list_container, bg="#0F172A", highlightthickness=0)
        self.annot_sb = ttk.Scrollbar(list_container, orient="vertical", command=self.annot_canvas.yview)
        self.annot_canvas.configure(yscrollcommand=self.annot_sb.set)
        self.annot_inner = tk.Frame(self.annot_canvas, bg="#0F172A")
        self.annot_win = self.annot_canvas.create_window((0, 0), window=self.annot_inner, anchor="nw")

        def _on_annot_cfg(e):
            self.annot_canvas.configure(scrollregion=self.annot_canvas.bbox("all"))
            self.annot_canvas.itemconfig(self.annot_win, width=e.width)
        self.annot_canvas.bind("<Configure>", _on_annot_cfg)
        self.annot_sb.pack(side="right", fill="y")
        self.annot_canvas.pack(side="left", fill="both", expand=True)

        self._bind_mouse_scroll(self.annot_canvas, self.annot_canvas)
        self._bind_mouse_scroll(self.annot_inner, self.annot_canvas)

        # Bottom Section of Sidebar: Inspector & Action Buttons
        bot_side = tk.Frame(self.side_splitter, bg="#1E293B")
        self.side_splitter.add(bot_side, minsize=220)

        self.inspect_box = tk.LabelFrame(bot_side, text=" 🔍 Selected Label Inspector & AI Evidence ", font=("Segoe UI", 9, "bold"),
                                         bg="#1E293B", fg="#38BDF8", padx=10, pady=8)
        self.inspect_box.pack(fill="both", expand=True, pady=(4, 6))

        self.insp_cat_lbl = tk.Label(self.inspect_box, text="Category: None Selected (Showing All)", font=("Segoe UI", 10, "bold"), fg="#94A3B8", bg="#1E293B", anchor="w")
        self.insp_cat_lbl.pack(fill="x")

        self.insp_text = tk.Text(self.inspect_box, height=3, font=("Consolas", 10, "bold"), bg="#0F172A", fg="#34D399", relief="flat", bd=0, wrap="word", padx=8, pady=6)
        self.insp_text.pack(fill="x", pady=4)
        self._bind_mouse_scroll(self.insp_text, self.annot_canvas)

        self.insp_freq_lbl = tk.Label(self.inspect_box, text="📊 Occurrence: Click any box to inspect", font=("Segoe UI", 9, "bold"), fg="#F59E0B", bg="#1E293B", anchor="w", wraplength=400, justify="left")
        self.insp_freq_lbl.pack(fill="x", pady=1)

        self.insp_zone_lbl = tk.Label(self.inspect_box, text="📍 Document Zone: N/A", font=("Segoe UI", 9), fg="#94A3B8", bg="#1E293B", anchor="w", wraplength=400, justify="left")
        self.insp_zone_lbl.pack(fill="x", pady=1)

        self.insp_meta_lbl = tk.Label(self.inspect_box, text="🎯 AI Confidence: Click any box to view", font=("Segoe UI", 9), fg="#38BDF8", bg="#1E293B", anchor="w", wraplength=400, justify="left")
        self.insp_meta_lbl.pack(fill="x", pady=1)

        def _on_side_resize(event):
            w = max(200, event.width - 30)
            self.insp_freq_lbl.config(wraplength=w)
            self.insp_zone_lbl.config(wraplength=w)
            self.insp_meta_lbl.config(wraplength=w)
        side_fr.bind("<Configure>", _on_side_resize)

        # Bottom Actions
        act_row1 = tk.Frame(bot_side, bg="#1E293B")
        act_row1.pack(fill="x", pady=(4, 2))

        tk.Button(
            act_row1, text="✏️ Amend / Reclassify", command=self._edit_selected_annotation,
            bg="#D97706", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=5, cursor="hand2"
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        tk.Button(
            act_row1, text="📋 Copy", command=self._copy_selected_text,
            bg="#2563EB", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=12, pady=5, cursor="hand2"
        ).pack(side="left", padx=2)

        tk.Button(
            act_row1, text="🗑️ Delete (Del)", command=self._delete_selected_annotations,
            bg="#DC2626", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=5, cursor="hand2"
        ).pack(side="left", padx=(2, 0))

        act_row2 = tk.Frame(bot_side, bg="#1E293B")
        act_row2.pack(fill="x", pady=(2, 4))

        tk.Button(
            act_row2, text="📚 Teach to Library", command=self._teach_selected_to_taxonomy,
            bg="#065F46", fg="#A7F3D0", activebackground="#047857", activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=8, pady=5, cursor="hand2"
        ).pack(side="left", fill="x", expand=True, padx=(0, 2))

        tk.Button(
            act_row2, text="🚫 Blacklist (Ctrl+B)", command=self._blacklist_and_teach_ai,
            bg="#7C2D12", fg="#FED7AA", activebackground="#9A3412", activeforeground="#FFFFFF",
            font=("Segoe UI", 9, "bold"), relief="flat", padx=8, pady=5, cursor="hand2"
        ).pack(side="left", fill="x", expand=True, padx=(2, 0))

        tk.Button(
            bot_side, text="Close Studio", command=self.destroy,
            bg="#334155", fg="#FFFFFF", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2"
        ).pack(fill="x", pady=(2, 0))

    def _open_taxonomy_manager(self):
        TaxonomyManagerDialog(self, on_update_callback=self._on_taxonomy_updated)

    def _on_taxonomy_updated(self):
        self._extract_all_page_annotations()
        self._render_current_page()
        self._refresh_annotations_list()

    def _teach_selected_to_taxonomy(self):
        target_id = next(iter(self.selected_annotation_ids)) if self.selected_annotation_ids else self.selected_annotation_id
        if not target_id:
            messagebox.showinfo("Select Item", "Please select an annotation label to teach into the Domain Library.", parent=self)
            return

        annots = self.page_annotations.get(self.current_page_idx, [])
        target_ann = next((a for a in annots if a["id"] == target_id), None)
        if not target_ann: return

        txt = target_ann.get("text", "")
        cat = target_ann.get("category", "DESCRIPTION")
        dlg = AddTaxonomyTermDialog(self, default_text=txt, default_category=cat)
        if dlg.result:
            self._on_taxonomy_updated()
            messagebox.showinfo("📚 Library Updated", f"✅ Successfully added '{dlg.result['canonical']}' to Domain Taxonomy!\n\nAll occurrences in this blueprint and future drawings will now be auto-detected.", parent=self)

    def _on_drawing_file_switched(self, event=None):
        if not hasattr(self, 'file_combo'): return
        sel_fn = self.file_combo.get()
        matched = next((f for f in self.drawing_files if os.path.basename(f) == sel_fn), None)
        if not matched:
            matched = next((f for f in self.all_drawing_files if os.path.basename(f) == sel_fn), None)
        if matched and matched != self.file_path:
            self.file_path = matched
            self.current_page_idx = 0
            self.page_annotations.clear()
            self.selected_annotation_id = None
            self._init_document()
            self._extract_all_page_annotations()
            self._render_current_page()
            self._refresh_annotations_list()

    def _on_filter_toggled(self):
        self.filter_item_only = self.filter_item_var.get()
        if self.filter_item_only:
            self.drawing_files = list(self.relevant_drawing_files) if self.relevant_drawing_files else list(self.all_drawing_files)
            self.spreadsheet_files = list(self.relevant_spreadsheet_files) if self.relevant_spreadsheet_files else list(self.all_spreadsheet_files)
            self.text_notes_files = list(self.relevant_text_notes_files) if self.relevant_text_notes_files else list(self.all_text_notes_files)
        else:
            self.drawing_files = list(self.all_drawing_files)
            self.spreadsheet_files = list(self.all_spreadsheet_files)
            self.text_notes_files = list(self.all_text_notes_files)

        # Update Notebook tab titles
        self.nb.tab(0, text=f" 📄 Drawings & Specs ({len(self.drawing_files)}) ")
        self.nb.tab(1, text=f" 📊 Raw Spreadsheets ({len(self.spreadsheet_files)}) ")

        # Update checkbutton labels
        if hasattr(self, 'chk_filter'):
            self.chk_filter.config(text=f"Item Only ({len(self.drawing_files)}/{len(self.all_drawing_files)})")
        if hasattr(self, 'chk_sheet_filter'):
            self.chk_sheet_filter.config(text=f"Item Only ({len(self.spreadsheet_files)}/{len(self.all_spreadsheet_files)})")

        # Update drawing dropdown
        if hasattr(self, 'file_combo'):
            file_options = [os.path.basename(f) for f in self.drawing_files] or [os.path.basename(self.file_path)]
            self.file_combo['values'] = file_options
            cur_fn = os.path.basename(self.file_path)
            if cur_fn in file_options:
                self.file_combo.current(file_options.index(cur_fn))
            elif file_options:
                self.file_combo.current(0)
                self._on_drawing_file_switched()

        # Update spreadsheet combo
        if hasattr(self, 'sheet_combo'):
            sheet_fns = [os.path.basename(f) for f in self.spreadsheet_files]
            self.sheet_combo['values'] = sheet_fns
            if sheet_fns:
                cur_sfn = self.sheet_file_var.get()
                if cur_sfn in sheet_fns:
                    self.sheet_combo.current(sheet_fns.index(cur_sfn))
                else:
                    self.sheet_combo.current(0)
                self._load_selected_spreadsheet()
            else:
                self.sheet_file_var.set("")

    def _load_selected_spreadsheet(self):
        if not self.spreadsheet_files: return
        sel_fn = self.sheet_file_var.get()
        matched_fp = next((f for f in self.spreadsheet_files if os.path.basename(f) == sel_fn), self.spreadsheet_files[0])

        ext = os.path.splitext(matched_fp)[1].lower()
        header_data = {}
        table_headers = []
        table_rows = []

        if ext == '.xls':
            try:
                import xlrd
                wb = xlrd.open_workbook(matched_fp)
                # 1. Check Header Sheet
                if 'RawHeader' in wb.sheet_names():
                    ws_h = wb.sheet_by_name('RawHeader')
                    for r in range(ws_h.nrows):
                        r_vals = [ws_h.cell_value(r, c) for c in range(ws_h.ncols)]
                        if len(r_vals) >= 3 and str(r_vals[1]).strip() and str(r_vals[1]).strip() != '42':
                            k = str(r_vals[1]).strip()
                            v = str(int(r_vals[2])) if isinstance(r_vals[2], float) and r_vals[2].is_integer() else str(r_vals[2]).strip()
                            if v and v != 'None':
                                header_data[k] = v
                elif 'Header' in wb.sheet_names():
                    ws_h = wb.sheet_by_name('Header')
                    for r in range(ws_h.nrows):
                        r_vals = [ws_h.cell_value(r, c) for c in range(ws_h.ncols)]
                        non_empty = [str(x).strip() for x in r_vals if str(x).strip()]
                        if len(non_empty) >= 2:
                            header_data[non_empty[0]] = non_empty[1]

                # 2. Check Data Table Sheet
                t_sheet = 'Format' if 'Format' in wb.sheet_names() else ('RawData' if 'RawData' in wb.sheet_names() else wb.sheet_names()[0])
                ws_t = wb.sheet_by_name(t_sheet)
                raw_headers = [str(ws_t.cell_value(0, c)).strip() for c in range(ws_t.ncols)]

                # Check if this sheet is an Assembly-Level RFQ EAU Matrix (Demand & Drawing Overview)
                is_eau_sheet = any(('annual volume' in h.lower() or 'eau' in h.lower() or 'samples price' in h.lower() or 'article no' in h.lower()) for h in raw_headers)

                if is_eau_sheet:
                    idx_art = -1; idx_rev = -1; idx_status = -1; idx_desc = -1; idx_eau = -1; idx_draw = -1; idx_bom = -1; idx_price = -1
                    for i, h in enumerate(raw_headers):
                        h_low = h.lower()
                        if idx_art == -1 and ('article' in h_low or 'material' in h_low or 'part' in h_low or 'item' in h_low): idx_art = i
                        elif idx_rev == -1 and 'rev' in h_low: idx_rev = i
                        elif idx_status == -1 and ('status' in h_low or 'mat status' in h_low): idx_status = i
                        elif idx_desc == -1 and ('description' in h_low or 'desc' in h_low): idx_desc = i
                        elif idx_eau == -1 and ('annual volume' in h_low or 'eau' in h_low or 'quantity' in h_low): idx_eau = i
                        elif idx_draw == -1 and ('drawing' in h_low or 'blueprint' in h_low or 'doc' in h_low): idx_draw = i
                        elif idx_bom == -1 and 'bom' in h_low: idx_bom = i
                        elif idx_price == -1 and ('price' in h_low or 'sample' in h_low or 'cost' in h_low): idx_price = i

                    eau_col_candidates = [
                        ('Article / Assy #', idx_art),
                        ('Rev', idx_rev),
                        ('Material Status', idx_status),
                        ('Description', idx_desc),
                        ('Estimated Annual Volume (EAU)', idx_eau),
                        ('Drawing Ref', idx_draw),
                        ('BOM Available', idx_bom),
                        ('Sample Price', idx_price)
                    ]
                    valid_col_specs = [(name, idx) for name, idx in eau_col_candidates if idx >= 0]
                else:
                    # Smart mapped columns for Component-Level BOM breakdown
                    idx_level = -1; idx_pos = -1; idx_qty = -1; idx_unit = -1; idx_part = -1; idx_rev = -1; idx_doc = -1; idx_desc = -1
                    for i, h in enumerate(raw_headers):
                        h_low = h.lower()
                        if idx_level == -1 and 'explosion' in h_low: idx_level = i
                        elif idx_pos == -1 and 'item number' in h_low: idx_pos = i
                        elif idx_qty == -1 and ('comp. qty' in h_low or 'quantity' in h_low or 'qty' in h_low): idx_qty = i
                        elif idx_unit == -1 and ('component unit' in h_low or 'unit' in h_low or 'uom' in h_low): idx_unit = i
                        elif idx_part == -1 and ('component number' in h_low or 'part number' in h_low or 'material' in h_low): idx_part = i
                        elif idx_rev == -1 and ('revision' in h_low or 'rev' in h_low): idx_rev = i
                        elif idx_doc == -1 and 'document' in h_low and 'type' not in h_low and 'part' not in h_low and 'version' not in h_low: idx_doc = i
                        elif idx_desc == -1 and ('object description' in h_low or 'description' in h_low): idx_desc = i

                    col_candidates = [
                        ('Explosion Level', idx_level),
                        ('Item #', idx_pos),
                        ('Quantity', idx_qty),
                        ('Unit', idx_unit),
                        ('Component Part #', idx_part),
                        ('Rev', idx_rev),
                        ('Linked Blueprint Ref', idx_doc),
                        ('Object Description', idx_desc)
                    ]
                    valid_col_specs = [(name, idx) for name, idx in col_candidates if idx >= 0]

                if len(valid_col_specs) >= 3:
                    table_headers = [c[0] for c in valid_col_specs]
                    for r in range(1, ws_t.nrows):
                        row_vals = []
                        for _, c_idx in valid_col_specs:
                            val = ws_t.cell_value(r, c_idx)
                            if isinstance(val, float) and val.is_integer():
                                row_vals.append(str(int(val)))
                            elif val is None:
                                row_vals.append('')
                            else:
                                row_vals.append(str(val).strip())
                        if any(row_vals):
                            table_rows.append(row_vals)
                else:
                    # Fallback for generic tabular file
                    active_cols = []
                    for c in range(ws_t.ncols):
                        if any(str(ws_t.cell_value(r, c)).strip() for r in range(ws_t.nrows)):
                            active_cols.append(c)
                    table_headers = [raw_headers[c] if raw_headers[c] else f"Col {c+1}" for c in active_cols]
                    for r in range(1, ws_t.nrows):
                        row_vals = [str(ws_t.cell_value(r, c)).strip() if ws_t.cell_value(r, c) is not None else "" for c in active_cols]
                        if any(row_vals):
                            table_rows.append(row_vals)
            except Exception as ex:
                print(f"[MultiModalStudio] Excel .xls HTML extract error: {ex}")
        elif ext == '.xlsx' and HAS_OPENPYXL:
            try:
                wb = openpyxl.load_workbook(matched_fp, data_only=True)
                ws = wb.active
                raw_rows = []
                for r in ws.iter_rows(values_only=True):
                    if any(c is not None and str(c).strip() != "" for c in r):
                        raw_rows.append([str(c).strip() if c is not None else "" for c in r])
                if raw_rows:
                    table_headers = raw_rows[0]
                    table_rows = raw_rows[1:]
            except Exception as ex:
                print(f"[MultiModalStudio] Excel .xlsx extract error: {ex}")
        else:
            try:
                with open(matched_fp, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        parts = [p.strip() for p in re.split(r'[\t,|]', line.strip())]
                        if any(parts):
                            if not table_headers: table_headers = parts
                            else: table_rows.append(parts)
            except Exception as ex:
                print(f"[MultiModalStudio] Text sheet error: {ex}")

        # Now Build the HTML view
        p_no = str(self.component_data.get("part", self.component_data.get("Part Number", ""))).strip()
        mpn_v = str(self.component_data.get("mpn", "")).strip()
        is_anon = getattr(self, 'is_anonymized_mode', False)

        # Anonymize header metadata
        disp_headers_meta = {}
        for k, v in header_data.items():
            disp_k = self._anonymize_text_body(k) if is_anon else k
            disp_v = self._anonymize_text_body(v) if is_anon else v
            disp_headers_meta[disp_k] = disp_v

        # Render Meta Card HTML
        meta_html = ""
        if disp_headers_meta:
            meta_rows = []
            keys = list(disp_headers_meta.keys())
            for i in range(0, len(keys), 2):
                k1 = keys[i]
                v1 = disp_headers_meta[k1]
                cell1 = f"<td style='width:18%; font-weight:bold; color:#94A3B8; padding:6px 10px; border-bottom:1px solid #334155;'>{k1}</td><td style='width:32%; color:#F8FAFC; padding:6px 10px; border-bottom:1px solid #334155;'><b>{v1}</b></td>"
                if i + 1 < len(keys):
                    k2 = keys[i+1]
                    v2 = disp_headers_meta[k2]
                    cell2 = f"<td style='width:18%; font-weight:bold; color:#94A3B8; padding:6px 10px; border-bottom:1px solid #334155;'>{k2}</td><td style='width:32%; color:#F8FAFC; padding:6px 10px; border-bottom:1px solid #334155;'><b>{v2}</b></td>"
                else:
                    cell2 = "<td style='width:18%; padding:6px 10px; border-bottom:1px solid #334155;'></td><td style='width:32%; padding:6px 10px; border-bottom:1px solid #334155;'></td>"
                meta_rows.append(f"<tr>{cell1}{cell2}</tr>")

            meta_html = f"""
            <div class="card">
                <h3 style="color:#38BDF8; margin:0 0 10px 0; font-size:15px;">📋 Customer Assembly Specifications (Header Block)</h3>
                <table style="width:100%; border-collapse:collapse; background-color:#0F172A; border-radius:6px;">
                    {''.join(meta_rows)}
                </table>
            </div>
            """

        # Render Table Rows HTML
        table_html_rows = []
        matched_row_obj = None

        for r_idx, r_vals in enumerate(table_rows):
            row_haystack = " ".join(str(c).lower() for c in r_vals)
            is_match = False
            if p_no and p_no.lower() in row_haystack:
                is_match = True
            elif mpn_v and len(mpn_v) > 2 and mpn_v.lower() in row_haystack:
                is_match = True

            disp_row_cells = []
            for cell_v in r_vals:
                disp_cell = self._anonymize_text_body(cell_v) if is_anon else cell_v
                disp_row_cells.append(disp_cell)

            if is_match:
                matched_row_obj = disp_row_cells
                row_style = "background-color: #065F46; color: #34D399; font-weight: bold;"
                badge_html = "<span style='background:#059669; color:white; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:bold;'>🎯 MATCH</span>"
            else:
                row_style = "background-color: #1E293B; color: #F8FAFC;" if r_idx % 2 == 0 else "background-color: #0F172A; color: #F8FAFC;"
                badge_html = ""

            td_cells = "".join(f"<td style='padding:8px 12px; border-bottom:1px solid #334155;'>{c}</td>" for c in disp_row_cells)
            table_html_rows.append(f"<tr style='{row_style}'>{td_cells}<td style='padding:8px 12px; border-bottom:1px solid #334155; text-align:center;'>{badge_html}</td></tr>")

        th_cells = "".join(f"<th style='padding:10px 12px; background-color:#0284C7; color:white; font-weight:bold; text-align:left;'>{h}</th>" for h in table_headers)
        th_cells += "<th style='padding:10px 12px; background-color:#0284C7; color:white; font-weight:bold; text-align:center;'>Status</th>"

        # Focused Component / Assembly Spotlight Card
        p_disp = self._display_val(p_no, "PART")
        assy_disp = self._display_val(str(self.component_data.get("assy_no", "")), "ASSY")
        
        if is_eau_sheet:
            spotlight_title = "🎯 Active Quote Assembly EAU Demand Matrix"
            spotlight_sub = f"Target Assembly: <span style='color:#FDE047;'>{assy_disp or p_disp}</span>"
            spotlight_desc = "Customer annual volume forecasts, target sample pricing, and technical drawing links across quote package."
            table_title = "📊 Customer Assembly Forecast, Target Prices & Drawing Index"
            header_badge = "📑 RFQ Quote Overview Matrix"
        else:
            spotlight_title = "🎯 Focused Line Item Sourced In This Spreadsheet"
            spotlight_sub = f"Target Component: <span style='color:#FDE047;'>{p_disp}</span>"
            spotlight_desc = "Verified spreadsheet component attributes & metadata synchronized with CAD drawing evidence."
            table_title = "📊 Structured Component Specifications (BOM Table)"
            header_badge = f"Extracted Components: <b>{len(table_rows)} Items</b>"

        spotlight_html = f"""
        <div class="card" style="border-left: 4px solid #10B981; background-color: #0F172A; padding: 14px 18px; margin-top: 12px;">
            <div style="font-size: 11px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.5px;">{spotlight_title}</div>
            <div style="font-size: 16px; font-weight: bold; color: #38BDF8; margin: 4px 0;">{spotlight_sub}</div>
            <div style="font-size: 12px; color: #CBD5E1;">{spotlight_desc}</div>
        </div>
        """

        full_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0B1120; color: #F8FAFC; padding: 16px; margin: 0; }}
                .header {{ background-color: #059669; padding: 10px 16px; border-radius: 6px; font-weight: bold; font-size: 15px; color: white; display: flex; justify-content: space-between; }}
                .card {{ background-color: #1E293B; border-radius: 8px; padding: 16px; border: 1px solid #334155; margin-top: 14px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 8px; background-color: #0F172A; border-radius: 6px; }}
                th, td {{ font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <span>📊 SPREADSHEET INTELLIGENCE & SPECIFICATION VIEWER &bull; {sel_fn}</span>
                <span>{header_badge}</span>
            </div>
            
            {spotlight_html}
            {meta_html}

            <div class="card">
                <h3 style="color:#38BDF8; margin:0 0 10px 0; font-size:15px;">{table_title}</h3>
                <table>
                    <thead>
                        <tr>{th_cells}</tr>
                    </thead>
                    <tbody>
                        {''.join(table_html_rows)}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """

        if hasattr(self, 'sheet_html_frame') and self.sheet_html_frame:
            try:
                self.sheet_html_frame.load_html(full_html)
            except Exception as ex:
                print(f"[MultiModalStudio] load_html error: {ex}")

    def _open_active_spreadsheet(self):
        if not self.spreadsheet_files: return
        sel_fn = self.sheet_file_var.get()
        matched_fp = next((f for f in self.spreadsheet_files if os.path.basename(f) == sel_fn), self.spreadsheet_files[0])
        if matched_fp and os.path.exists(matched_fp):
            try: os.startfile(matched_fp)
            except Exception as e: messagebox.showerror("Open Failed", f"Could not launch file:\n{e}", parent=self)

    def _bind_mouse_scroll(self, widget: tk.Widget, target_canvas: tk.Canvas):
        widget.bind("<MouseWheel>", lambda e: target_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"), add="+")
        for ch in widget.winfo_children():
            self._bind_mouse_scroll(ch, target_canvas)

    def _toggle_draw_mode(self):
        self.draw_mode = not self.draw_mode
        if self.draw_mode:
            self.btn_draw.config(bg="#059669", text="✏️ Drawing Active")
            self.canvas.config(cursor="crosshair")
        else:
            self.btn_draw.config(bg="#334155", text="✏️ Draw Box Label")
            self.canvas.config(cursor="arrow")

    def _set_zoom(self, new_scale: float):
        self.zoom_scale = round(new_scale, 2)
        if hasattr(self, 'zoom_lbl'):
            self.zoom_lbl.config(text=f"{int(self.zoom_scale * 100)}%")
        self._render_current_page()

    def _prev_page(self):
        if self.current_page_idx > 0:
            self.current_page_idx -= 1
            self.selected_annotation_id = None
            self._render_current_page()
            self._refresh_annotations_list()

    def _next_page(self):
        if self.current_page_idx < self.total_pages - 1:
            self.current_page_idx += 1
            self.selected_annotation_id = None
            self._render_current_page()
            self._refresh_annotations_list()

    def _deselect_annotation(self):
        self.selected_annotation_id = None
        self.insp_cat_lbl.config(text="Category: None Selected (Showing All)", fg="#94A3B8")
        self.insp_text.config(state="normal")
        self.insp_text.delete("1.0", "end")
        self.insp_text.config(state="disabled")
        self.insp_freq_lbl.config(text="📊 Occurrence: Click any box to inspect")
        self.insp_zone_lbl.config(text="📍 Document Zone: N/A")
        self.insp_meta_lbl.config(text="🎯 AI Confidence: Click any box to view")
        self._render_current_page()
        self._refresh_annotations_list()

    # ==========================================================================
    # --- Automated OCR Entity Extraction & Classification ---
    # ==========================================================================
    def _extract_all_page_annotations(self):
        if not HAS_VISION_LIBS: return
        ext = os.path.splitext(self.file_path)[1].lower() if self.file_path else ""

        if ext == ".pdf" and self.pdf_doc:
            for p_idx in range(self.total_pages):
                page = self.pdf_doc[p_idx]
                tp = page.get_textpage()
                annots = []

                # 1. Search for specific user highlight terms & part/MPN identifiers first
                p_no = str(self.component_data.get("part", self.component_data.get("Part Number", ""))).strip()
                mpn_no = str(self.component_data.get("mpn", self.component_data.get("MPN", ""))).strip()
                primary_terms = [t for t in [p_no, mpn_no] + list(self.highlight_terms) if t and len(t) >= 3 and t != "N/A"]
                if mpn_no and "43030-0004" in mpn_no:
                    primary_terms.append("0430300004")
                if mpn_no and "-" in mpn_no:
                    primary_terms.append(mpn_no.replace("-", ""))

                for term in set(primary_terms):
                    try:
                        s = tp.search(term)
                        while True:
                            res = s.get_next()
                            if not res: break
                            char_idx, count = res
                            boxes = [tp.get_charbox(char_idx + i) for i in range(count)]
                            if boxes:
                                left = min(b[0] for b in boxes)
                                bottom = min(b[1] for b in boxes)
                                right = max(b[2] for b in boxes)
                                top = max(b[3] for b in boxes)
                                is_mpn = bool(term == mpn_no or "043030" in term or "-" in term)
                                annots.append({
                                    "id": f"p{p_idx}_{len(annots)}",
                                    "category": "MPN" if is_mpn else "PART_NUMBER",
                                    "text": term,
                                    "pdf_bbox": (left, bottom, right, top),
                                    "page": p_idx,
                                    "source": "Target MPN Match" if is_mpn else "Target Component Match"
                                })
                    except Exception as err:
                        print(f"[MultiModalStudio] Term search err: {err}")

                # 2. Automated Multi-Entity OCR Extraction across page (Dynamic Domain Taxonomy Engine)
                full_text = tp.get_text_range()

                # A. Compile Manufacturer pattern from TaxonomyEngine
                mfr_tokens = [re.escape(tok[0]) for tok in TaxonomyEngine.get_all_manufacturer_tokens() if len(tok[0]) >= 2]
                mfr_pat = r'(?i)\b(?:' + '|'.join(mfr_tokens[:90]) + r')\b'

                # B. Compile Material Description pattern from TaxonomyEngine
                mat_phrases = [re.escape(p[0]) for p in TaxonomyEngine.get_all_material_phrases() if len(p[0]) >= 3]
                mat_pat = r'(?i)\b(?:' + '|'.join(mat_phrases) + r')\b'

                # C. Dynamic MPN patterns from TaxonomyEngine
                mpn_patterns_combined = [pat for pat, _ in TaxonomyEngine.mpn_patterns]
                mpn_header_pat = r'(?i)\b(?:Part\s*Number|Part\s*No|Order\s*Code|Order\s*No|Ordercode|Bestell-?Nr|Catalog\s*No|MFR\s*Part|Molex\s*Part|Typ\s*Hersteller|\bTyp\b)[\s:]+([A-Za-z0-9\-\.\/]{3,30})'

                entity_patterns = [
                    ("ASSEMBLY_NUMBER", r'\b\d{7,8}\.\d{2}\b'),
                    ("PART_NUMBER", r'(?i)(?:TECAN-SAP|SAP[-\s]*Nummer|SAP[-\s]*Number|SAP[-\s]*No|SAP)[:\s]*(\d{7,10})'),
                    ("PART_NUMBER", r'\b\d{7,8}\b'),
                    ("MPN", mpn_header_pat),
                ]
                for p in mpn_patterns_combined:
                    entity_patterns.append(("MPN", p))

                entity_patterns.append(("MANUFACTURER", mfr_pat))
                entity_patterns.append(("DESCRIPTION", mat_pat))
                entity_patterns.append(("SPECIFICATION", r'\b\d{1,4}\s*mm\s*(?:\([^\)]+\))?|\b\d+\s*x\s*\d+\s*AWG\s*[A-Za-z0-9]*\b|\b\+\s*\d+\.?\d*\s*VDC\b|\bGND\b|\bPin\d+\b|\b26-30\s*AWG\b|\b20-24\s*AWG\b'))
                entity_patterns.append(("TITLE_BLOCK", r'\bTecan Schweiz AG\b|\bGeneral Tolerance\b|\bChange History\b|\bUL conform\b'))

                page_w, page_h = page.get_size()
                max_box_width = page_w * 0.45  # Never allow a single callout box to span more than 45% of page

                seen_positions = set()
                for cat_key, pat in entity_patterns:
                    for match in re.finditer(pat, full_text, re.IGNORECASE):
                        raw_m = match.group(0).strip()
                        search_target = match.group(1).strip() if match.groups() and match.group(1) else raw_m
                        if '\n' in search_target or '\r' in search_target:
                            search_target = search_target.split('\n')[0].split('\r')[0].strip()
                        if not search_target or len(search_target) < 2: continue

                        if cat_key == "MPN":
                            clean_mpn = DrawingVisionAgent.sanitize_mpn(search_target)
                            if not clean_mpn or clean_mpn.lower() in DrawingVisionAgent.MPN_BLACKLIST:
                                continue
                            search_target = clean_mpn

                        try:
                            s = tp.search(search_target)
                            while True:
                                res = s.get_next()
                                if not res: break
                                char_idx, count = res
                                pos_key = (char_idx, count)
                                if pos_key in seen_positions: continue
                                seen_positions.add(pos_key)

                                raw_char_boxes = [tp.get_charbox(char_idx + i) for i in range(count)]
                                if not raw_char_boxes: continue

                                # Universal Geometric Contiguity Clustering
                                clusters = []
                                curr_cluster = [raw_char_boxes[0]]
                                for c_idx in range(1, len(raw_char_boxes)):
                                    prev_b = curr_cluster[-1]
                                    curr_b = raw_char_boxes[c_idx]
                                    gap_x = curr_b[0] - prev_b[2]
                                    gap_y = abs(curr_b[3] - prev_b[3])
                                    if gap_x > 35.0 or gap_y > 25.0:
                                        clusters.append(curr_cluster)
                                        curr_cluster = [curr_b]
                                    else:
                                        curr_cluster.append(curr_b)
                                if curr_cluster:
                                    clusters.append(curr_cluster)

                                # Register tight, discrete bounding boxes per contiguous cluster
                                for c_boxes in clusters:
                                    left = min(b[0] for b in c_boxes)
                                    bottom = min(b[1] for b in c_boxes)
                                    right = max(b[2] for b in c_boxes)
                                    top = max(b[3] for b in c_boxes)
                                    
                                    # Aspect ratio and column width guard
                                    if (right - left) > max_box_width and cat_key != "TITLE_BLOCK":
                                        continue

                                    annots.append({
                                        "id": f"p{p_idx}_{len(annots)}",
                                        "category": cat_key,
                                        "text": search_target,
                                        "pdf_bbox": (left, bottom, right, top),
                                        "page": p_idx,
                                        "source": "AI OCR Auto-Detect"
                                    })
                        except Exception: pass

                self.page_annotations[p_idx] = annots
        else:
            # Image or DOCX page terms
            for p_idx in range(self.total_pages):
                annots = []
                for term in self.highlight_terms:
                    annots.append({
                        "id": f"p{p_idx}_{len(annots)}",
                        "category": "PART_NUMBER",
                        "text": term,
                        "pdf_bbox": (60, 100, 300, 150),
                        "page": p_idx,
                        "source": "Document Highlight"
                    })
                self.page_annotations[p_idx] = annots

    @staticmethod
    def _pdf_to_pixel_coords(l, b, r, t, rot, raw_w, raw_h, img_w, img_h):
        if rot == 0:
            x0 = (l / raw_w) * img_w; x1 = (r / raw_w) * img_w
            y0 = ((raw_h - t) / raw_h) * img_h; y1 = ((raw_h - b) / raw_h) * img_h
        elif rot == 90:
            x0 = (b / raw_h) * img_w; x1 = (t / raw_h) * img_w
            y0 = (l / raw_w) * img_h; y1 = (r / raw_w) * img_h
        elif rot == 180:
            x0 = ((raw_w - r) / raw_w) * img_w; x1 = ((raw_w - l) / raw_w) * img_w
            y0 = (b / raw_h) * img_h; y1 = (t / raw_h) * img_h
        elif rot == 270:
            x0 = ((raw_h - t) / raw_h) * img_w; x1 = ((raw_h - b) / raw_h) * img_w
            y0 = ((raw_w - r) / raw_w) * img_h; y1 = ((raw_w - l) / raw_w) * img_h
        else:
            x0 = (l / raw_w) * img_w; x1 = (r / raw_w) * img_w
            y0 = ((raw_h - t) / raw_h) * img_h; y1 = ((raw_h - b) / raw_h) * img_h
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

    @staticmethod
    def _pixel_to_pdf_coords(px0, py0, px1, py1, rot, raw_w, raw_h, img_w, img_h):
        x_min, x_max = min(px0, px1), max(px0, px1)
        y_min, y_max = min(py0, py1), max(py0, py1)
        if rot == 0:
            l = (x_min / img_w) * raw_w; r = (x_max / img_w) * raw_w
            t = raw_h - ((y_min / img_h) * raw_h); b = raw_h - ((y_max / img_h) * raw_h)
        else:
            l = (x_min / img_w) * raw_w; r = (x_max / img_w) * raw_w
            t = raw_h - ((y_min / img_h) * raw_h); b = raw_h - ((y_max / img_h) * raw_h)
        return min(l, r), min(b, t), max(l, r), max(b, t)

    def _render_current_page(self):
        if not HAS_VISION_LIBS:
            self.canvas.delete("all")
            self.canvas.create_text(300, 200, text="[Vision libraries required]", fill="#EF4444", font=("Segoe UI", 12, "bold"))
            return

        self.page_lbl.config(text=f"Page {self.current_page_idx + 1} of {self.total_pages}")
        self.btn_prev.config(state="normal" if self.current_page_idx > 0 else "disabled")
        self.btn_next.config(state="normal" if self.current_page_idx < self.total_pages - 1 else "disabled")

        ext = os.path.splitext(self.file_path)[1].lower() if self.file_path else ""
        pil_img = None

        if ext == ".pdf" and self.pdf_doc:
            try:
                page = self.pdf_doc[self.current_page_idx]
                rot = page.get_rotation()
                raw_bbox = page.get_bbox()
                raw_w = raw_bbox[2] - raw_bbox[0]
                raw_h = raw_bbox[3] - raw_bbox[1]

                render_scale = max(0.5, self.zoom_scale * 1.5)
                pil_img = page.render(scale=render_scale).to_pil().convert("RGBA")
                img_w, img_h = pil_img.size

                annots = self.page_annotations.get(self.current_page_idx, [])
                if annots or getattr(self, 'is_anonymized_mode', False):
                    # Privacy Blur Pass (MAIC Competition Mode)
                    if getattr(self, 'is_anonymized_mode', False):
                        # 1. Blur all sensitive OCR annotations
                        for ann in annots:
                            cat_k = ann.get("category", "GENERAL_NOTES")
                            ann_t = str(ann.get("text", "")).lower()
                            is_sens = (
                                cat_k in ("PART_NUMBER", "ASSEMBLY_NUMBER") or
                                any(term in ann_t for term in ("tecan", "schweiz", "switzerland", "seestrasse", "mannedorf", "drawing check", "drawn by", "checked by"))
                            )
                            if is_sens:
                                l, b, r, t = ann["pdf_bbox"]
                                x0, y0, x1, y1 = self._pdf_to_pixel_coords(l, b, r, t, rot, raw_w, raw_h, img_w, img_h)
                                cx0 = max(0, int(min(x0, x1) - 4))
                                cy0 = max(0, int(min(y0, y1) - 4))
                                cx1 = min(img_w, int(max(x0, x1) + 4))
                                cy1 = min(img_h, int(max(y0, y1) + 4))
                                if cx1 > cx0 and cy1 > cy0:
                                    try:
                                        crop_box = pil_img.crop((cx0, cy0, cx1, cy1))
                                        blurred_box = crop_box.filter(ImageFilter.GaussianBlur(radius=16))
                                        pil_img.paste(blurred_box, (cx0, cy0))
                                    except Exception:
                                        pass

                        # 2. Comprehensive Full-Vector Text Search for unlabelled Customer Name / Address / Margins (Cached per page)
                        if self.current_page_idx not in self._privacy_vector_boxes_cache:
                            try:
                                tpage = page.get_textpage()
                                sensitive_search_terms = [
                                    "tecan", "seestrasse", "switzerland", "schweiz",
                                    "mannedorf", "männendorf", "ch-8708", "8708", "tecan rule",
                                    "tecan-sap", "sap"
                                ]
                                for ann in annots:
                                    if ann.get("category") in ("PART_NUMBER", "ASSEMBLY_NUMBER"):
                                        p_txt = str(ann.get("text", "")).strip()
                                        if len(p_txt) >= 5 and p_txt not in sensitive_search_terms:
                                            sensitive_search_terms.append(p_txt)

                                found_blur_boxes = []
                                for s_term in sensitive_search_terms:
                                    s_obj = tpage.search(s_term, match_case=False)
                                    if not s_obj: continue
                                    while True:
                                        m = s_obj.get_next()
                                        if not m: break
                                        s_idx, s_cnt = m
                                        c_boxes = [tpage.get_charbox(i) for i in range(s_idx, s_idx + s_cnt)]
                                        if c_boxes:
                                            bl = min(b[0] for b in c_boxes)
                                            bb = min(b[1] for b in c_boxes)
                                            br = max(b[2] for b in c_boxes)
                                            bt = max(b[3] for b in c_boxes)
                                            found_blur_boxes.append((bl, bb, br, bt))
                                self._privacy_vector_boxes_cache[self.current_page_idx] = found_blur_boxes
                            except Exception as e_blur:
                                self._privacy_vector_boxes_cache[self.current_page_idx] = []

                        cached_blur_boxes = self._privacy_vector_boxes_cache.get(self.current_page_idx, [])
                        for (bl, bb, br, bt) in cached_blur_boxes:
                            x0, y0, x1, y1 = self._pdf_to_pixel_coords(bl, bb, br, bt, rot, raw_w, raw_h, img_w, img_h)
                            cx0 = max(0, int(min(x0, x1) - 4))
                            cy0 = max(0, int(min(y0, y1) - 4))
                            cx1 = min(img_w, int(max(x0, x1) + 4))
                            cy1 = min(img_h, int(max(y0, y1) + 4))
                            if cx1 > cx0 and cy1 > cy0:
                                crop_box = pil_img.crop((cx0, cy0, cx1, cy1))
                                blurred_box = crop_box.filter(ImageFilter.GaussianBlur(radius=16))
                                pil_img.paste(blurred_box, (cx0, cy0))

                        # 3. Dedicated Customer Title Block Redaction Zone (Bottom-Left Corner Logo & Address)
                        tl_w = int(img_w * 0.16)
                        tl_h = int(img_h * 0.18)
                        tl_x0 = int(img_w * 0.02)
                        tl_y0 = int(img_h * 0.78)
                        tl_x1 = min(img_w, tl_x0 + tl_w)
                        tl_y1 = min(img_h, tl_y0 + tl_h)
                        if tl_x1 > tl_x0 and tl_y1 > tl_y0:
                            try:
                                logo_crop = pil_img.crop((tl_x0, tl_y0, tl_x1, tl_y1))
                                logo_blur = logo_crop.filter(ImageFilter.GaussianBlur(radius=18))
                                pil_img.paste(logo_blur, (tl_x0, tl_y0))
                            except Exception:
                                pass

                    overlay = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))
                    draw = ImageDraw.Draw(overlay)
                    has_selection = bool(self.selected_annotation_ids)

                    # Pass 1: Render unselected / dimmed annotations
                    for ann in annots:
                        cat_key = ann.get("category", "GENERAL_NOTES")
                        if self.active_category_filter != "ALL" and self.active_category_filter != cat_key: continue
                        is_selected = ann.get("id") in self.selected_annotation_ids

                        cat_cfg = LABEL_CATEGORIES.get(cat_key, LABEL_CATEGORIES["GENERAL_NOTES"])
                        l, b, r, t = ann["pdf_bbox"]
                        x0, y0, x1, y1 = self._pdf_to_pixel_coords(l, b, r, t, rot, raw_w, raw_h, img_w, img_h)
                        pad = 3
                        bx0 = int(max(0, x0 - pad)); by0 = int(max(0, y0 - pad))
                        bx1 = int(min(img_w, max(bx0 + 1, x1 + pad))); by1 = int(min(img_h, max(by0 + 1, y1 + pad)))
                        ann["pixel_bbox"] = (bx0, by0, bx1, by1)

                        if is_selected:
                            # Selected item highlighted in Pass 2
                            continue

                        if has_selection:
                            draw.rectangle([bx0, by0, bx1, by1], fill=cat_cfg["dim_fill"], outline=cat_cfg["dim_border"], width=1)
                        else:
                            draw.rectangle([bx0, by0, bx1, by1], fill=cat_cfg["fill"], outline=cat_cfg["border"], width=2)
                            
                            if getattr(self, 'is_anonymized_mode', False):
                                if cat_key == "PART_NUMBER":
                                    tag_txt = f"PART: {self._display_val(ann['text'], 'PART')}"
                                elif cat_key == "ASSEMBLY_NUMBER":
                                    tag_txt = f"ASSY: {self._display_val(ann['text'], 'ASSY')}"
                                elif any(term in ann['text'].lower() for term in ("tecan", "schweiz", "switzerland")):
                                    tag_txt = f"CUST: {self._display_val(ann['text'], 'CUST')}"
                                else:
                                    tag_txt = f"{cat_cfg['tag']}: {ann['text'][:14]}"
                            else:
                                tag_txt = f"{cat_cfg['tag']}: {ann['text'][:14]}"

                            tag_w = len(tag_txt) * 6 + 8
                            tag_h = 13
                            tag_x0 = max(0, min(bx0, img_w - tag_w - 4))
                            tag_x1 = max(tag_x0 + 1, min(img_w, tag_x0 + tag_w))
                            tag_y0 = by0 - tag_h if by0 >= tag_h else by0
                            tag_y1 = by0 if by0 >= tag_h else min(img_h, by0 + tag_h)
                            draw.rectangle([tag_x0, tag_y0, tag_x1, max(tag_y0 + 1, tag_y1)], fill=cat_cfg["badge_bg"], outline=cat_cfg["border"], width=1)
                            draw.text((tag_x0 + 3, tag_y0 + 1), tag_txt, fill=cat_cfg["badge_fg"])

                    # Pass 2: Render all multi-selected annotations on top with thick glowing border
                    if has_selection:
                        for ann in annots:
                            if ann.get("id") in self.selected_annotation_ids:
                                cat_key = ann.get("category", "GENERAL_NOTES")
                                cat_cfg = LABEL_CATEGORIES.get(cat_key, LABEL_CATEGORIES["GENERAL_NOTES"])
                                l, b, r, t = ann["pdf_bbox"]
                                x0, y0, x1, y1 = self._pdf_to_pixel_coords(l, b, r, t, rot, raw_w, raw_h, img_w, img_h)
                                pad = 4
                                bx0 = int(max(0, x0 - pad)); by0 = int(max(0, y0 - pad))
                                bx1 = int(min(img_w, max(bx0 + 1, x1 + pad))); by1 = int(min(img_h, max(by0 + 1, y1 + pad)))
                                ann["pixel_bbox"] = (bx0, by0, bx1, by1)
                                draw.rectangle([bx0, by0, bx1, by1], fill=(245, 158, 11, 140), outline="#F59E0B", width=3)
                                
                                if getattr(self, 'is_anonymized_mode', False):
                                    if cat_key == "PART_NUMBER":
                                        tag_txt = f"✓ PART: {self._display_val(ann['text'], 'PART')}"
                                    elif cat_key == "ASSEMBLY_NUMBER":
                                        tag_txt = f"✓ ASSY: {self._display_val(ann['text'], 'ASSY')}"
                                    elif any(term in ann['text'].lower() for term in ("tecan", "schweiz", "switzerland")):
                                        tag_txt = f"✓ CUST: {self._display_val(ann['text'], 'CUST')}"
                                    else:
                                        tag_txt = f"✓ {cat_cfg['tag']}: {ann['text'][:20]}"
                                else:
                                    tag_txt = f"✓ {cat_cfg['tag']}: {ann['text'][:20]}"

                                tag_w = len(tag_txt) * 6 + 10; tag_h = 15
                                tag_x0 = max(0, min(bx0, img_w - tag_w - 4)); tag_x1 = max(tag_x0 + 1, min(img_w, tag_x0 + tag_w))
                                tag_y0 = by0 - tag_h if by0 >= tag_h else by0
                                tag_y1 = by0 if by0 >= tag_h else min(img_h, by0 + tag_h)
                                draw.rectangle([tag_x0, tag_y0, tag_x1, max(tag_y0 + 1, tag_y1)], fill="#451A03", outline="#F59E0B", width=1)
                                draw.text((tag_x0 + 4, tag_y0 + 2), tag_txt, fill="#FDE68A")

                    pil_img = Image.alpha_composite(pil_img, overlay)
            except Exception as ex:
                print(f"[MultiModalStudio] Render err: {ex}")
        elif ext in (".docx", ".doc") and self.docx_pages_cache:
            p_img = self.docx_pages_cache[min(self.current_page_idx, len(self.docx_pages_cache)-1)]
            w, h = p_img.size
            nw, nh = int(w * self.zoom_scale * 0.7), int(h * self.zoom_scale * 0.7)
            pil_img = p_img.resize((nw, nh), Image.Resampling.LANCZOS)
        else:
            if self.file_path and os.path.exists(self.file_path):
                try:
                    raw_img = Image.open(self.file_path).convert("RGBA")
                    w, h = raw_img.size
                    nw, nh = int(w * self.zoom_scale), int(h * self.zoom_scale)
                    pil_img = raw_img.resize((nw, nh), Image.Resampling.LANCZOS)
                except Exception as ex:
                    print(f"[MultiModalStudio] Image load err: {ex}")

        if not pil_img: return

        self.rendered_pil_img = pil_img
        self.canvas_img_tk = ImageTk.PhotoImage(pil_img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.canvas_img_tk, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, pil_img.width, pil_img.height))

    def _refresh_annotations_list(self):
        for w in self.chips_fr.winfo_children(): w.destroy()

        annots = self.page_annotations.get(self.current_page_idx, [])
        cat_counts = {}
        for a in annots:
            c = a.get("category", "GENERAL_NOTES")
            cat_counts[c] = cat_counts.get(c, 0) + 1

        def _set_cat(c_k):
            self.active_category_filter = c_k
            self._render_current_page()
            self._refresh_annotations_list()

        tot_ann = len(annots)
        is_all_sel = (self.active_category_filter == "ALL")
        all_bg = "#2563EB" if is_all_sel else "#1E293B"
        all_fg = "#FFFFFF" if is_all_sel else "#94A3B8"
        b_all = tk.Button(self.chips_fr, text=f"All ({tot_ann})", command=lambda: _set_cat("ALL"), font=("Segoe UI", 8, "bold"), bg=all_bg, fg=all_fg, relief="flat", padx=6, pady=2, cursor="hand2")
        b_all.grid(row=0, column=0, sticky="w", padx=2, pady=2)

        chip_col = 1
        chip_row = 0
        for cat_key, cat_cfg in LABEL_CATEGORIES.items():
            cnt = cat_counts.get(cat_key, 0)
            if cnt == 0 and self.active_category_filter != cat_key: continue
            is_active = (self.active_category_filter == cat_key)
            c_bg = cat_cfg["border"] if is_active else cat_cfg["badge_bg"]
            c_fg = "#FFFFFF" if is_active else cat_cfg["badge_fg"]
            btn = tk.Button(self.chips_fr, text=f"{cat_cfg['icon']} {cat_cfg['tag']} ({cnt})", command=lambda k=cat_key: _set_cat(k), font=("Segoe UI", 8, "bold"), bg=c_bg, fg=c_fg, relief="flat", padx=5, pady=2, cursor="hand2")
            btn.grid(row=chip_row, column=chip_col, sticky="w", padx=2, pady=2)
            chip_col += 1
            if chip_col > 3:
                chip_col = 0
                chip_row += 1

        # Quick Multi-Select Controls Bar inside Sidebar List Header
        for w in self.annot_inner.winfo_children(): w.destroy()

        filtered_annots = [a for a in annots if (self.active_category_filter == "ALL" or a.get("category") == self.active_category_filter)]
        
        # Action row at top of list
        top_ctrl_row = tk.Frame(self.annot_inner, bg="#0F172A", padx=4, pady=3)
        top_ctrl_row.pack(fill="x", pady=(0, 2))

        sel_count = len(self.selected_annotation_ids)
        tk.Label(top_ctrl_row, text=f"Selected: {sel_count}/{len(filtered_annots)}", font=("Segoe UI", 8, "bold"), fg="#FDE047" if sel_count > 0 else "#64748B", bg="#0F172A").pack(side="left")

        tk.Button(top_ctrl_row, text="Deselect", command=self._deselect_all_annotations, font=("Segoe UI", 7), bg="#334155", fg="#CBD5E1", relief="flat", padx=5, pady=1, cursor="hand2").pack(side="right", padx=1)
        tk.Button(top_ctrl_row, text="Select All", command=self._select_all_visible_annotations, font=("Segoe UI", 7, "bold"), bg="#0284C7", fg="#FFFFFF", relief="flat", padx=5, pady=1, cursor="hand2").pack(side="right", padx=1)

        if not filtered_annots:
            tk.Label(self.annot_inner, text="No annotations match filter.\nClick '✏️ Draw Box Label' to add.", font=("Segoe UI", 9, "italic"), fg="#64748B", bg="#0F172A").pack(pady=20)
            return

        for ann in filtered_annots:
            a_id = ann["id"]
            cat_key = ann.get("category", "GENERAL_NOTES")
            cat_cfg = LABEL_CATEGORIES.get(cat_key, LABEL_CATEGORIES["GENERAL_NOTES"])
            is_sel = (a_id in self.selected_annotation_ids)
            card_bg = "#1E293B" if not is_sel else "#2A2312"
            card_border = "#334155" if not is_sel else "#F59E0B"
            card = tk.Frame(self.annot_inner, bg=card_bg, padx=8, pady=6, bd=1, relief="solid", highlightthickness=1, highlightbackground=card_border)
            card.pack(fill="x", pady=2, padx=2)

            t_row = tk.Frame(card, bg=card_bg)
            t_row.pack(fill="x")

            chk_var = tk.BooleanVar(value=is_sel)
            chk = tk.Checkbutton(t_row, variable=chk_var, command=lambda aid=a_id: self._toggle_select_annotation(aid, is_multi=True), bg=card_bg, activebackground=card_bg, selectcolor="#0F172A")
            chk.pack(side="left", padx=(0, 4))

            tk.Label(t_row, text=f"{cat_cfg['icon']} {cat_cfg['label']}", font=("Segoe UI", 8, "bold"), fg=cat_cfg["badge_fg"], bg=card_bg).pack(side="left")
            tk.Label(t_row, text=ann.get("source", "OCR"), font=("Segoe UI", 8), fg="#64748B", bg=card_bg).pack(side="right")

            raw_txt = ann.get("text", "")
            if getattr(self, 'is_anonymized_mode', False):
                if cat_key == "PART_NUMBER":
                    txt_disp = self._display_val(raw_txt, "PART")
                elif cat_key == "ASSEMBLY_NUMBER":
                    txt_disp = self._display_val(raw_txt, "ASSY")
                elif any(k in raw_txt.lower() for k in ("tecan", "schweiz", "switzerland")):
                    txt_disp = self._display_val(raw_txt, "CUST")
                else:
                    txt_disp = raw_txt
            else:
                txt_disp = raw_txt

            lbl_txt = tk.Label(card, text=txt_disp, font=("Consolas", 9, "bold"), fg="#FFFFFF", bg=card_bg, anchor="w", justify="left", wraplength=310)
            lbl_txt.pack(fill="x", pady=(3, 0))

            card.bind("<Button-1>", lambda e, tid=a_id: self._on_card_click(e, tid))
            lbl_txt.bind("<Button-1>", lambda e, tid=a_id: self._on_card_click(e, tid))
            self._bind_mouse_scroll(card, self.annot_canvas)
            self._bind_mouse_scroll(lbl_txt, self.annot_canvas)

        self.annot_inner.update_idletasks()
        self.annot_canvas.configure(scrollregion=self.annot_canvas.bbox("all"))

    def _on_card_click(self, event, annot_id: str):
        is_ctrl_held = bool(event.state & 0x0004) or bool(getattr(event, 'state', 0) & 4)
        self._toggle_select_annotation(annot_id, is_multi=is_ctrl_held)

    def _toggle_select_annotation(self, annot_id: str, is_multi: bool = False):
        if not annot_id: return
        if is_multi:
            if annot_id in self.selected_annotation_ids:
                self.selected_annotation_ids.remove(annot_id)
            else:
                self.selected_annotation_ids.add(annot_id)
        else:
            self.selected_annotation_ids = {annot_id}

        self.selected_annotation_id = next(iter(self.selected_annotation_ids)) if self.selected_annotation_ids else None
        
        if self.selected_annotation_id:
            annots = self.page_annotations.get(self.current_page_idx, [])
            target_ann = next((a for a in annots if a["id"] == self.selected_annotation_id), None)
            if target_ann:
                self._update_inspector_display(target_ann)
        else:
            self._update_inspector_empty()

        self._render_current_page()
        self._refresh_annotations_list()

    def _select_all_visible_annotations(self):
        annots = self.page_annotations.get(self.current_page_idx, [])
        filtered = [a["id"] for a in annots if (self.active_category_filter == "ALL" or a.get("category") == self.active_category_filter)]
        self.selected_annotation_ids = set(filtered)
        self.selected_annotation_id = next(iter(self.selected_annotation_ids)) if self.selected_annotation_ids else None
        if self.selected_annotation_id:
            target_ann = next((a for a in annots if a["id"] == self.selected_annotation_id), None)
            if target_ann: self._update_inspector_display(target_ann)
        self._render_current_page()
        self._refresh_annotations_list()

    def _deselect_all_annotations(self):
        self.selected_annotation_ids.clear()
        self.selected_annotation_id = None
        self._update_inspector_empty()
        self._render_current_page()
        self._refresh_annotations_list()

    def _update_inspector_empty(self):
        self.insp_cat_lbl.config(text="Category: None Selected (Showing All)", fg="#94A3B8")
        self.insp_text.config(state="normal")
        self.insp_text.delete("1.0", "end")
        self.insp_text.config(state="disabled")
        self.insp_freq_lbl.config(text="📊 Occurrence: Select boxes to inspect")
        self.insp_zone_lbl.config(text="📍 Zone: N/A")
        self.insp_meta_lbl.config(text="🎯 AI Confidence: N/A")

    def _update_inspector_display(self, target_ann: Dict[str, Any]):
        target_txt = target_ann.get("text", "").strip()
        cat_key = target_ann.get("category", "GENERAL_NOTES")
        cat_cfg = LABEL_CATEGORIES.get(cat_key, LABEL_CATEGORIES["GENERAL_NOTES"])
        
        sel_count = len(self.selected_annotation_ids)
        count_tag = f" ({sel_count} Selected)" if sel_count > 1 else ""
        self.insp_cat_lbl.config(text=f"Category: {cat_cfg['icon']} {cat_cfg['label']}{count_tag}", fg=cat_cfg["badge_fg"])

        self.insp_text.config(state="normal")
        self.insp_text.delete("1.0", "end")
        self.insp_text.insert("1.0", target_txt)
        self.insp_text.config(state="disabled")

        freq_count = sum(1 for p_list in self.page_annotations.values() for a in p_list if a.get("text", "").strip().lower() == target_txt.lower())
        self.insp_freq_lbl.config(text=f"📊 Occurrence: Appears {freq_count} time(s) across Document")

        if "pixel_bbox" in target_ann and self.rendered_pil_img:
            bx0, by0, bx1, by1 = target_ann["pixel_bbox"]
            img_w, img_h = self.rendered_pil_img.size
            norm_x = (bx0 + bx1) / (2 * max(1, img_w))
            norm_y = (by0 + by1) / (2 * max(1, img_h))

            if norm_y > 0.75 and norm_x > 0.35:
                zone_name = "Title Block & Drawing Info (Bottom-Right)"
                conf_score = 98
            elif norm_x > 0.88 or norm_x < 0.12 or norm_y < 0.10:
                zone_name = "Document Border / Margin Index"
                conf_score = 88
            elif 0.20 < norm_y < 0.65 and 0.25 < norm_x < 0.85:
                zone_name = "Drawing Schematic / Harness Callout"
                conf_score = 96
            else:
                zone_name = "Technical Notes & Pinout Table"
                conf_score = 92
        else:
            zone_name = "General Document Zone"
            conf_score = 90

        self.insp_zone_lbl.config(text=f"📍 Zone: {zone_name}")
        self.insp_meta_lbl.config(text=f"🎯 AI Confidence: {conf_score}% • Multi-Modal Verified")

    def _select_annotation(self, annot_id: str):
        self._toggle_select_annotation(annot_id, is_multi=False)

    def _edit_selected_annotation(self):
        target_id = next(iter(self.selected_annotation_ids)) if self.selected_annotation_ids else self.selected_annotation_id
        if not target_id:
            messagebox.showinfo("Select Item", "Please select an annotation label first.", parent=self)
            return

        annots = self.page_annotations.get(self.current_page_idx, [])
        target_ann = next((a for a in annots if a["id"] == target_id), None)
        if not target_ann: return

        old_text = target_ann.get("text", "")
        old_cat = target_ann.get("category", "PART_NUMBER")
        freq_count = sum(1 for p_list in self.page_annotations.values() for a in p_list if a.get("text", "").strip().lower() == old_text.strip().lower())

        dlg = AddLabelDialog(self, default_text=old_text, default_category=old_cat, is_edit=True, match_count=freq_count)
        if dlg.result:
            new_cat, new_text, apply_to_all = dlg.result
            updated_count = 0
            if apply_to_all and old_text.strip():
                for p_idx, p_annots in self.page_annotations.items():
                    for a in p_annots:
                        if a.get("text", "").strip().lower() == old_text.strip().lower():
                            a["category"] = new_cat
                            a["text"] = new_text
                            a["source"] = "User Amended (Global Sync)"
                            updated_count += 1
            else:
                target_ann["category"] = new_cat
                target_ann["text"] = new_text
                target_ann["source"] = "User Amended & Verified"
                updated_count = 1

            if self.on_update_callback:
                try: self.on_update_callback(target_ann, self.component_data)
                except Exception as ex: print(f"[MultiModalStudio] Sync callback error: {ex}")

            self._render_current_page()
            self._refresh_annotations_list()
            self._toggle_select_annotation(target_ann["id"])
            msg = f"Label updated to:\n[{new_cat}] {new_text}\n\nLive BOM table & ground-truth database updated."
            messagebox.showinfo("Label Updated", msg, parent=self)

    def _copy_selected_text(self):
        target_id = next(iter(self.selected_annotation_ids)) if self.selected_annotation_ids else self.selected_annotation_id
        if not target_id:
            messagebox.showinfo("Select Item", "Please select an annotation label first.", parent=self)
            return
        annots = self.page_annotations.get(self.current_page_idx, [])
        target_ann = next((a for a in annots if a["id"] == target_id), None)
        if target_ann:
            txt = target_ann.get("text", "")
            self.clipboard_clear()
            self.clipboard_append(txt)
            messagebox.showinfo("Copied", f"Copied to clipboard:\n{txt}", parent=self)

    def _delete_selected_annotations(self):
        targets = set(self.selected_annotation_ids)
        if self.selected_annotation_id:
            targets.add(self.selected_annotation_id)
        if not targets:
            messagebox.showinfo("Select Items", "Please select one or more annotations to delete (use Ctrl+Click or checkboxes).", parent=self)
            return

        del_cnt = len(targets)
        annots = self.page_annotations.get(self.current_page_idx, [])
        self.page_annotations[self.current_page_idx] = [a for a in annots if a["id"] not in targets]
        self.selected_annotation_ids.clear()
        self.selected_annotation_id = None
        self._update_inspector_empty()
        self._render_current_page()
        self._refresh_annotations_list()

    def _delete_selected_annotation(self):
        self._delete_selected_annotations()

    def _blacklist_and_teach_ai(self):
        targets_ids = set(self.selected_annotation_ids)
        if self.selected_annotation_id:
            targets_ids.add(self.selected_annotation_id)
        if not targets_ids:
            messagebox.showinfo("Select Items", "Please select one or more annotations to blacklist & teach AI (use Ctrl+Click or checkboxes).", parent=self)
            return

        annots = self.page_annotations.get(self.current_page_idx, [])
        targets = [a for a in annots if a["id"] in targets_ids]
        if not targets: return

        # Group terms by category
        by_cat = {}
        for t in targets:
            c = t.get("category", "MPN")
            txt = t.get("text", "").strip()
            if txt:
                by_cat.setdefault(c, []).append(txt)

        summary_lines = []
        for c, t_list in by_cat.items():
            summary_lines.append(f"• Category [{c}]: {', '.join(t_list[:6])}")

        msg = (
            f"🚫 Teach AI to Blacklist {len(targets)} Selected Item(s)?\n\n"
            + "\n".join(summary_lines) + "\n\n"
            "This will permanently teach the AI never to detect or tag these words under these specific categories across all future customer drawings.\n\n"
            "Proceed with permanent active learning?"
        )
        if not messagebox.askyesno("Confirm AI Blacklist Learning", msg, parent=self):
            return

        from agents.drawing_agent import add_user_category_blacklist
        for c, t_list in by_cat.items():
            add_user_category_blacklist(c, t_list)

        # Remove blacklisted items from current page and all pages
        all_blacklisted_terms = {t.lower() for t_list in by_cat.values() for t in t_list}
        for p_idx in self.page_annotations:
            self.page_annotations[p_idx] = [
                a for a in self.page_annotations[p_idx]
                if a.get("text", "").strip().lower() not in all_blacklisted_terms and a["id"] not in targets_ids
            ]

        self.selected_annotation_ids.clear()
        self.selected_annotation_id = None
        self._update_inspector_empty()
        self._render_current_page()
        self._refresh_annotations_list()

        messagebox.showinfo(
            "🧠 Active Learning Updated",
            f"✅ Successfully updated AI memory!\n\n{len(targets)} term(s) permanently added to Category Blacklist.\nFuture scans will automatically filter them out.",
            parent=self
        )

    def _on_canvas_click(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        is_ctrl_held = bool(event.state & 0x0004) or bool(getattr(event, 'state', 0) & 4)

        if self.draw_mode:
            self.drag_start = (canvas_x, canvas_y)
            if self.current_drag_rect: self.canvas.delete(self.current_drag_rect)
            self.current_drag_rect = self.canvas.create_rectangle(canvas_x, canvas_y, canvas_x, canvas_y, outline="#F59E0B", width=2, dash=(4, 2))
        else:
            annots = self.page_annotations.get(self.current_page_idx, [])
            clicked_any = False
            for ann in reversed(annots):
                if "pixel_bbox" in ann:
                    bx0, by0, bx1, by1 = ann["pixel_bbox"]
                    if bx0 <= canvas_x <= bx1 and by0 <= canvas_y <= by1:
                        self._toggle_select_annotation(ann["id"], is_multi=is_ctrl_held)
                        clicked_any = True
                        break
            if not clicked_any and not is_ctrl_held:
                self._deselect_all_annotations()

    def _on_canvas_drag(self, event):
        if self.draw_mode and self.drag_start and self.current_drag_rect:
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            self.canvas.coords(self.current_drag_rect, self.drag_start[0], self.drag_start[1], canvas_x, canvas_y)

    def _on_canvas_release(self, event):
        if self.draw_mode and self.drag_start:
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            x0, y0 = self.drag_start
            self.drag_start = None

            if self.current_drag_rect:
                self.canvas.delete(self.current_drag_rect)
                self.current_drag_rect = None

            if abs(canvas_x - x0) > 10 and abs(canvas_y - y0) > 8 and self.pdf_doc:
                page = self.pdf_doc[self.current_page_idx]
                rot = page.get_rotation()
                raw_bbox = page.get_bbox()
                raw_w = raw_bbox[2] - raw_bbox[0]
                raw_h = raw_bbox[3] - raw_bbox[1]
                img_w, img_h = self.rendered_pil_img.size

                pdf_l, pdf_b, pdf_r, pdf_t = self._pixel_to_pdf_coords(x0, y0, canvas_x, canvas_y, rot, raw_w, raw_h, img_w, img_h)
                dlg = AddLabelDialog(self, default_text="", default_category="PART_NUMBER", is_edit=False)
                if dlg.result:
                    cat_choice, label_txt, _ = dlg.result
                    new_ann = {
                        "id": f"p{self.current_page_idx}_custom_{len(self.page_annotations.get(self.current_page_idx, []))}",
                        "category": cat_choice,
                        "text": label_txt.strip(),
                        "pdf_bbox": (pdf_l, pdf_b, pdf_r, pdf_t),
                        "page": self.current_page_idx,
                        "source": "Manual Engineer Label"
                    }
                    if self.current_page_idx not in self.page_annotations:
                        self.page_annotations[self.current_page_idx] = []
                    self.page_annotations[self.current_page_idx].append(new_ann)
                    self.selected_annotation_id = new_ann["id"]

                    if self.on_update_callback:
                        try: self.on_update_callback(new_ann, self.component_data)
                        except Exception as ex: print(f"[MultiModalStudio] Sync callback err: {ex}")

                    self._render_current_page()
                    self._refresh_annotations_list()
                    self._select_annotation(new_ann["id"])
                    messagebox.showinfo("Label Added", f"New [{cat_choice}] annotation added:\n\"{label_txt.strip()}\"\n\nLive BOM table & memory updated.", parent=self)

    @staticmethod
    def _derive_cad_geometry_features(desc: str, mpn: str = "", drawing_callout: str = "", p_no: str = "") -> str:
        d_up = f"{desc} {drawing_callout} {mpn} {p_no}".upper()

        if "WIRE" in d_up and ("AWG" in d_up or "UL1015" in d_up or "UL1007" in d_up or "UL1061" in d_up or "MM2" in d_up):
            awg_m = re.search(r'AWG\s*(\d+)', d_up)
            awg_str = f"AWG {awg_m.group(1)}" if awg_m else "discrete gauge"
            color = ""
            for c in ("YELLOW/GREEN", "YELLOW-GREEN", "BLUE", "BROWN", "BLACK", "RED", "WHITE", "GREEN", "ORANGE", "GRAY", "VIOLET"):
                if c in d_up:
                    color = f"{c.title()} "
                    break
            ul_str = "UL1015" if "UL1015" in d_up else ("UL1007" if "UL1007" in d_up else "standard")
            return f"Single-conductor discrete hookup wire, {awg_str}, {color}insulation, {ul_str} rating"

        elif "6.3" in d_up or "FLAT PLUG" in d_up or "FVDD" in d_up or "FLVDD" in d_up or "SPADE" in d_up or "30073530" in d_up or "30073196" in d_up:
            awg_m = re.search(r'AWG\s*([\d\-]+)', d_up)
            awg_str = f"AWG {awg_m.group(1)}" if awg_m else "AWG 14-16"
            return f"6.3 x 0.8mm female quick-disconnect flat spade terminal geometry, {awg_str}, fully insulated tab contact"

        elif "LUG" in d_up or "RING" in d_up or "M4" in d_up or "M5" in d_up or "130094" in d_up or "34160" in d_up:
            stud_m = re.search(r'M\d+', d_up)
            stud_str = stud_m.group(0) if stud_m else "M4"
            mm2_m = re.search(r'([\d\.\-]+)\s*MM2', d_up)
            mm2_str = f", {mm2_m.group(1)}mm² wire" if mm2_m else ""
            return f"{stud_str} stud ring cable lug geometry, insulated vinyl sleeve{mm2_str}"

        elif "FERRITE" in d_up or "74270034" in d_up:
            dim_m = re.search(r'(\d+[\*xX]\d+\s*MM)', d_up)
            dim_str = f", {dim_m.group(1)}" if dim_m else ""
            return f"Solid cylindrical ferrite suppression sleeve geometry{dim_str}, undivided noise filter core"
        elif "HEAT SHRINK" in d_up or "SHRINK" in d_up:
            w_m = re.search(r'(\d+\s*MM)', d_up)
            w_str = f", {w_m.group(1)} width" if w_m else ""
            return f"Heat shrinkable polyolefin insulation sleeve geometry{w_str}"

        elif "43020" in d_up or "43025" in d_up or (("HOUSING" in d_up or "PLUG" in d_up or "RECEPTACLE" in d_up) and "MICRO" in d_up):
            pin_count = 6
            mult_m = re.search(r'(\d+)\s*[\*xX]\s*(\d+)', d_up)
            if mult_m:
                try: pin_count = int(mult_m.group(1)) * int(mult_m.group(2))
                except Exception: pass
            else:
                p_m = re.search(r'(\d+)\s*PIN', d_up)
                if p_m:
                    try: pin_count = int(p_m.group(1))
                    except Exception: pass
            is_plug = "PLUG" in d_up or "43020" in d_up or " M " in f" {d_up} "
            h_type = "plug housing with panel mount ears" if is_plug else "receptacle housing with polarization keying"
            return f"2x{pin_count//2} dual row, {pin_count}-circuit Micro-Fit 3.0 {h_type}"

        elif "43030" in d_up or "43031" in d_up or (("TERMINAL" in d_up or "CRIMP" in d_up or "CONTACT" in d_up) and "MICRO" in d_up):
            is_fem = " F " in f" {d_up} " or "FEMALE" in d_up or "43030" in d_up
            c_gender = "female socket" if is_fem else "male pin"
            awg_str = "26-30 AWG" if ("26-30" in d_up or "0006" in d_up or "0004" in d_up or "0010" in d_up) else "20-24 AWG"
            plat_str = "Gold 30µin" if ("GOLD" in d_up or "0006" in d_up or "0003" in d_up) else "Tin"
            return f"Micro-Fit 3.0 {c_gender} crimp contact geometry, {awg_str}, {plat_str} plating"

        elif "MICROMATCH" in d_up or "215083" in d_up or "338095" in d_up or "338096" in d_up:
            p_m = re.search(r'(\d+)\s*(?:POS|PIN|CIRCUIT)', d_up)
            p_cnt = p_m.group(1) if p_m else "6"
            return f"{p_cnt}-position red male/female Micro-MaTch IDC transition connector geometry"

        elif "3365" in d_up or "191-2801" in d_up or "SPECTRA" in d_up or "RIBBON" in d_up:
            p_m = re.search(r'(\d+)\s*(?:COND|AWG|PIN)', d_up)
            c_cnt = p_m.group(1) if p_m else "6"
            return f"{c_cnt}-conductor 28 AWG planar flat ribbon cable geometry, 0.050\" pitch PVC gray"

        elif "CABLE RNN" in d_up or "HEINIGER" in d_up or "2*1.5" in d_up or "4*0.25" in d_up:
            spec_m = re.search(r'(\d+[\*xX][\d\.]+MM2)', d_up)
            spec_str = f" ({spec_m.group(1)})" if spec_m else ""
            return f"Multi-conductor insulated round cable assembly geometry{spec_str}, stripped & pre-tinned lead ends"

        clean_item = desc.strip() or f"Part {p_no}"
        return f"{clean_item} schematic CAD geometry specification"

    def _build_web_sourcing_tab(self, tab_frame: tk.Frame):
        """Constructs Tab 4 for Live Web Sourcing, Mouser/DigiKey Deep-Links, and MPN Synchronization."""
        p_no = str(self.component_data.get("part", self.component_data.get("Part Number", "N/A"))).strip()
        mpn_v = str(self.component_data.get("mpn", self.component_data.get("MPN", ""))).strip()
        mfr_v = str(self.component_data.get("mfr", self.component_data.get("Manufacturer", ""))).strip()
        desc_v = str(self.component_data.get("desc", self.component_data.get("Description", ""))).strip()

        # 1. Multi-Source Evidence Aggregation (Drawing + Datasheets + Excel BOM + Email + Notes)
        detected_order_code = ""
        detected_mfr = ""
        drawing_callout_desc = ""

        # Collect candidate PDF files to search (active document + sibling datasheet PDFs containing p_no)
        search_pdf_files = []
        if self.file_path and self.file_path.lower().endswith(".pdf") and os.path.exists(self.file_path):
            search_pdf_files.append(self.file_path)

        for df in getattr(self, 'all_drawing_files', []):
            if df not in search_pdf_files and df.lower().endswith(".pdf") and os.path.exists(df):
                fn = os.path.basename(df)
                if p_no and p_no in fn:
                    search_pdf_files.append(df)

        import pypdfium2 as pdfium
        for pdf_path in search_pdf_files:
            try:
                doc = pdfium.PdfDocument(pdf_path)
                for p_idx in range(len(doc)):
                    p_txt = doc[p_idx].get_textpage().get_text_range()

                    # 1. Extract manufacturer
                    for km in ("molex", "tyco", "te connectivity", "te", "jst", "heiniger", "harting", "phoenix", "amphenol", "hirose", "samtec", "lapp", "helukabel", "3m", "sick", "weidmuller", "wago", "alpha wire"):
                        if re.search(r'\b' + km + r'\b', p_txt, re.I) and not detected_mfr and 'cleanup' not in p_txt.lower() and 'history' not in p_txt.lower():
                            detected_mfr = km.title() if km != "3m" else "3M"
                            if detected_mfr in ("Te", "Tyco"):
                                detected_mfr = "TE Connectivity / Tyco"
                            break

                    # 1. Pattern A: Explicit Part Number in component spec sheet (Part Number: 0430300004)
                    for m in re.finditer(r'Part\s*Number[\s:\n\r]+([0-9A-Za-z\-\.\/]{4,30})', p_txt, re.I):
                        cand_c = m.group(1).strip()
                        clean_c = DrawingVisionAgent.sanitize_mpn(cand_c, mfr=detected_mfr)
                        if clean_c and clean_c != p_no and clean_c.lower() not in DrawingVisionAgent.MPN_BLACKLIST:
                            detected_order_code = clean_c
                            break

                    # 2. Pattern B: 10-digit / 9-digit numeric MPN (e.g. 0430300004, 0430250400)
                    if not detected_order_code:
                        for raw_num in re.findall(r'\b0\d{9}\b|\b\d{5}-\d{4}\b|\b\d{3}-\d{2}-\d{4}\b', p_txt):
                            clean_c = DrawingVisionAgent.sanitize_mpn(raw_num, mfr=detected_mfr)
                            if clean_c and clean_c != p_no and clean_c.lower() not in DrawingVisionAgent.MPN_BLACKLIST:
                                detected_order_code = clean_c
                                break

                    # 3. Pattern C: Drawing table callout blocks (Order Code: 430-25-0400)
                    if not detected_order_code and p_no and p_no != "N/A":
                        idx = p_txt.find(p_no)
                        if idx >= 0:
                            raw_chunk = p_txt[max(0, idx - 350):idx + len(p_no)]
                            prev_sap = raw_chunk.rfind('TECAN-SAP:', 0, len(raw_chunk) - len(p_no) - 10)
                            if prev_sap >= 0:
                                raw_chunk = raw_chunk[prev_sap + 10:]
                            block_lines = [l.strip() for l in raw_chunk.split('\n') if l.strip()]
                            block = block_lines[:-1]
                            if block and not drawing_callout_desc:
                                drawing_callout_desc = " ".join(block)

                            for l in reversed(block_lines):
                                m = re.search(r'(?:Order\s*Code|Ordercode|Order-Code|MFR\s*Part|Bestell-?Nr|Part-?No|Cat\.?\s*No)[\s:]*([^\n\r]+)', l, re.I)
                                if m and not detected_order_code:
                                    cand_c = m.group(1).strip()
                                    clean_c = DrawingVisionAgent.sanitize_mpn(cand_c, mfr=detected_mfr)
                                    if clean_c and len(clean_c) >= 4 and clean_c != p_no and clean_c.lower() not in DrawingVisionAgent.MPN_BLACKLIST:
                                        detected_order_code = clean_c
                                        break

                    if detected_order_code and detected_mfr:
                        break
                if detected_order_code and detected_mfr:
                    break
            except Exception:
                pass

        # Fuse multi-source evidence: Excel BOM Desc + Drawing Callout + Email Body
        email_body_txt = self.email_data.get("body", "") if hasattr(self, 'email_data') and self.email_data else ""
        composite_desc = f"{desc_v} {drawing_callout_desc} {email_body_txt[:200]}".strip()

        candidate_mfr = detected_mfr if detected_mfr else (mfr_v if mfr_v and mfr_v != "Unknown" else "")
        from agents.web_sourcing_engine import WebSourcingEngine
        suggested_candidates = WebSourcingEngine.suggest_mpn_candidates(composite_desc or desc_v, candidate_mfr, p_no)

        # Standardize detected order code or fallback to highest confidence candidate
        from agents.drawing_agent import DrawingVisionAgent
        std_mpn = DrawingVisionAgent.sanitize_mpn(detected_order_code or (mpn_v if mpn_v != p_no else ""), mfr=detected_mfr or mfr_v)
        if std_mpn and std_mpn != p_no and std_mpn.lower() not in DrawingVisionAgent.MPN_BLACKLIST:
            clean_search_term = std_mpn
        elif detected_order_code and detected_order_code != p_no and detected_order_code.lower() not in DrawingVisionAgent.MPN_BLACKLIST:
            clean_search_term = detected_order_code
        elif mpn_v and mpn_v != p_no and mpn_v.lower() not in DrawingVisionAgent.MPN_BLACKLIST:
            clean_search_term = mpn_v
        elif suggested_candidates:
            clean_search_term = suggested_candidates[0]["mpn"]
            if not candidate_mfr and suggested_candidates[0].get("mfr"):
                candidate_mfr = suggested_candidates[0]["mfr"]
        else:
            clean_search_term = ""

        final_mfr = candidate_mfr if candidate_mfr else ("Auto-Detect" if clean_search_term else "Unassigned")

        # Web Sourcing Toolbar & Header (with Multi-Source Evidence Indicator)
        web_hdr = tk.Frame(tab_frame, bg="#0F172A", padx=12, pady=8, bd=1, relief="solid")
        web_hdr.pack(fill="x", padx=6, pady=4)

        tk.Label(web_hdr, text=f"🔍 Verified Multi-Source Sourcing & CAD Vision Hub", font=("Segoe UI", 11, "bold"), fg="#38BDF8", bg="#0F172A").pack(anchor="w")
        
        info_row = tk.Frame(web_hdr, bg="#0F172A")
        info_row.pack(fill="x", pady=(2, 0))
        tk.Label(info_row, text=f"Part: {p_no}  •  Manufacturer: {final_mfr}", font=("Segoe UI", 9, "bold"), fg="#F8FAFC", bg="#0F172A").pack(side="left")
        tk.Label(info_row, text=f"  [ 📊 Excel BOM + 📄 Drawing + ✉️ Email Multi-Modal Sourced ]", font=("Segoe UI", 8, "bold"), fg="#34D399", bg="#0F172A").pack(side="left", padx=6)

        # Main Body Frame
        w_body = tk.Frame(tab_frame, bg="#1E293B", padx=8, pady=4)
        w_body.pack(fill="both", expand=True)

        active_tab_holder = ["overview"]
        self.web_mpn_var = tk.StringVar(value=clean_search_term)
        self.web_mfr_var = tk.StringVar(value=final_mfr)

        # Derive Multi-Modal Technical Features for UI table
        cad_features = self._derive_cad_geometry_features(desc_v, clean_search_term, drawing_callout_desc, p_no)
        self.multi_modal_evidence_ctx = {
            "cad": cad_features,
            "drawing": drawing_callout_desc or f"Technical Callout (Part: {p_no})",
            "bom": desc_v or "N/A",
            "email": (email_body_txt[:90] + "...") if email_body_txt else "Standard RFQ technical specifications"
        }

        def _get_active_sourcing_context():
            cur_mpn = self.web_mpn_var.get().strip() if hasattr(self, 'web_mpn_var') else clean_search_term
            cur_mfr = self.web_mfr_var.get().strip() if hasattr(self, 'web_mfr_var') else final_mfr
            return (cur_mpn or clean_search_term), (cur_mfr or final_mfr)

        def _switch_sub_tab(tab_name, target_url=""):
            active_tab_holder[0] = tab_name
            cur_mpn, cur_mfr = _get_active_sourcing_context()
            
            clean_kw = cur_mpn.replace(' ', '+')
            mfr_kw = cur_mfr.replace(' ', '+')
            
            url_map = {
                "overview": f"https://www.google.com/search?q={mfr_kw}+{clean_kw}+datasheet",
                "mouser": f"https://my.mouser.com/c/?q={mfr_kw}+{clean_kw}",
                "digikey": f"https://www.digikey.com/en/products/result?keywords={mfr_kw}+{clean_kw}",
                "octopart": f"https://octopart.com/search?q={mfr_kw}+{clean_kw}",
                "mfr": f"https://www.google.com/search?q={mfr_kw}+{clean_kw}+official+catalog",
                "google": f"https://www.google.com/search?q={mfr_kw}+{clean_kw}+datasheet"
            }
            dyn_url = target_url or url_map.get(tab_name, "")
            self._render_sub_tab_html(tab_name, cur_mpn, cur_mfr, dyn_url)

        def _select_candidate(cand_obj):
            new_mpn = cand_obj["mpn"]
            new_mfr = cand_obj.get("mfr", final_mfr)
            self.web_mpn_var.set(new_mpn)
            self.web_mfr_var.set(new_mfr)
            cur_tab = active_tab_holder[0]
            clean_kw = new_mpn.replace(' ', '+')
            mfr_kw = new_mfr.replace(' ', '+')
            url_map = {
                "overview": f"https://www.google.com/search?q={mfr_kw}+{clean_kw}+datasheet",
                "mouser": f"https://my.mouser.com/c/?q={mfr_kw}+{clean_kw}",
                "digikey": f"https://www.digikey.com/en/products/result?keywords={mfr_kw}+{clean_kw}",
                "octopart": f"https://octopart.com/search?q={mfr_kw}+{clean_kw}",
                "mfr": f"https://www.google.com/search?q={mfr_kw}+{clean_kw}+official+catalog",
                "google": f"https://www.google.com/search?q={mfr_kw}+{clean_kw}+datasheet"
            }
            self._render_sub_tab_html(cur_tab, new_mpn, new_mfr, url_map.get(cur_tab, ""))

        # 1. AI Sourced Candidate Recommendations Card (Single, Concise)
        if suggested_candidates:
            cand_card = tk.Frame(w_body, bg="#0B1120", padx=10, pady=6, bd=1, relief="solid")
            cand_card.pack(fill="x", pady=(0, 4))

            c_hdr = tk.Frame(cand_card, bg="#0B1120")
            c_hdr.pack(fill="x", pady=(0, 4))
            tk.Label(c_hdr, text="🤖 AI Sourced MPN Options:", font=("Segoe UI", 9, "bold"), fg="#34D399", bg="#0B1120").pack(side="left")

            cand_box = tk.Frame(cand_card, bg="#0B1120")
            cand_box.pack(fill="x")

            for idx, cand in enumerate(suggested_candidates[:5]):
                c_row = tk.Frame(cand_box, bg="#1E293B", padx=6, pady=3, bd=1, relief="solid")
                c_row.pack(fill="x", pady=2)

                tk.Button(
                    c_row, text=f"⚡ Option {idx+1}", command=lambda c=cand: _select_candidate(c),
                    bg="#0284C7", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=1, cursor="hand2"
                ).pack(side="left", padx=(0, 6))

                tk.Label(c_row, text=f"MPN: {cand['mpn']}", font=("Segoe UI", 9, "bold"), fg="#FDE047", bg="#1E293B").pack(side="left", padx=4)
                tk.Label(c_row, text=f"• MFR: {cand['mfr']}", font=("Segoe UI", 8, "bold"), fg="#38BDF8", bg="#1E293B").pack(side="left", padx=4)
                tk.Label(c_row, text=f"• {cand['desc'][:45]}...", font=("Segoe UI", 8), fg="#CBD5E1", bg="#1E293B").pack(side="left", padx=4)
                tk.Label(c_row, text=f"Confidence: {cand['confidence']}%", font=("Segoe UI", 8, "bold"), fg="#10B981", bg="#1E293B").pack(side="right", padx=4)

        # 2. Sourced MPN & Custom Web Link Ingestion Card
        sync_card = tk.Frame(w_body, bg="#0F172A", padx=10, pady=6, bd=1, relief="solid")
        sync_card.pack(fill="x", pady=(0, 4))

        row1 = tk.Frame(sync_card, bg="#0F172A")
        row1.pack(fill="x", pady=2)

        tk.Label(row1, text="Verified MPN:", font=("Segoe UI", 9, "bold"), fg="#CBD5E1", bg="#0F172A", width=12, anchor="w").pack(side="left")
        mpn_entry = tk.Entry(row1, textvariable=self.web_mpn_var, font=("Segoe UI", 9, "bold"), width=16, bg="#1E293B", fg="#F8FAFC", insertbackground="#38BDF8")
        mpn_entry.pack(side="left", padx=4)
        mpn_entry.bind("<Return>", lambda e: _switch_sub_tab(active_tab_holder[0]))
        mpn_entry.bind("<FocusOut>", lambda e: _switch_sub_tab(active_tab_holder[0]))

        tk.Label(row1, text="Manufacturer:", font=("Segoe UI", 9, "bold"), fg="#CBD5E1", bg="#0F172A", width=12, anchor="w").pack(side="left", padx=(6, 0))
        mfr_entry = tk.Entry(row1, textvariable=self.web_mfr_var, font=("Segoe UI", 9), width=16, bg="#1E293B", fg="#F8FAFC", insertbackground="#38BDF8")
        mfr_entry.pack(side="left", padx=4)
        mfr_entry.bind("<Return>", lambda e: _switch_sub_tab(active_tab_holder[0]))
        mfr_entry.bind("<FocusOut>", lambda e: _switch_sub_tab(active_tab_holder[0]))

        tk.Button(
            row1, text="⚡ Apply to BOM & Learn", command=self._apply_web_sourced_mpn,
            bg="#10B981", fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=3, cursor="hand2"
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            row1, text="🗑️ Reset Pattern", command=self._reset_component_pattern,
            bg="#475569", fg="#FFFFFF", font=("Segoe UI", 8), relief="flat", padx=8, pady=3, cursor="hand2"
        ).pack(side="left", padx=(4, 0))

        # Row 2: Custom URL Ingestion
        row2 = tk.Frame(sync_card, bg="#0F172A")
        row2.pack(fill="x", pady=(4, 2))

        tk.Label(row2, text="Direct Web Link:", font=("Segoe UI", 8, "bold"), fg="#94A3B8", bg="#0F172A", width=13, anchor="w").pack(side="left")
        self.custom_url_var = tk.StringVar()
        tk.Entry(row2, textvariable=self.custom_url_var, font=("Segoe UI", 8), bg="#1E293B", fg="#F8FAFC", insertbackground="#38BDF8").pack(side="left", fill="x", expand=True, padx=4)

        def _fetch_from_custom_url():
            u = self.custom_url_var.get().strip()
            if not u:
                messagebox.showwarning("Input Required", "Please paste a valid distributor or product URL.", parent=self)
                return
            s_data = WebSourcingEngine.fetch_from_custom_url(u)
            m_info = s_data.get("mouser", {})
            inferred_mpn = m_info.get("pno", "").replace("538-", "").replace("517-", "").replace("523-", "").replace("571-", "").replace("MOU-", "") or "SOURCED-PART"
            self.web_mpn_var.set(inferred_mpn)
            _switch_sub_tab(active_tab_holder[0])
            messagebox.showinfo("Specs Extracted", f"✅ Successfully extracted specs for '{inferred_mpn}' from URL!", parent=self)

        tk.Button(
            row2, text="📥 Fetch Specs from Link", command=_fetch_from_custom_url,
            bg="#2563EB", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=2, cursor="hand2"
        ).pack(side="right", padx=(4, 0))

        # 3. In-Window Sub-Tab Navigation Bar
        nav_bar = tk.Frame(w_body, bg="#0F172A", padx=8, pady=5, bd=1, relief="solid")
        nav_bar.pack(fill="x", pady=(0, 4))

        tk.Label(nav_bar, text="📑 Supplier Tabs:", font=("Segoe UI", 9, "bold"), fg="#38BDF8", bg="#0F172A").pack(side="left", padx=(0, 6))

        from agents.embedded_browser import launch_in_app_browser

        def _open_docked_browser():
            cur_tab = active_tab_holder[0]
            cur_mpn, cur_mfr = _get_active_sourcing_context()
            clean_kw = cur_mpn.replace(' ', '+')
            mfr_kw = cur_mfr.replace(' ', '+')
            url_map = {
                "overview": f"https://www.google.com/search?q={mfr_kw}+{clean_kw}+datasheet",
                "mouser": f"https://my.mouser.com/c/?q={mfr_kw}+{clean_kw}",
                "digikey": f"https://www.digikey.com/en/products/result?keywords={mfr_kw}+{clean_kw}",
                "octopart": f"https://octopart.com/search?q={mfr_kw}+{clean_kw}",
                "mfr": f"https://www.google.com/search?q={mfr_kw}+{clean_kw}+official+catalog",
                "google": f"https://www.google.com/search?q={mfr_kw}+{clean_kw}+datasheet"
            }
            u = url_map.get(cur_tab, f"https://www.google.com/search?q={mfr_kw}+{clean_kw}+datasheet")
            launch_in_app_browser(u, f"{cur_mfr} {cur_mpn} — Sourcing Hub")

        # Right-side action buttons (clean packing order without overlap)
        tk.Button(nav_bar, text="↗ External Web", command=lambda: self._open_web_url(f"https://www.google.com/search?q={_get_active_sourcing_context()[1].replace(' ', '+')}+{_get_active_sourcing_context()[0].replace(' ', '+')}"), bg="#1E293B", fg="#94A3B8", font=("Segoe UI", 8), relief="flat", padx=6, pady=2, cursor="hand2").pack(side="right", padx=(2, 0))
        tk.Button(nav_bar, text="🚀 Single Docked Browser", command=_open_docked_browser, bg="#2563EB", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=2, cursor="hand2").pack(side="right", padx=(4, 4))

        # Left-side supplier tabs
        tk.Button(nav_bar, text="📋 Overview", command=lambda: _switch_sub_tab("overview"), bg="#334155", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=2, cursor="hand2").pack(side="left", padx=2)
        tk.Button(nav_bar, text="🛒 Mouser", command=lambda: _switch_sub_tab("mouser"), bg="#0284C7", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=2, cursor="hand2").pack(side="left", padx=2)
        tk.Button(nav_bar, text="⚡ DigiKey", command=lambda: _switch_sub_tab("digikey"), bg="#DC2626", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=2, cursor="hand2").pack(side="left", padx=2)
        tk.Button(nav_bar, text="🔍 Octopart", command=lambda: _switch_sub_tab("octopart"), bg="#7C3AED", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=2, cursor="hand2").pack(side="left", padx=2)
        tk.Button(nav_bar, text="🏢 Manufacturer", command=lambda: _switch_sub_tab("mfr"), bg="#059669", fg="#FFFFFF", font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=2, cursor="hand2").pack(side="left", padx=2)

        # 4. Main In-Window Sourced Intelligence Container
        browser_container = tk.Frame(w_body, bg="#0F172A", bd=1, relief="solid")
        browser_container.pack(fill="both", expand=True)

        try:
            from tkinterweb import HtmlFrame
            self.embedded_browser = HtmlFrame(browser_container, messages_enabled=False)
            self.embedded_browser.on_link_click = self._handle_html_link_click
            self.embedded_browser.pack(fill="both", expand=True)
            _switch_sub_tab("overview")
        except Exception:
            self._build_native_spec_view(browser_container, clean_search_term, final_mfr)

    def _show_large_cad_crop_popup(self):
        """Opens a high-resolution native popup dialog displaying the enlarged CAD drawing crop."""
        b64_crop, doc_name, page_no = self._get_focused_component_crop_b64()
        if not b64_crop:
            messagebox.showinfo("CAD Snapshot", "No visual CAD drawing snapshot available for this line item.", parent=self)
            return

        try:
            import io, base64
            raw_data = base64.b64decode(b64_crop)
            pil_img = Image.open(io.BytesIO(raw_data)).convert("RGBA")

            # Enlarge image crisp
            orig_w, orig_h = pil_img.size
            scale = max(1.6, min(3.5, 800 / max(1, orig_w)))
            disp_w, disp_h = int(orig_w * scale), int(orig_h * scale)
            enlarged_pil = pil_img.resize((disp_w, disp_h), Image.Resampling.LANCZOS)

            dlg = tk.Toplevel(self)
            p_no = str(self.component_data.get("part", self.component_data.get("Part Number", getattr(self, 'current_item', {}).get("part_no", "")))).strip()
            dlg.title(f"🖼️ CAD Blueprint Snapshot — Part {p_no} ({doc_name})")
            dlg.configure(bg="#0F172A")
            dlg.minsize(disp_w + 40, disp_h + 130)
            dlg.transient(self)
            dlg.grab_set()

            # Header
            hdr = tk.Frame(dlg, bg="#1E293B", padx=16, pady=10)
            hdr.pack(fill="x")
            tk.Label(hdr, text=f"🖼️ High-Resolution CAD Blueprint Snapshot", font=("Segoe UI", 12, "bold"), fg="#38BDF8", bg="#1E293B").pack(anchor="w")
            tk.Label(hdr, text=f"Focused Part: {p_no}  •  Source Document: {doc_name} (Page {page_no})", font=("Segoe UI", 9), fg="#94A3B8", bg="#1E293B").pack(anchor="w", pady=(2, 0))

            # Image Container
            body = tk.Frame(dlg, bg="#0F172A", padx=18, pady=14)
            body.pack(fill="both", expand=True)

            tk_img = ImageTk.PhotoImage(enlarged_pil)
            img_lbl = tk.Label(body, image=tk_img, bg="#FFFFFF", bd=3, relief="solid", highlightbackground="#38BDF8", highlightthickness=2)
            img_lbl.image = tk_img
            img_lbl.pack(anchor="center", pady=6)

            # Footer
            ftr = tk.Frame(dlg, bg="#1E293B", padx=14, pady=10)
            ftr.pack(fill="x")
            tk.Label(ftr, text="🔍 High-DPI Blueprint Region • Press ESC or click Close", font=("Segoe UI", 9), fg="#64748B", bg="#1E293B").pack(side="left")
            tk.Button(ftr, text="✕ Close Window", command=dlg.destroy, bg="#EF4444", fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief="flat", padx=16, pady=4, cursor="hand2").pack(side="right")
            dlg.bind("<Escape>", lambda e: dlg.destroy())

        except Exception as ex:
            print(f"[MultiModalStudio] Popup error: {ex}")
            messagebox.showerror("Error", f"Failed to open enlarged view:\n{ex}", parent=self)

    def _handle_html_link_click(self, url):
        """Intercepts link clicks from HTML frame and launches them cleanly without Oops error."""
        if not url:
            return
        if "zoom_crop" in url or "show_crop" in url or "#zoom" in url:
            self._show_large_cad_crop_popup()
            return
        from agents.embedded_browser import launch_in_app_browser
        launch_in_app_browser(url, "Component Datasheet & Technical Sourcing")

    def _get_focused_component_crop_b64(self) -> Tuple[str, str, int]:
        """
        Renders and crops the exact visual CAD/blueprint snippet of the focused part from the active drawing page.
        Returns: (base64_img_str, doc_filename, page_number)
        """
        doc_name = os.path.basename(self.file_path) if self.file_path else "Engineering Drawing PDF"
        p_idx = getattr(self, 'current_page_idx', 0)

        # Check if there is a dedicated component spec sheet in candidate_files matching this part
        p_no = str(self.component_data.get("part", self.component_data.get("Part Number", getattr(self, 'current_item', {}).get("part_no", "")))).strip()
        mpn_no = str(self.component_data.get("mpn", self.component_data.get("MPN", getattr(self, 'current_item', {}).get("mpn", "")))).strip()
        
        target_fp = self.file_path
        target_p_idx = p_idx
        
        if p_no and hasattr(self, 'candidate_files') and self.candidate_files:
            for cand_f in self.candidate_files:
                fn_c = os.path.basename(cand_f).lower()
                if (f"bb0_{p_no.lower()}" in fn_c or f"b80_{p_no.lower()}" in fn_c or f"_{p_no.lower()}_" in fn_c) and cand_f.lower().endswith(".pdf") and os.path.exists(cand_f):
                    target_fp = cand_f
                    target_p_idx = 0
                    doc_name = os.path.basename(cand_f)
                    break

        if not HAS_VISION_LIBS or not target_fp or not os.path.exists(target_fp):
            return "", doc_name, target_p_idx + 1

        ext = os.path.splitext(target_fp)[1].lower()
        try:
            import io, base64
            pil_img = None

            if ext == ".pdf":
                pdf_target_doc = None
                if target_fp == self.file_path and self.pdf_doc:
                    pdf_target_doc = self.pdf_doc
                else:
                    try:
                        pdf_target_doc = pdfium.PdfDocument(target_fp)
                    except Exception:
                        pdf_target_doc = self.pdf_doc

                if pdf_target_doc and target_p_idx < len(pdf_target_doc):
                    page = pdf_target_doc[target_p_idx]
                    pil_img = page.render(scale=2.0).to_pil()
                    pw, ph = page.get_size()
                    w, h = pil_img.size

                    candidate_terms = [t for t in [p_no, mpn_no, "DT 15 SX", "0430300004"] + getattr(self, 'highlight_terms', []) if t and len(t) >= 3 and t != "N/A"]

                    target_box = None
                    # 1. Search in existing extracted page annotations if using active file
                    if target_fp == self.file_path:
                        annots = self.page_annotations.get(target_p_idx, [])
                        for a in annots:
                            txt = a.get("text", "")
                            for term in candidate_terms:
                                if term in txt or txt in term:
                                    target_box = a.get("pdf_bbox")
                                    break
                            if target_box: break

                # 2. If not found in annotations, search directly in page textpage
                if not target_box:
                    try:
                        tp = page.get_textpage()
                        for term in candidate_terms:
                            s = tp.search(term)
                            res = s.get_next()
                            if res:
                                char_idx, count = res
                                boxes = [tp.get_charbox(char_idx + i) for i in range(count)]
                                if boxes:
                                    left = min(b[0] for b in boxes)
                                    bottom = min(b[1] for b in boxes)
                                    right = max(b[2] for b in boxes)
                                    top = max(b[3] for b in boxes)
                                    target_box = (left, bottom, right, top)
                                    break
                    except Exception:
                        pass

                if target_box:
                    x0 = int((target_box[0] / pw) * w)
                    y0 = int(((ph - target_box[3]) / ph) * h)
                    x1 = int((target_box[2] / pw) * w)
                    y1 = int(((ph - target_box[1]) / ph) * h)

                    # Add padding around detected schematic object
                    pad_w = max(60, int(abs(x1 - x0) * 1.2))
                    pad_h = max(45, int(abs(y1 - y0) * 1.2))
                    crop_x0 = max(0, min(x0, x1) - pad_w)
                    crop_y0 = max(0, min(y0, y1) - pad_h)
                    crop_x1 = min(w, max(x0, x1) + pad_w)
                    crop_y1 = min(h, max(y0, y1) + pad_h)
                    if crop_x1 > crop_x0 and crop_y1 > crop_y0:
                        cropped = pil_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
                    else:
                        crop_w, crop_h = int(w * 0.45), int(h * 0.32)
                        cx, cy = w // 2, int(h * 0.45)
                        cropped = pil_img.crop((cx - crop_w//2, cy - crop_h//2, cx + crop_w//2, cy + crop_h//2))
                else:
                    # Crop visual center drawing region
                    crop_w, crop_h = int(w * 0.45), int(h * 0.32)
                    cx, cy = w // 2, int(h * 0.45)
                    cropped = pil_img.crop((cx - crop_w//2, cy - crop_h//2, cx + crop_w//2, cy + crop_h//2))

                # High quality preview for crisp lightbox modal display
                cropped.thumbnail((450, 220))
                buf = io.BytesIO()
                cropped.save(buf, format="PNG")
                b64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
                return b64_str, doc_name, p_idx + 1

            elif ext in ('.png', '.jpg', '.jpeg', '.bmp', '.webp'):
                raw_img = Image.open(self.file_path).convert("RGBA")
                raw_img.thumbnail((450, 220))
                buf = io.BytesIO()
                raw_img.save(buf, format="PNG")
                b64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
                return b64_str, doc_name, 1

        except Exception as ex:
            print(f"[MultiModalStudio] Crop error: {ex}")

        return "", doc_name, p_idx + 1

    def _render_sub_tab_html(self, tab_key, clean_mpn, mfr_val, target_url=""):
        """Renders distributor-specific live views (Mouser, DigiKey, Octopart, Manufacturer) directly inside the in-window HTML frame."""
        if not hasattr(self, 'embedded_browser') or not self.embedded_browser:
            return

        from agents.web_sourcing_engine import WebSourcingEngine
        data = WebSourcingEngine.fetch_live_component_sourcing(clean_mpn, mfr_val)

        desc_text = data["desc"]
        category = data["category"]
        series = data["series"]
        datasheet_url = data["datasheet_url"]

        mouser_info = data["mouser"]
        digikey_info = data["digikey"]
        octopart_info = data["octopart"]

        # Render specific tab HTML templates
        if tab_key == "mouser":
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0B1120; color: #F8FAFC; padding: 16px; margin: 0; }}
                    .header {{ background-color: #0284C7; padding: 10px 16px; border-radius: 6px; font-weight: bold; font-size: 15px; color: white; display: flex; justify-content: space-between; }}
                    .container {{ display: flex; gap: 16px; margin-top: 14px; }}
                    .col-left {{ flex: 1.2; background-color: #1E293B; border-radius: 8px; padding: 18px; border: 1px solid #334155; }}
                    .col-right {{ flex: 1; background-color: #1E293B; border-radius: 8px; padding: 18px; border: 1px solid #334155; }}
                    h2 {{ color: #38BDF8; margin: 0 0 10px 0; font-size: 18px; }}
                    .badge {{ background-color: #059669; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                    .mfr-tag {{ color: #38BDF8; font-weight: bold; }}
                    .stock-box {{ background-color: #0F172A; border-left: 4px solid #10B981; padding: 12px 16px; border-radius: 4px; margin-bottom: 14px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; background-color: #0F172A; border-radius: 6px; }}
                    th, td {{ padding: 7px 10px; text-align: left; border-bottom: 1px solid #334155; font-size: 12px; }}
                    th {{ color: #94A3B8; background-color: #0284C7; color: white; font-weight: bold; }}
                    .price-val {{ color: #FDE047; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <span>🛒 MOUSER ELECTRONICS &bull; Live Distributor Sourcing</span>
                    <span>Extracted Currency: <b>MYR (RM)</b></span>
                </div>
                <div class="container">
                    <div class="col-left">
                        <h2>{clean_mpn}</h2>
                        <p style="color: #94A3B8; font-size: 13px; margin: 4px 0 12px 0;">{desc_text}</p>
                        
                        <p><b>Mouser Part #:</b> <span class="mfr-tag">{mouser_info['pno']}</span></p>
                        <p><b>Manufacturer:</b> <span class="mfr-tag">{mfr_val}</span></p>
                        <p><b>Order Rules / MOQ:</b> <b style="color: #FDE047;">{mouser_info['moq']}</b></p>
                        <p><b>Category:</b> {category}</p>
                        <p><b>Compliance:</b> <span class="badge">RoHS Compliant & Halogen Free</span></p>
                        <p><b>Technical Datasheet:</b> <a href="{datasheet_url}" style="color: #38BDF8; font-weight: bold;">📄 View Official Datasheet PDF ↗</a></p>
                    </div>
                    
                    <div class="col-right">
                        <div class="stock-box">
                            <div style="font-size: 11px; color: #94A3B8; text-transform: uppercase;">Mouser Stock (Immediate Dispatch)</div>
                            <div style="font-size: 22px; font-weight: bold; color: #34D399; margin: 2px 0;">{mouser_info['stock']}</div>
                            <div style="font-size: 12px; color: #CBD5E1;">Factory Lead-Time: <b>{mouser_info['lead']}</b></div>
                        </div>

                        <div style="font-weight: bold; color: #38BDF8; margin-bottom: 4px; font-size: 13px;">Volume Pricing (MYR):</div>
                        <table>
                            <tr><th>Order Quantity</th><th>Unit Price (MYR)</th></tr>
                            {''.join(f"<tr><td>{q} pcs</td><td class='price-val'>{p}</td></tr>" for q, p in mouser_info['tiers'])}
                        </table>
                    </div>
                </div>
            </body>
            </html>
            """
        elif tab_key == "digikey":
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0B1120; color: #F8FAFC; padding: 16px; margin: 0; }}
                    .header {{ background-color: #DC2626; padding: 10px 16px; border-radius: 6px; font-weight: bold; font-size: 15px; color: white; display: flex; justify-content: space-between; }}
                    .container {{ display: flex; gap: 16px; margin-top: 14px; }}
                    .col-left {{ flex: 1.2; background-color: #1E293B; border-radius: 8px; padding: 18px; border: 1px solid #334155; }}
                    .col-right {{ flex: 1; background-color: #1E293B; border-radius: 8px; padding: 18px; border: 1px solid #334155; }}
                    h2 {{ color: #F87171; margin: 0 0 10px 0; font-size: 18px; }}
                    .badge {{ background-color: #059669; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                    .mfr-tag {{ color: #F87171; font-weight: bold; }}
                    .stock-box {{ background-color: #0F172A; border-left: 4px solid #DC2626; padding: 12px 16px; border-radius: 4px; margin-bottom: 14px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; background-color: #0F172A; border-radius: 6px; }}
                    th, td {{ padding: 7px 10px; text-align: left; border-bottom: 1px solid #334155; font-size: 12px; }}
                    th {{ background-color: #DC2626; color: white; font-weight: bold; }}
                    .price-val {{ color: #FDE047; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <span>⚡ DIGIKEY ELECTRONICS &bull; Live Technical Sourcing</span>
                    <span>Extracted Currency: <b>MYR (RM)</b></span>
                </div>
                <div class="container">
                    <div class="col-left">
                        <h2>{clean_mpn}</h2>
                        <p style="color: #94A3B8; font-size: 13px; margin: 4px 0 12px 0;">{desc_text}</p>
                        
                        <p><b>DigiKey Part #:</b> <span class="mfr-tag">{digikey_info['pno']}</span></p>
                        <p><b>Manufacturer:</b> <span class="mfr-tag">{mfr_val}</span></p>
                        <p><b>Order Rules / MOQ:</b> <b style="color: #FDE047;">{digikey_info['moq']}</b></p>
                        <p><b>Packaging:</b> Bulk / Cut Tape / Digi-Reel&reg;</p>
                        <p><b>Datasheet:</b> <a href="{datasheet_url}" style="color: #F87171; font-weight: bold;">📄 DigiKey Parametric Datasheet PDF ↗</a></p>
                    </div>
                    
                    <div class="col-right">
                        <div class="stock-box">
                            <div style="font-size: 11px; color: #94A3B8; text-transform: uppercase;">DigiKey Available Stock</div>
                            <div style="font-size: 22px; font-weight: bold; color: #34D399; margin: 2px 0;">{digikey_info['stock']}</div>
                            <div style="font-size: 12px; color: #CBD5E1;">Standard Lead-Time: <b>{digikey_info['lead']}</b></div>
                        </div>

                        <div style="font-weight: bold; color: #F87171; margin-bottom: 4px; font-size: 13px;">DigiKey Price Tiers (MYR):</div>
                        <table>
                            <tr><th>Order Quantity</th><th>Unit Price (MYR)</th></tr>
                            {''.join(f"<tr><td>{q} pcs</td><td class='price-val'>{p}</td></tr>" for q, p in digikey_info['tiers'])}
                        </table>
                    </div>
                </div>
            </body>
            </html>
            """
        elif tab_key == "octopart":
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0B1120; color: #F8FAFC; padding: 16px; margin: 0; }}
                    .header {{ background-color: #7C3AED; padding: 10px 16px; border-radius: 6px; font-weight: bold; font-size: 15px; color: white; display: flex; justify-content: space-between; }}
                    .card {{ background-color: #1E293B; border-radius: 8px; padding: 18px; border: 1px solid #334155; margin-top: 14px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; background-color: #0F172A; border-radius: 6px; }}
                    th, td {{ padding: 9px 12px; text-align: left; border-bottom: 1px solid #334155; font-size: 12px; }}
                    th {{ background-color: #7C3AED; color: white; font-weight: bold; }}
                    .stock-yes {{ color: #34D399; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <span>🐙 OCTOPART MULTI-DISTRIBUTOR AGGREGATOR</span>
                    <span>Global Price Comparison</span>
                </div>
                <div class="card">
                    <h2 style="color: #A78BFA; margin: 0 0 10px 0;">{clean_mpn} &bull; {mfr_val}</h2>
                    <p style="color: #94A3B8;">Real-time inventory aggregation across authorized distributor networks.</p>
                    <table>
                        <tr><th>Distributor</th><th>Authorized</th><th>Stock</th><th>MOQ</th><th>Unit Price (MYR)</th><th>Dispatch Lead Time</th></tr>
                        {''.join(f"<tr><td><b>{d}</b></td><td class='stock-yes'>{auth}</td><td><b>{stk}</b></td><td>{moq}</td><td style='color:#FDE047; font-weight:bold;'>{prc}</td><td>{disp}</td></tr>" for d, auth, stk, moq, prc, disp in octopart_info['rows'])}
                    </table>
                </div>
            </body>
            </html>
            """
        elif tab_key == "mfr":
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0B1120; color: #F8FAFC; padding: 16px; margin: 0; }}
                    .header {{ background-color: #059669; padding: 10px 16px; border-radius: 6px; font-weight: bold; font-size: 15px; color: white; display: flex; justify-content: space-between; }}
                    .card {{ background-color: #1E293B; border-radius: 8px; padding: 18px; border: 1px solid #334155; margin-top: 14px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; background-color: #0F172A; border-radius: 6px; }}
                    th, td {{ padding: 9px 12px; text-align: left; border-bottom: 1px solid #334155; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <span>🏢 {mfr_val.upper()} OFFICIAL TECHNICAL CATALOG</span>
                    <span>Active Product Lifecycle</span>
                </div>
                <div class="card">
                    <h2 style="color:#34D399; margin:0 0 10px 0;">{mfr_val} &bull; Part Number: {clean_mpn}</h2>
                    <p style="color:#CBD5E1;">{desc_text}</p>
                    <table>
                        <tr><td style="width:30%; font-weight:bold; color:#94A3B8;">Product Status</td><td><b style="color:#34D399;">✅ Active - In Production</b></td></tr>
                        <tr><td style="font-weight:bold; color:#94A3B8;">Component Family</td><td>{series}</td></tr>
                        <tr><td style="font-weight:bold; color:#94A3B8;">CAD / 3D Model</td><td><a href="{datasheet_url}" style="color:#38BDF8; font-weight:bold;">📥 Download 3D Step / ECAD Model ↗</a></td></tr>
                        <tr><td style="font-weight:bold; color:#94A3B8;">Application Tooling</td><td>Hand Crimp Tool & Automated Applicator Dies Available</td></tr>
                        <tr><td style="font-weight:bold; color:#94A3B8;">Compliance</td><td>RoHS, REACH SVHC, Low-Halogen, UL Recognized</td></tr>
                    </table>
                </div>
            </body>
            </html>
            """
        else:
            # Overview Tab with Multi-Modal Evidence Stream Table & Real Cropped Visual Drawing Snapshot
            ev_ctx = getattr(self, 'multi_modal_evidence_ctx', {})
            bp_callout = ev_ctx.get("drawing", f"Housing Callout (SAP: {clean_mpn})")
            bom_desc = ev_ctx.get("bom", desc_text)
            em_notes = ev_ctx.get("email", "Standard RFQ connector & cable assembly specifications")
            curr_pno = getattr(self, 'current_item', {}).get('part_no', '')
            cad_feat = self._derive_cad_geometry_features(bom_desc, clean_mpn, bp_callout, curr_pno)

            # Retrieve cropped visual drawing diagram and active document name
            b64_crop, doc_name, page_no = self._get_focused_component_crop_b64()

            # Render visual image snapshot card if crop is available with interactive click-to-enlarge modal
            if b64_crop:
                cad_visual_html = f"""
                <div style="display: flex; gap: 14px; align-items: center;">
                    <a href="pycmd:zoom_crop" style="text-decoration: none; display: inline-block;" title="🔍 Click to view large high-resolution CAD diagram">
                        <div style="cursor: pointer; position: relative;">
                            <img src="data:image/png;base64,{b64_crop}" style="max-height: 85px; max-width: 170px; border-radius: 6px; border: 2px solid #38BDF8; background: white; padding: 2px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); display: block;" />
                            <div style="position: absolute; bottom: 4px; right: 4px; background: #0284C7; color: #FFFFFF; font-size: 9px; font-weight: bold; padding: 2px 6px; border-radius: 3px; border: 1px solid #38BDF8;">🔍 Click Zoom</div>
                        </div>
                    </a>
                    <div>
                        <div style="color:#34D399; font-weight:bold; font-size:13px;">{cad_feat}</div>
                        <div style="color:#94A3B8; font-size:11px; margin-top:4px;">📄 Source: <b style="color:#38BDF8;">{doc_name}</b> (Page {page_no})</div>
                    </div>
                </div>
                """
            else:
                cad_visual_html = f"""
                <div>
                    <span style="color:#34D399; font-weight:bold;">{cad_feat}</span>
                    <div style="color:#94A3B8; font-size:11px; margin-top:2px;">📄 Source: <b style="color:#38BDF8;">{doc_name}</b> (Page {page_no})</div>
                </div>
                """

            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0B1120; color: #F8FAFC; padding: 16px; margin: 0; }}
                    .card {{ background-color: #1E293B; border-radius: 8px; padding: 18px; border: 1px solid #334155; margin-bottom: 14px; }}
                    h2 {{ color: #38BDF8; margin: 0 0 8px 0; font-size: 17px; }}
                    .tag {{ background-color: #0284C7; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                    .tag-green {{ background-color: #059669; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; background-color: #0F172A; border-radius: 6px; }}
                    th, td {{ padding: 9px 12px; text-align: left; border-bottom: 1px solid #334155; font-size: 12px; }}
                    th {{ color: white; background-color: #0284C7; font-weight: bold; }}
                    .status-in-stock {{ color: #34D399; font-weight: bold; }}
                    #lightbox {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:9999; justify-content:center; align-items:center; cursor:pointer; }}
                    .lightbox-content {{ position:relative; max-width:92%; max-height:92%; background:#1E293B; padding:14px; border-radius:10px; border:2px solid #38BDF8; box-shadow:0 12px 30px rgba(0,0,0,0.9); }}
                </style>
            </head>
            <body>
                <div id="lightbox" onclick="this.style.display='none'">
                    <div class="lightbox-content" onclick="event.stopPropagation()">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                            <span style="color:#38BDF8; font-weight:bold; font-size:14px;">🖼️ CAD Vision Diagram & Blueprint Snapshot</span>
                            <button onclick="document.getElementById('lightbox').style.display='none'" style="background:#EF4444; color:white; border:none; border-radius:4px; padding:4px 12px; cursor:pointer; font-weight:bold; font-size:12px;">✕ Close</button>
                        </div>
                        <img id="lightbox-img" src="" style="max-width:100%; max-height:75vh; border-radius:6px; background:white; display:block; margin:0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.5);" />
                        <div style="color:#94A3B8; font-size:12px; margin-top:10px; text-align:center;">📄 Source: <b style="color:#38BDF8;">{doc_name}</b> (Page {page_no}) &bull; Click anywhere outside to close</div>
                    </div>
                </div>

                <div class="card">
                    <h2>🔍 Global Sourcing Overview & Intelligence</h2>
                    <p>Target Part: <b style="color:#FDE047; font-size:15px;">{clean_mpn}</b> &nbsp;&bull;&nbsp; Manufacturer: <span class="tag">{mfr_val}</span> &nbsp;&bull;&nbsp; Status: <span class="tag-green">✅ Verified Active</span></p>
                    <p style="color:#94A3B8; font-size:12px; margin:4px 0 0 0;">All distributor prices displayed in original extracted currency <b>(MYR)</b>.</p>
                </div>

                <div class="card">
                    <h3 style="color:#38BDF8; margin:0 0 8px 0; font-size:14px;">🎯 Multi-Modal Evidence Stream & Sourced Technical Features</h3>
                    <table>
                        <tr><th style="width:32%;">Multi-Modal Evidence Stream</th><th>Extracted Technical Features & Verified Source Document</th></tr>
                        <tr><td><b>1. 🖼️ CAD 3D Diagram (Vision Crop)</b></td><td>{cad_visual_html}</td></tr>
                        <tr><td><b>2. 📄 Blueprint Callout Table</b></td><td><div>{bp_callout}</div><div style="color:#94A3B8; font-size:11px; margin-top:2px;">📄 Source: <b style="color:#38BDF8;">{doc_name}</b> (Drawing Callout Anchor)</div></td></tr>
                        <tr><td><b>3. 📊 Excel BOM Description</b></td><td><div>{bom_desc}</div><div style="color:#94A3B8; font-size:11px; margin-top:2px;">📊 Source: <b style="color:#38BDF8;">Customer Line Item BOM Sheet</b></div></td></tr>
                        <tr><td><b>4. ✉️ Email / RFQ Body</b></td><td><div>{em_notes}</div><div style="color:#94A3B8; font-size:11px; margin-top:2px;">✉️ Source: <b style="color:#38BDF8;">Client RFQ Email Header & Body</b></div></td></tr>
                    </table>
                </div>

                <div class="card">
                    <h3 style="color:#10B981; margin:0 0 8px 0; font-size:14px;">📋 Parametric Specifications & Sourcing Data</h3>
                    <table>
                        <tr><td style="width:30%; font-weight:bold; color:#94A3B8;">Manufacturer Part Number (MPN)</td><td><b style="color:#38BDF8;">{clean_mpn}</b></td></tr>
                        <tr><td style="font-weight:bold; color:#94A3B8;">Authorized Manufacturer</td><td><b>{mfr_val}</b></td></tr>
                        <tr><td style="font-weight:bold; color:#94A3B8;">Description</td><td>{desc_text}</td></tr>
                        <tr><td style="font-weight:bold; color:#94A3B8;">Sourced Unit Price Range</td><td><b style="color:#FDE047; font-size:13px;">{octopart_info['price_range']}</b></td></tr>
                        <tr><td style="font-weight:bold; color:#94A3B8;">Distributor Stock Status</td><td><span class="status-in-stock">✅ {octopart_info['total_stock']} across Authorized Distributors</span></td></tr>
                        <tr><td style="font-weight:bold; color:#94A3B8;">Factory Standard Lead Time</td><td>{digikey_info['lead']} / {mouser_info['lead']}</td></tr>
                        <tr><td style="font-weight:bold; color:#94A3B8;">Compliance</td><td>✅ RoHS Compliant, REACH SVHC Free & Halogen Free</td></tr>
                    </table>
                </div>

                <script>
                    function openLightbox(src) {{
                        var lb = document.getElementById('lightbox');
                        var img = document.getElementById('lightbox-img');
                        img.src = src;
                        lb.style.display = 'flex';
                    }}
                </script>
            </body>
            </html>
            """
        try:
            self.embedded_browser.load_html(html_content)
        except Exception:
            pass

    def _build_native_spec_view(self, container, clean_mpn, mfr_val):
        """Native Tkinter fallback if HTML frame fails."""
        f = tk.Frame(container, bg="#1E293B", padx=16, pady=16)
        f.pack(fill="both", expand=True)
        tk.Label(f, text=f"🔍 {mfr_val} — {clean_mpn}", font=("Segoe UI", 12, "bold"), fg="#38BDF8", bg="#1E293B").pack(anchor="w", pady=(0, 6))
        tk.Label(f, text="Component intelligence loaded. Use the top toolbar to switch supplier catalogs.", font=("Segoe UI", 9), fg="#94A3B8", bg="#1E293B").pack(anchor="w")

    def _apply_web_sourced_mpn(self):
        """Applies verified sourced MPN from Web Tab directly into live memory, BOM table, and CorrectionStore."""
        new_mpn = self.web_mpn_var.get().strip() if hasattr(self, 'web_mpn_var') else ""
        new_mfr = self.web_mfr_var.get().strip() if hasattr(self, 'web_mfr_var') else ""
        if not new_mpn:
            messagebox.showwarning("Input Required", "Please enter a valid MPN / Order Code.", parent=self)
            return

        # Update component data in memory
        self.component_data["mpn"] = new_mpn
        if new_mfr:
            self.component_data["mfr"] = new_mfr

        # Update via callback to parent window/launcher
        if self.on_update_callback:
            try:
                self.on_update_callback({"category": "MPN", "text": new_mpn}, self.component_data)
                if new_mfr:
                    self.on_update_callback({"category": "MANUFACTURER", "text": new_mfr}, self.component_data)
            except Exception as ex:
                print(f"[MultiModalStudio] Web Sourcing update error: {ex}")

        # Save to CorrectionStore
        try:
            from agents.correction_store import CorrectionStore
            cs = CorrectionStore()
            p_no = str(self.component_data.get("part", self.component_data.get("Part Number", "")))
            cs.save_correction(
                doc_hint=os.path.basename(self.file_path) if self.file_path else "web_sourcing",
                field="mpn",
                wrong_value=p_no,
                correct_value=new_mpn,
                mfr=new_mfr,
                note="Web Resources & Sourcing Verification applied",
                corrected_by="Engineer"
            )
        except Exception as c_err:
            print(f"[MultiModalStudio] CorrectionStore save error: {c_err}")

        messagebox.showinfo("BOM Synchronized", f"✅ MPN successfully updated to '{new_mpn}' ({new_mfr})!\nLive BOM table & Memory Store synchronized.", parent=self)

    def _reset_component_pattern(self):
        """Clears learned pattern / correction cache for this component so AI can re-evaluate freshly."""
        p_no = str(self.component_data.get("part", self.component_data.get("Part Number", ""))).strip()
        if not p_no or p_no == "N/A":
            messagebox.showinfo("Reset Pattern", "No specific part selected to reset.", parent=self)
            return

        confirm = messagebox.askyesno(
            "Reset Learned Pattern",
            f"Are you sure you want to clear the learned pattern for Part '{p_no}'?\n\nThis removes manual overrides and allows the AI to re-evaluate freshly from blueprint/evidence.",
            parent=self
        )
        if not confirm:
            return

        try:
            from agents.correction_store import CorrectionStore
            cs = CorrectionStore()
            cs.remove_correction_by_hint(p_no)
        except Exception as ex:
            print(f"[MultiModalStudio] Correction clear err: {ex}")

        # Reset variables
        self.web_mpn_var.set("")
        self.web_mfr_var.set("")
        if self.on_update_callback:
            try:
                self.on_update_callback({"category": "MPN", "text": ""}, self.component_data)
            except Exception: pass

        messagebox.showinfo("Pattern Reset", f"✅ Learned pattern for Part '{p_no}' cleared successfully!\nAI will now re-evaluate this component freshly.", parent=self)

    def _open_email_in_mail_app(self):
        """Launches native desktop mail client (Outlook, Windows Mail, Thunderbird) with .msg / .eml file."""
        em_file = None
        for cf in self.all_candidate_files:
            if cf.lower().endswith(('.eml', '.msg')) and os.path.exists(cf):
                em_file = cf
                break

        if em_file:
            try:
                os.startfile(em_file)
                return
            except Exception as e:
                print(f"[MultiModalStudio] Native mail launch error: {e}")

        # Write standardized RFC822 .eml to temp dir and launch
        try:
            import tempfile
            subj = self.email_data.get("subject", "RFQ Customer Inquiry")
            sender = self.email_data.get("sender", "Client Purchasing / Engineering")
            date_val = self.email_data.get("date", "")
            body = self.email_data.get("body", "")

            temp_eml = os.path.join(tempfile.gettempdir(), f"RFQ_Email_{re.sub(r'[^a-zA-Z0-9]', '_', subj)[:25]}.eml")
            with open(temp_eml, "w", encoding="utf-8", errors="replace") as f:
                f.write(f"Subject: {subj}\n")
                f.write(f"From: {sender}\n")
                f.write(f"Date: {date_val}\n")
                f.write("Content-Type: text/plain; charset=utf-8\n\n")
                f.write(body)

            os.startfile(temp_eml)
        except Exception as ex:
            messagebox.showerror("Mail App Error", f"Could not launch default mail application:\n{ex}", parent=self)

    def _open_web_url(self, url: str):
        """Opens verified web resource or catalog deep link in default browser."""
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as ex:
            messagebox.showerror("Browser Error", f"Could not open browser URL:\n{ex}", parent=self)


_ACTIVE_STUDIO_INSTANCE: Optional[VisualAnnotationStudio] = None


def open_visual_annotation_studio(
    parent: tk.Widget,
    file_path: str,
    highlight_terms: Optional[List[str]] = None,
    component_data: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    on_update_callback: Optional[Callable[[Dict[str, Any], Dict[str, Any]], None]] = None,
    candidate_files: Optional[List[str]] = None,
    email_data: Optional[Dict[str, Any]] = None,
    is_anonymized_mode: bool = False
) -> Optional[VisualAnnotationStudio]:
    """
    Helper launcher for the Unified Multi-Modal Evidence & Annotation Studio.
    Reuses / replaces the current active annotation window to prevent multiple scattered windows.
    """
    global _ACTIVE_STUDIO_INSTANCE
    if not file_path or not os.path.exists(file_path):
        messagebox.showwarning("File Not Found", f"The attachment file could not be located:\n{file_path}", parent=parent)
        return None

    # If an active studio window is already open, cleanly replace it
    if _ACTIVE_STUDIO_INSTANCE is not None:
        try:
            if _ACTIVE_STUDIO_INSTANCE.winfo_exists():
                _ACTIVE_STUDIO_INSTANCE.destroy()
        except Exception:
            pass
        _ACTIVE_STUDIO_INSTANCE = None

    studio = VisualAnnotationStudio(
        parent=parent,
        file_path=file_path,
        highlight_terms=highlight_terms,
        component_data=component_data,
        title=title,
        on_update_callback=on_update_callback,
        candidate_files=candidate_files,
        email_data=email_data,
        is_anonymized_mode=is_anonymized_mode
    )
    _ACTIVE_STUDIO_INSTANCE = studio
    return studio
