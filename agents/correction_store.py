# ==============================================================================
# --- ContinuumX Correction Store ---
# Persistent few-shot correction database for RFQ extraction agents.
# Saves user corrections to corrections.json; retrieved at runtime to inject
# as few-shot examples into Gemini prompts for improved future extractions.
# ==============================================================================

import os
import sys
import json
import configparser
from datetime import datetime

if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS') or "__compiled__" in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif '__file__' in globals():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
elif len(sys.argv) > 0 and sys.argv[0] and sys.argv[0] != '-c':
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
else:
    BASE_DIR = os.getcwd()


def _load_server_path():
    """Load server path from config.ini for corrections file location."""
    for cfg_path in [
        os.path.join(BASE_DIR, "config.ini"),
        os.path.normpath(os.path.join(BASE_DIR, "..", "config.ini")),
    ]:
        if os.path.exists(cfg_path):
            try:
                cfg = configparser.ConfigParser()
                cfg.read(cfg_path, encoding='utf-8')
                for section in ('Network', 'PATHS'):
                    for key in ('ServerPath', 'server_path'):
                        if section in cfg and key in cfg[section]:
                            sp = cfg[section][key].strip()
                            if sp:
                                return sp
            except Exception:
                pass
    return ""


class CorrectionStore:
    """
    Persistent correction database for RFQ extraction agents.

    Corrections are saved as JSON records and loaded at extraction time
    to inject as few-shot examples into Gemini prompts.

    Storage: data/corrections/corrections.json (relative to BASE_DIR)
    """

    def __init__(self):
        corrections_dir = os.path.join(BASE_DIR, "data", "corrections")
        os.makedirs(corrections_dir, exist_ok=True)
        self._corrections_path = os.path.join(corrections_dir, "corrections.json")

    def _load_all(self):
        if not os.path.exists(self._corrections_path):
            return []
        try:
            with open(self._corrections_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_all(self, records):
        try:
            with open(self._corrections_path, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[CorrectionStore] Failed to save corrections: {e}")

    def save_correction(self, doc_hint, field, wrong_value, correct_value,
                        mfr="", note="", corrected_by="User"):
        """
        Save a user correction for a specific field.

        Args:
            doc_hint:      Fuzzy match key — assy_no prefix or filename prefix
            field:         Field that was wrong (mpn, mfr, description, qty, uom, assy_rev, etc.)
            wrong_value:   What the agent extracted (may be empty string)
            correct_value: What the user says is correct
            mfr:           Manufacturer name (for component corrections)
            note:          Optional user note explaining the correction
            corrected_by:  Username who submitted the correction
        """
        records = self._load_all()
        record = {
            "doc_hint": str(doc_hint).strip(),
            "field": str(field).strip(),
            "wrong_value": str(wrong_value).strip(),
            "correct_value": str(correct_value).strip(),
            "mfr": str(mfr).strip(),
            "note": str(note).strip(),
            "corrected_by": str(corrected_by).strip(),
            "timestamp": datetime.now().isoformat()
        }
        # Avoid duplicate corrections (same doc_hint + field + correct_value)
        records = [r for r in records
                   if not (r.get("doc_hint") == record["doc_hint"]
                           and r.get("field") == record["field"]
                           and r.get("correct_value") == record["correct_value"])]
        records.append(record)
        self._save_all(records)
        print(f"[CorrectionStore] Saved: {doc_hint} | {field}: {wrong_value!r} -> {correct_value!r}")
        return record

    def get_relevant_corrections(self, doc_hint, fields=None):
        """
        Retrieve corrections relevant to a document and optionally filtered by fields.

        Matching strategy (fuzzy):
        1. Exact doc_hint match
        2. doc_hint startswith stored hint (or vice versa)
        3. Shared 6-char prefix (catches part number family matches)

        Args:
            doc_hint: Assy no or filename prefix to match against stored corrections
            fields:   Optional list of field names to filter (None = return all)

        Returns:
            List of matching correction records (dicts)
        """
        all_records = self._load_all()
        hint_clean = str(doc_hint).strip().upper()
        if not hint_clean:
            return []
        matched = []
        for rec in all_records:
            stored = str(rec.get("doc_hint", "")).strip().upper()
            if not stored:
                continue
            # Precise matching: exact or clean separator boundary
            match = (
                stored == hint_clean
                or (stored.startswith(hint_clean) and (len(stored) == len(hint_clean) or stored[len(hint_clean)] in ("-", "_", ".", " ", ":", "/")))
                or (hint_clean.startswith(stored) and (len(hint_clean) == len(stored) or hint_clean[len(stored)] in ("-", "_", ".", " ", ":", "/")))
            )
            if match:
                if fields is None or rec.get("field") in fields:
                    matched.append(rec)
        return matched

    def get_field_correction(self, doc_hint, field):
        """Returns the most recent correction record for a specific doc_hint and field, or None."""
        if not doc_hint:
            return None
        recs = self.get_relevant_corrections(doc_hint, fields=[field])
        if recs:
            return recs[-1]
        return None

    def get_all(self):
        """Return all stored corrections sorted by timestamp descending."""
        records = self._load_all()
        return sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)

    def save_taught_rule(self, rule_text, category="general", doc_hint="GLOBAL", taught_by="User"):
        """
        Save a general engineering knowledge item or extraction rule taught by the user directly in chat.
        """
        records = self._load_all()
        clean_rule = str(rule_text).strip()
        record = {
            "type": "taught_rule",
            "doc_hint": str(doc_hint).strip() or "GLOBAL",
            "field": category,
            "rule": clean_rule,
            "wrong_value": "",
            "correct_value": clean_rule,
            "taught_by": str(taught_by).strip(),
            "timestamp": datetime.now().isoformat()
        }
        # Deduplicate identical rules
        records = [r for r in records if not (r.get("rule") == clean_rule and r.get("doc_hint") == record["doc_hint"])]
        records.append(record)
        self._save_all(records)
        print(f"[CorrectionStore] Learned Rule ({category}): {clean_rule}")
        return record

    def get_all_memory_context(self, limit=20):
        """
        Formats all persistent field corrections and user-taught rules into a comprehensive
        few-shot memory block for Gemini prompts.
        """
        records = self.get_all()
        if not records:
            return ""

        lines = ["--- PERMANENT AI MEMORY & USER-TAUGHT RULES ---"]
        for r in records[:limit]:
            if r.get("type") == "taught_rule" or "rule" in r:
                lines.append(f"• [RULE - {r.get('doc_hint', 'GLOBAL')}]: {r.get('rule', '')} (Taught by: {r.get('taught_by', 'User')})")
            else:
                dh = r.get('doc_hint', 'General')
                f = r.get('field', 'item')
                w = r.get('wrong_value', '')
                c = r.get('correct_value', '')
                m = r.get('mfr', '')
                m_str = f" [MFR: {m}]" if m else ""
                lines.append(f"• [CORRECTION - {dh}] {f}: extracted as '{w}' -> MUST BE '{c}'{m_str}")
        lines.append("--- END OF AI MEMORY ---")
        return "\n".join(lines)

    def delete_correction(self, doc_hint, field, correct_value):
        """Remove a specific correction record."""
        records = self._load_all()
        before = len(records)
        records = [r for r in records
                   if not (r.get("doc_hint") == doc_hint
                           and r.get("field") == field
                           and r.get("correct_value") == correct_value)]
        self._save_all(records)
        return before - len(records)
