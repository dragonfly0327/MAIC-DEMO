# ==============================================================================
# --- ContinuumX Verified BOM & Assembly Ground Truth Store ---
# Stores and manages verified component lists for assembly part numbers & drawings.
# When a user edits and verifies a BOM in Review Studio / Excel, future extractions
# for that assembly number or drawing will automatically use the verified ground truth.
# ==============================================================================

import os
import sys
import json
import re
import copy
from typing import Dict, Any, Optional, List

# Standardized Base Directory Resolution Pattern
if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS') or "__compiled__" in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif '__file__' in globals():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
elif len(sys.argv) > 0 and sys.argv[0] and sys.argv[0] != '-c':
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
else:
    BASE_DIR = os.getcwd()

DATA_DIR = os.path.join(BASE_DIR, "data", "verified_boms")
VERIFIED_FILE = os.path.join(DATA_DIR, "verified_assemblies.json")


class VerifiedBOMStore:
    """
    Central repository for human-verified assembly BOMs.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(VerifiedBOMStore, cls).__new__(cls)
            cls._instance._init_store()
        return cls._instance

    def _init_store(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(VERIFIED_FILE):
            try:
                with open(VERIFIED_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(VERIFIED_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[VerifiedBOMStore] Error saving verified BOMs: {e}")

    @staticmethod
    def _normalize_key(assy_no: str) -> str:
        if not assy_no:
            return ""
        # Remove whitespace and uppercase
        return str(assy_no).strip().upper()

    def save_verified_assembly(self, assy_no: str, assy_data: Dict[str, Any], customer: str = "", rfq_no: str = ""):
        """
        Saves a verified assembly structure with all its component rows.
        """
        k = self._normalize_key(assy_no)
        if not k:
            return

        items = copy.deepcopy(assy_data.get("items", []))
        if not items:
            return

        record = {
            "assy_no": assy_data.get("assy_no", assy_no),
            "assy_model": assy_data.get("assy_model", ""),
            "assy_rev": assy_data.get("assy_rev", ""),
            "target_price": assy_data.get("target_price", ""),
            "eau": assy_data.get("eau", ""),
            "customer": customer,
            "rfq_no": rfq_no,
            "items_count": len(items),
            "items": items
        }

        self.data[k] = record

        # Also register prefix key if it contains sub-suffix (e.g. 155-892105-010-00R -> 155-892105)
        m = re.match(r'^([A-Za-z0-9]+-[A-Za-z0-9]+)', k)
        if m:
            prefix_k = m.group(1)
            if prefix_k != k:
                self.data[prefix_k] = record

        self._save()
        print(f"[VerifiedBOMStore] [Learned Pattern] Saved Verified BOM for Assembly '{assy_no}' ({len(items)} components)")

    def get_verified_assembly(self, assy_no: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves verified assembly data by exact or normalized assembly number.
        """
        if not assy_no:
            return None
        k = self._normalize_key(assy_no)

        # 1. Exact match
        if k in self.data:
            return copy.deepcopy(self.data[k])

        # 2. Match with dashes / suffixes removed
        for stored_k, rec in self.data.items():
            if stored_k == k:
                return copy.deepcopy(rec)
            if stored_k.replace("-", "").replace("_", "") == k.replace("-", "").replace("_", ""):
                return copy.deepcopy(rec)
            # If stored key starts with k or vice versa
            if (stored_k.startswith(k) or k.startswith(stored_k)) and len(stored_k) >= 8 and len(k) >= 8:
                return copy.deepcopy(rec)

        return None

    def get_all(self) -> Dict[str, Any]:
        return copy.deepcopy(self.data)
