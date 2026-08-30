import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd

# Add Project Management path to sys path to import base_panel
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "Project Management")))
from base_panel import BaseProjectManagementPanel

from sourcing_wizard import BOMVerificationPanel, AssemblyMOQPanel
from target_price_wizard import BOMTargetPriceWizardDialog

class BOMProjectManagementPanel(BaseProjectManagementPanel):
    def __init__(self, parent, bom_data_dir, **kwargs):
        super().__init__(parent, bom_data_dir, **kwargs)
        self.allowed_stages = ["pending_bom"]

    def view_workflow(self, rfq_id, customer):
        cust_folder = customer.replace(" ", "_")
        filepath = os.path.normpath(os.path.join(self.bom_data_dir, cust_folder, f"{rfq_id.replace(' ', '_')}.json"))
        
        if not os.path.exists(filepath):
            messagebox.showerror("Error", f"BOM data file not found:\n{filepath}", parent=self)
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load BOM data:\n{e}", parent=self)
            return

        # 1. Verification view
        # Reconstruct DataFrame
        records = []
        for assy in data.get("Assemblies", []):
            assy_num = assy.get("Assy #")
            model = assy.get("Assy Model", "")
            rev = assy.get("Assy Rev", "")
            for comp in assy.get("Components", []):
                records.append({
                    "Assy #": assy_num,
                    "Assy Model": model,
                    "Assy Rev": rev,
                    "Line Item": comp.get("Line Item", ""),
                    "Part": comp.get("Part", ""),
                    "Description": comp.get("Description", ""),
                    "MFR": comp.get("MFR", ""),
                    "MPN": comp.get("MPN", ""),
                    "Qty": comp.get("Qty", 0.0),
                    "UOM": comp.get("UOM", "")
                })
        
        if not records:
            messagebox.showinfo("No Components", "This RFQ has no components to view.", parent=self)
            return

        df = pd.DataFrame(records)
        cust_info = ({}, customer, rfq_id, "")
        mapping = {c: c for c in df.columns}
        assembly_status = {str(a.get("Assy #")): "Verified" for a in data.get("Assemblies", [])}

        step = 1
        win = None
        while step > 0:
            if step == 1:
                if win is None or not win.winfo_exists():
                    win = tk.Toplevel(self)
                    win.geometry("1200x700")
                    win.configure(bg="#EBF8FF")
                    win.grab_set()

                win.title(f"View BOM Verification â€” RFQ {rfq_id} ({customer})")
                panel1 = BOMVerificationPanel(win, df, cust_info, mapping, assembly_status=assembly_status, read_only=True)
                panel1.pack(fill="both", expand=True)

                res1 = panel1.wait_for_close()
                panel1.destroy()

                if res1 is None or (isinstance(res1, str) and res1 == "CANCEL"):
                    step = 0
                else:
                    step = 2

            elif step == 2:
                if win is None or not win.winfo_exists():
                    win = tk.Toplevel(self)
                    win.geometry("1200x700")
                    win.configure(bg="#EBF8FF")
                    win.grab_set()

                win.title(f"View MOQ Assignation â€” RFQ {rfq_id} ({customer})")
                unique_assemblies = [str(a.get("Assy #")) for a in data.get("Assemblies", [])]
                global_moqs = [int(x) for x in data.get("Global MOQs", [])]
                assembly_moqs = {}
                for assy in data.get("Assemblies", []):
                    a_num = str(assy.get("Assy #"))
                    assembly_moqs[a_num] = [int(x) for x in assy.get("Assigned MOQs", [])]

                panel2 = AssemblyMOQPanel(win, unique_assemblies, initial_global_moqs=global_moqs, initial_assembly_moqs=assembly_moqs, title="View Assembly MOQ Assignments", raw_data=data, current_user="Admin", read_only=True)
                panel2.pack(fill="both", expand=True)

                res2 = panel2.wait_for_close()
                panel2.destroy()

                if isinstance(res2, str) and res2 in ("BACK", "PREVIOUS"):
                    step = 1
                elif res2 is not None and not (isinstance(res2, str) and res2 == "CANCEL"):
                    step = 3
                else:
                    step = 0

            elif step == 3:
                if win and win.winfo_exists():
                    win.destroy()
                    win = None

                tp_dialog = BOMTargetPriceWizardDialog(self.winfo_toplevel(), customer, rfq_id, filepath, data, read_only=True, show_previous=True)
                self.winfo_toplevel().wait_window(tp_dialog)
                res3 = getattr(tp_dialog, 'result', None)

                if res3 == "PREVIOUS":
                    step = 2
                else:
                    step = 0

        if win and win.winfo_exists():
            win.destroy()


def open_project_management_panel(parent_window, bom_data_dir, module_name=''):
    attr_name = '_pm_panel_window'
    existing = getattr(parent_window, attr_name, None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                for child in existing.winfo_children():
                    if isinstance(child, BOMProjectManagementPanel):
                        child.load_data()
                return
        except Exception:
            pass
    win = tk.Toplevel(parent_window)
    win.title('Project Management - RFQ Status Tracker')
    win.geometry('1200x720')
    win.configure(bg='#EBF8FF')
    prefix = f'{module_name} | ' if module_name else ''
    panel = BOMProjectManagementPanel(win, bom_data_dir, title_prefix=prefix, user_name=getattr(parent_window, 'user_name', None), user_role=getattr(parent_window, 'user_role', None))
    panel.pack(fill='both', expand=True)
    setattr(parent_window, attr_name, win)
    def _on_close():
        setattr(parent_window, attr_name, None)
        win.destroy()
    win.protocol('WM_DELETE_WINDOW', _on_close)
    panel.load_data()
