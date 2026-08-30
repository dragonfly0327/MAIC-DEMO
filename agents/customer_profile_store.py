# ==============================================================================
# --- ContinuumX Customer Profile & Archetype Memory Store ---
# Learns and remembers document archetypes, spreadsheet structures, drawing conventions,
# and extraction patterns per customer. Adapts to new formats through Human Review.
# ==============================================================================

import os
import sys
import json
import re
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

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


class CustomerProfileStore:
    """
    Manages customer-specific extraction profiles, document archetypes,
    and adaptive learning patterns.
    """
    def __init__(self, storage_dir: Optional[str] = None):
        if not storage_dir:
            storage_dir = os.path.join(BASE_DIR, "data", "customer_profiles")
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self._ensure_built_in_profiles()

    def _get_profile_path(self, customer_name: str) -> str:
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', customer_name.strip().lower())
        return os.path.join(self.storage_dir, f"{safe_name}.json")

    def _ensure_built_in_profiles(self):
        """Initializes baseline profiles for standard known customers."""
        cust_456_path = self._get_profile_path("CUST-456")
        if not os.path.exists(cust_456_path):
            cust_456_profile = {
                "customer_name": "CUST-456",
                "aliases": ["cust-456", "cust_456", "client-456"],
                "default_commodity": "Wire Harness",
                "archetypes": {
                    "master_excel_package": {
                        "description": "Master Excel RFQ with unzipped SAP BOMs and PDF drawings",
                        "indicators": {
                            "has_excel": True,
                            "filename_patterns": ["cable_rfq", "rfq_cable", "cust_rfq", "relocation"],
                            "header_keywords": ["article no", "rev.level", "mat status", "description", "volume", "eau", "drawing", "bom"]
                        },
                        "excel_mapping": {
                            "header_search_rows": [1, 10],
                            "assy_no_aliases": ["article no", "part no", "item no"],
                            "assy_rev_aliases": ["rev.level", "rev", "revision", "level"],
                            "assy_model_aliases": ["description", "desc", "model", "item description"],
                            "eau_aliases": ["estimated annual volume", "annual volume", "volume quantity", "volume", "eau", "annual consumption"],
                            "drawing_aliases": ["drawing", "drawing name", "blueprint", "drawing no"],
                            "bom_flag_aliases": ["bom", "bom attached", "sap bom"]
                        },
                        "child_boms": {
                            "pattern": "BOM_{assy_no}.xls",
                            "sap_export_format": True
                        },
                        "drawings": {
                            "filename_patterns": ["AJ0_{assy_no}_EN_{rev}.pdf", "{assy_no}.{rev}*.pdf"],
                            "sap_callout_keyword": "SAP-DRAWING"
                        }
                    },
                    "drawing_only_package": {
                        "description": "Drawings only attached without master Excel",
                        "indicators": {
                            "has_excel": False,
                            "has_pdf_drawings": True
                        },
                        "title_block_pattern": r'([0-9]{8})\.([0-9]{2})',
                        "callout_sap_pattern": r'SAP[:\s]+([0-9]{7,10})'
                    }
                },
                "mpn_blacklist": [
                    "number and name", "number and nam", "part number and name",
                    "component", "description", "order code",
                    "item", "sap", "rev", "qty", "uom"
                ],
                "verified_by_human": True,
                "version": 1
            }
            self.save_profile(cust_456_profile)

        cust_123_path = self._get_profile_path("CUST-123")
        if not os.path.exists(cust_123_path):
            cust_123_profile = {
                "customer_name": "CUST-123",
                "aliases": ["cust-123", "cust_123", "client-123"],
                "default_commodity": "Wire Harness",
                "archetypes": {
                    "email_body_embedded_table": {
                        "description": "Multi-assembly specification with multiline MPN blocks embedded in email body",
                        "indicators": {
                            "has_excel": False,
                            "body_pattern": r'\b\d{3}-\d{6}-\d{3}-\d{2}[A-Za-z0-9]?'
                        },
                        "assy_no_regex": r'(\b\d{3}-\d{6}-\d{3}-\d{2}[A-Za-z0-9]?)',
                        "drawing_filename_pattern": r'(\d{3}-\d{6}-\d{3}-\d{2}[A-Za-z0-9]?)\.pdf'
                    }
                },
                "mpn_blacklist": ["number and name", "component", "description", "item"],
                "verified_by_human": True,
                "version": 1
            }
            self.save_profile(cust_123_profile)

    def get_profile(self, customer_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves customer profile by name or alias."""
        if not customer_name:
            return None
        cust_clean = customer_name.strip().lower()

        # Direct file check
        p_path = self._get_profile_path(customer_name)
        if os.path.exists(p_path):
            try:
                with open(p_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass

        # Alias scan across all profiles
        if os.path.exists(self.storage_dir):
            for fname in os.listdir(self.storage_dir):
                if fname.endswith(".json"):
                    fp = os.path.join(self.storage_dir, fname)
                    try:
                        with open(fp, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            aliases = [a.lower() for a in data.get("aliases", [])]
                            if cust_clean in aliases or data.get("customer_name", "").lower() == cust_clean:
                                return data
                    except Exception:
                        pass
        return None

    def save_profile(self, profile_data: Dict[str, Any]) -> bool:
        """Saves or updates a customer profile."""
        cust_name = profile_data.get("customer_name")
        if not cust_name:
            return False
        p_path = self._get_profile_path(cust_name)
        try:
            with open(p_path, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=2)
            return True
        except Exception as e:
            print(f"[CustomerProfileStore] Error saving profile for {cust_name}: {e}")
            return False

    def identify_customer(self, subject: str = "", body: str = "", sender: str = "", filenames: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Identifies customer name, profile, and active archetype from email signals.
        """
        if filenames is None:
            filenames = []

        full_text = f"{subject} {body} {sender} {' '.join(filenames)}".lower()

        # Search existing profiles
        if os.path.exists(self.storage_dir):
            for fname in os.listdir(self.storage_dir):
                if fname.endswith(".json"):
                    fp = os.path.join(self.storage_dir, fname)
                    try:
                        with open(fp, 'r', encoding='utf-8') as f:
                            prof = json.load(f)
                            c_name = prof.get("customer_name", "")
                            aliases = [a.lower() for a in prof.get("aliases", [])] + [c_name.lower()]
                            for alias in aliases:
                                if alias and re.search(r'\b' + re.escape(alias) + r'\b', full_text):
                                    return {
                                        "customer_name": c_name,
                                        "is_known_customer": True,
                                        "profile": prof,
                                        "confidence": 0.95,
                                        "requires_human_review": not prof.get("verified_by_human", True),
                                        "review_reason": "Known customer profile matched" if prof.get("verified_by_human", True) else "Customer profile pending human confirmation"
                                    }
                    except Exception:
                        pass

        # Fallback: Heuristic customer extraction for new customer
        cust_candidate = ""
        end_cust_m = re.search(r'(?:end\s+customer|customer|client)[:\s]+([A-Za-z0-9 .&_-]{3,30})', body, re.IGNORECASE)
        if end_cust_m:
            cust_candidate = end_cust_m.group(1).strip()
        else:
            # Check domain from sender (e.g. user@tecan.com -> Tecan)
            domain_m = re.search(r'@([a-zA-Z0-9-]+)\.', sender)
            if domain_m:
                d_name = domain_m.group(1).lower()
                if d_name not in ("gmail", "yahoo", "hotmail", "outlook", "radysis-asia", "radysis"):
                    cust_candidate = d_name.title()

        if not cust_candidate:
            # Check for pattern "from CUST-..." in body
            opp_m = re.search(r'(?:from|opportunity\s+from|customer|client)[:\s]+([A-Za-z0-9_-]+)', body, re.I)
            if opp_m:
                c_val = opp_m.group(1).strip()
                if c_val.lower() not in ("the", "our", "team", "this", "you"):
                    cust_candidate = c_val

        if not cust_candidate:
            # Check subject keywords
            for part in re.split(r'[-_~:]', subject):
                p_clean = part.strip()
                if p_clean and len(p_clean) >= 3 and not re.search(r'\b(?:rfq|request\s+for\s+quotation|enquiry|enquiry\s+for\s+quotation|cable|fwd|re|relocation|wire|rs25|rs26|rs24)\b', p_clean, re.I):
                    cust_candidate = p_clean
                    break

        resolved = cust_candidate or "New Customer"
        return {
            "customer_name": resolved,
            "is_known_customer": False,
            "profile": None,
            "confidence": 0.65,
            "requires_human_review": True,
            "review_reason": f"New Customer '{resolved}' — human verification recommended"
        }

    def learn_or_update_customer_pattern(self, customer_name: str, rfq_json: Dict[str, Any], feedback_notes: str = "") -> bool:
        """
        Learns and persists customer pattern from a verified/corrected RFQ JSON.
        """
        if not customer_name or customer_name == "New Customer":
            customer_name = rfq_json.get("rfq_metadata", {}).get("customer_name", "Customer")

        existing_profile = self.get_profile(customer_name) or {
            "customer_name": customer_name,
            "aliases": [customer_name.lower()],
            "default_commodity": rfq_json.get("rfq_metadata", {}).get("commodity", "Wire Harness"),
            "archetypes": {},
            "mpn_blacklist": ["number and name", "component", "description", "item", "order code"],
            "verified_by_human": True,
            "version": 1
        }

        assemblies = rfq_json.get("assemblies", [])
        has_drawings = bool(rfq_json.get("drawings_detected"))
        
        archetype_key = "learned_package_archetype"
        if has_drawings and len(assemblies) > 1:
            archetype_key = "multi_assembly_drawing_package"
        elif len(assemblies) == 1:
            archetype_key = "single_assembly_package"

        existing_profile["archetypes"][archetype_key] = {
            "description": f"Learned from RFQ {rfq_json.get('rfq_metadata', {}).get('rfq_number', '')} on {rfq_json.get('rfq_metadata', {}).get('received_date', '')}",
            "assemblies_count_sample": len(assemblies),
            "sample_assy_numbers": [a.get("assy_no") for a in assemblies[:5] if a.get("assy_no")],
            "has_drawings": has_drawings,
            "feedback_notes": feedback_notes
        }
        existing_profile["verified_by_human"] = True
        existing_profile["version"] = existing_profile.get("version", 1) + 1

        return self.save_profile(existing_profile)
