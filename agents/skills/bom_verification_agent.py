# ==============================================================================
# --- ContinuumX BOM Verification AI Agent ---
# Handles intelligent header mapping, customer BOM parsing, and continuous
# learning from user-confirmed mapping adjustments.
# ==============================================================================

import os
import json
import re
import openpyxl
import sys
from datetime import datetime

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
bom_dir = os.path.join(base_dir, "ref", "BOM")
if bom_dir not in sys.path:
    sys.path.append(bom_dir)


class BOMVerificationAgent:
    def __init__(self, server_path=None):
        if not server_path:
            try:
                from utils import load_server_path
                server_path = load_server_path()
            except Exception:
                server_path = None

        self.server_path = server_path
        self.auto_dispatch_setting = self._load_auto_dispatch_setting()
        self.knowledge_path = self._get_learned_mappings_path()
        
        try:
            from agents.brain_router import BrainRouter
            self.router = BrainRouter()
        except Exception as e:
            self.router = None
            print(f"[BOMVerificationAgent] BrainRouter notice: {e}")

    def _get_learned_mappings_path(self):
        kb_dir = os.path.join(base_dir, "knowledge_base")
        os.makedirs(kb_dir, exist_ok=True)
        return os.path.join(kb_dir, "learned_column_mappings.json")

    def _load_learned_mappings(self):
        if os.path.exists(self.knowledge_path):
            try:
                with open(self.knowledge_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "customer_mappings": {},
            "global_header_aliases": {
                "PART NO": "Part",
                "PART NO.": "Part",
                "PART NUMBER": "Part",
                "ITEM NO": "Part",
                "ITEM NO.": "Part",
                "ITEM CODE": "Part",
                "BOM DESCRIPTION": "Description",
                "ITEM DESCRIPTION": "Description",
                "PART DESCRIPTION": "Description",
                "QTY": "Qty",
                "QUANTITY": "Qty",
                "QTY/ASSY": "Qty",
                "UOM": "UOM",
                "UM": "UOM",
                "UNIT OF MEASURE": "UOM",
                "LINE ITEM": "Line Item",
                "LINE": "Line Item",
                "ITEM #": "Line Item",
                "BOM LEVEL": "Line Item"
            }
        }

    def _save_learned_mappings(self, data):
        try:
            with open(self.knowledge_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[BOMVerificationAgent] Error saving learned mappings: {e}")

    def learn_mapping(self, customer_name, headers, dynamic_mapping, special_results=None, commodity=None):
        """
        Learns and persists confirmed column mappings from user verification.
        Saves both customer-specific profile and global header alias dictionaries.
        """
        if not customer_name:
            return

        kb = self._load_learned_mappings()
        cust_key = str(customer_name).strip()

        # Update customer profile
        kb["customer_mappings"][cust_key] = {
            "headers_mapping": dynamic_mapping,
            "special_columns": special_results or {},
            "commodity": commodity or "Wire Harness",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Update global header aliases for unmapped headers
        for src_col, target_col in dynamic_mapping.items():
            if isinstance(target_col, str) and target_col and src_col:
                kb["global_header_aliases"][src_col.strip().upper()] = target_col.strip()

        self._save_learned_mappings(kb)
        print(f"[BOMVerificationAgent] Successfully learned column mappings for customer '{cust_key}'!")

    def parse_customer_bom(self, excel_path, customer_hint=None):
        """
        Parses customer Excel BOM sheet and performs intelligent column header mapping
        utilizing learned customer profiles, global aliases, and regex heuristics.
        """
        if not os.path.exists(excel_path):
            return {"success": False, "error": f"File not found: {excel_path}"}

        try:
            wb = openpyxl.load_workbook(excel_path, data_only=True)
            sheet = wb.active
            rows_data = list(sheet.iter_rows(values_only=True))

            if not rows_data:
                return {"success": False, "error": "Excel sheet is empty"}

            header_row_idx = 0
            headers = []

            # Find header row
            for idx, r in enumerate(rows_data[:10]):
                str_row = [str(cell).upper() if cell is not None else "" for cell in r]
                if any(k in str_row for k in ["PART", "PART NUMBER", "PART NO.", "DESCRIPTION", "ITEM DESCRIPTION", "QTY", "MPN"]):
                    header_row_idx = idx
                    headers = [str(cell).strip() if cell is not None else "" for cell in r]
                    break

            if not headers:
                headers = [str(cell).strip() if cell is not None else "" for cell in rows_data[0]]

            # Extract Customer Metadata candidate
            filename = os.path.basename(excel_path)
            cust_name_match = filename.replace("synthetic_", "").replace(".xlsx", "").replace(".xls", "").split("_")[0]
            customer_name = customer_hint or (cust_name_match if cust_name_match else "Customer")

            kb = self._load_learned_mappings()
            cust_profile = kb["customer_mappings"].get(customer_name, {})
            learned_cust_mapping = cust_profile.get("headers_mapping", {})
            learned_special = cust_profile.get("special_columns", {})
            global_aliases = kb.get("global_header_aliases", {})

            # Column Mapping Intelligence Dictionary
            mapping = {
                "Assy #": "", "Assy Model": "", "Assy Rev": "",
                "Part": "", "Description": "", "MFR": "", "MPN": "",
                "Qty": "", "UOM": "", "Line Item": ""
            }

            # 1. First Pass: Apply Customer Learned Memory if available
            for h in headers:
                if h in learned_cust_mapping:
                    std = learned_cust_mapping[h]
                    if isinstance(std, str) and std in mapping and not mapping[std]:
                        mapping[std] = h

            # 2. Second Pass: Apply Global Learned Aliases
            for h in headers:
                h_up = h.strip().upper()
                if h_up in global_aliases:
                    std = global_aliases[h_up]
                    if std in mapping and not mapping[std]:
                        mapping[std] = h

            # 3. Third Pass: Standard Heuristic Detection
            for col_name in headers:
                col_upper = col_name.upper()
                if not col_upper:
                    continue

                if not mapping["Part"] and any(k in col_upper for k in ["PART NUMBER", "PART NO", "PART NO.", "PART", "ITEM NO"]):
                    mapping["Part"] = col_name
                elif not mapping["Description"] and any(k in col_upper for k in ["DESCRIPTION", "PART NAME", "ITEM DESCRIPTION"]):
                    mapping["Description"] = col_name
                elif not mapping["Qty"] and col_upper in ["QTY", "QUANTITY", "QTY/ASSY"]:
                    mapping["Qty"] = col_name
                elif not mapping["UOM"] and col_upper in ["UOM", "UM", "UNIT OF MEASURE"]:
                    mapping["UOM"] = col_name
                elif not mapping["Line Item"] and any(k in col_upper for k in ["LINE ITEM", "LINE", "ITEM #", "BOM LEVEL"]):
                    mapping["Line Item"] = col_name
                elif not mapping["Assy #"] and "ASSY #" in col_upper:
                    mapping["Assy #"] = col_name
                elif not mapping["Assy Model"] and ("ASSY MODEL" in col_upper or col_upper == "MODEL"):
                    mapping["Assy Model"] = col_name
                elif not mapping["Assy Rev"] and ("ASSY REV" in col_upper or col_upper == "RV"):
                    mapping["Assy Rev"] = col_name

            # Convert mapping to {excel_header: standard_col} format for CombinedMappingPanel
            panel_mapping = {excel_col: std_col for std_col, excel_col in mapping.items() if excel_col}

            # Multi-source column detection for MFR and MPN
            multi_mfr = []
            multi_mpn = []
            if "MFR" in learned_cust_mapping and isinstance(learned_cust_mapping["MFR"], list):
                multi_mfr = [c for c in learned_cust_mapping["MFR"] if c in headers]
            if "MPN" in learned_cust_mapping and isinstance(learned_cust_mapping["MPN"], list):
                multi_mpn = [c for c in learned_cust_mapping["MPN"] if c in headers]

            for col_name in headers:
                col_upper = col_name.upper()
                if not col_upper:
                    continue
                if not multi_mfr and any(k in col_upper for k in ["MFG NAME", "MANUFACTURER", "MFR", "VENDOR NAME"]):
                    multi_mfr.append(col_name)
                elif not multi_mpn and any(k in col_upper for k in ["MFG PART", "MPN", "MANUFACTURER PART", "VENDOR PART", "VENDOR PN"]):
                    multi_mpn.append(col_name)

            if multi_mfr:
                panel_mapping["MFR"] = multi_mfr
            if multi_mpn:
                panel_mapping["MPN"] = multi_mpn

            initial_special = dict(learned_special) if learned_special else {}
            if not initial_special:
                if mapping.get("Assy #"):
                    initial_special["Assy #"] = {"method": "map", "source_column": mapping["Assy #"]}
                if mapping.get("Assy Model"):
                    initial_special["Assy Model"] = {"method": "map", "source_column": mapping["Assy Model"]}
                if mapping.get("Assy Rev"):
                    initial_special["Assy Rev"] = {"method": "map", "source_column": mapping["Assy Rev"]}

            # Parse Rows into structured list
            parsed_items = []
            for r_idx, r_values in enumerate(rows_data[header_row_idx + 1:], start=header_row_idx + 2):
                if not any(r_values):
                    continue

                row_dict = {}
                for h_idx, h_name in enumerate(headers):
                    if h_idx < len(r_values):
                        row_dict[h_name] = r_values[h_idx]

                part_val = row_dict.get(mapping.get("Part", ""), "")
                if part_val or any(r_values):
                    parsed_items.append({
                        "line_no": r_idx,
                        "raw_data": row_dict
                    })

            suggested_commodity = cust_profile.get("commodity") or ("PCBA" if "PCBA" in filename.upper() else "Wire Harness")

            return {
                "success": True,
                "file_path": excel_path,
                "headers": headers,
                "suggested_mapping": panel_mapping,
                "suggested_mapping_raw": mapping,
                "suggested_special": initial_special,
                "suggested_customer_name": customer_name,
                "suggested_commodity": suggested_commodity,
                "suggested_project_title": filename.replace(".xlsx", "").replace(".xls", ""),
                "item_count": len(parsed_items),
                "items": parsed_items
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _load_auto_dispatch_setting(self):
        b_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate_cfgs = [
            os.path.join(b_dir, "config.ini"),
            os.path.join(self.server_path or "", "config.ini"),
            r"C:\ProgramData\ContinuumX\config.ini"
        ]
        for cfg_path in candidate_cfgs:
            if os.path.exists(cfg_path):
                try:
                    import configparser
                    cfg = configparser.ConfigParser()
                    cfg.read(cfg_path, encoding='utf-8')
                    if 'WORKFLOW' in cfg and 'auto_dispatch_bom' in cfg['WORKFLOW']:
                        val = cfg['WORKFLOW']['auto_dispatch_bom'].strip().lower()
                        return val in ("true", "1", "yes")
                except Exception:
                    pass
        return False
