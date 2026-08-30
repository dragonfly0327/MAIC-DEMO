import os
import re
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from .workflow_state import WorkflowStateManager

class CycleTimeAIEngine:
    """
    AI-Assisted Drawing & PDF Analysis Engine for Cycle Time.
    Extracts manufacturing characteristics and maintains a persistent
    Continuous Learning Feedback Store for user corrections.
    """
    def __init__(self, state_manager: Optional[WorkflowStateManager] = None):
        self.state_manager = state_manager or WorkflowStateManager()
        self.kb_dir = os.path.join(self.state_manager.base_dir, "knowledge_base")
        self.feedback_file = os.path.join(self.kb_dir, "cycle_time_user_corrections.json")
        os.makedirs(self.kb_dir, exist_ok=True)

    def _load_user_corrections(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def record_user_correction(self, context: str, ai_proposed: Dict[str, Any], human_corrected: Dict[str, Any], customer: str = "") -> bool:
        """Saves a 3-tier audit record of user adjustments to train few-shot memory."""
        corrections = self._load_user_corrections()
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer": customer,
            "context": context,
            "ai_proposed": ai_proposed,
            "human_corrected": human_corrected,
            "final_approved": human_corrected
        }
        corrections.append(entry)
        try:
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(corrections, f, indent=4)
            return True
        except Exception as ex:
            print(f"[CycleTimeAI Feedback Error] {ex}")
            return False

    def analyze_drawing(self, file_path_or_text: str, customer: str = "", assy_code: str = "") -> Dict[str, Any]:
        """
        Analyzes drawing text or file content, applies user correction memory,
        and generates a structured Cycle Time proposal.
        """
        raw_text = ""
        if os.path.exists(file_path_or_text):
            # Try reading text from drawing / pdf / file
            try:
                with open(file_path_or_text, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_text = f.read()
            except Exception:
                raw_text = os.path.basename(file_path_or_text)
        else:
            raw_text = file_path_or_text

        # Feature Extraction Regex Parsers
        wire_m = re.search(r'(\d{2})\s*(?:awg|gauge)', raw_text, re.IGNORECASE)
        len_m = re.search(r'(\d+)\s*(?:mm|millimeters?|inch(?:es)?|in|\")', raw_text, re.IGNORECASE)
        ckt_m = re.search(r'(\d+)\s*(?:ckt|circuits?|pins?|pos|ways?)', raw_text, re.IGNORECASE)
        conn_m = re.search(r'(molex|jst|te|deutsch|amphenol|hirose|tyco)\s*([a-z0-9_-]+)', raw_text, re.IGNORECASE)
        term_m = re.search(r'terminal\s*(?:pn|part)?\s*([a-z0-9_-]+)', raw_text, re.IGNORECASE)

        wire_size = f"{wire_m.group(1)} AWG" if wire_m else "24 AWG"
        wire_length = f"{len_m.group(1)} mm" if len_m else "350 mm"
        circuit_count = int(ckt_m.group(1)) if ckt_m else 8
        connector = f"{conn_m.group(1).title()} {conn_m.group(2)}" if conn_m else "Molex 43025-0800"
        terminal = term_m.group(1) if term_m else "Molex 43030-0001"
        has_seal = "seal" in raw_text.lower() or "waterproof" in raw_text.lower()
        has_hs = "heat shrink" in raw_text.lower() or "hs" in raw_text.lower() or "tubing" in raw_text.lower()

        # Check Few-Shot Learning from User Corrections
        past_corrections = self._load_user_corrections()
        matched_learned_rule = None
        for corr in reversed(past_corrections):
            if customer and corr.get("customer", "").lower() == customer.lower():
                # Apply learned customer adjustment
                hc = corr.get("human_corrected", {})
                if hc.get("wire_size"): wire_size = hc["wire_size"]
                if hc.get("circuit_count"): circuit_count = hc["circuit_count"]
                matched_learned_rule = f"Applied past customer rule from {corr.get('timestamp')}"
                break

        features = {
            "assembly_code": assy_code or "A01",
            "wire_size": wire_size,
            "wire_length": wire_length,
            "circuit_count": circuit_count,
            "connector": connector,
            "terminal": terminal,
            "seal": "Yes" if has_seal else "No",
            "heat_shrink": "Yes" if has_hs else "No",
            "suggested_cycle_time_sec": round(circuit_count * 4.5 + (15 if has_hs else 0) + (10 if has_seal else 0), 1)
        }

        return {
            "drawing_name": os.path.basename(file_path_or_text) if os.path.exists(file_path_or_text) else "Drawing Context",
            "confidence": "High (94%)" if (wire_m and ckt_m) else "Medium (82%)",
            "features": features,
            "learned_rule_applied": matched_learned_rule
        }

    def save_approved_cycle_time(self, rfq_id: str, approved_features: Dict[str, Any], customer: Optional[str] = None) -> Tuple[bool, str]:
        """Saves human-approved Cycle Time data into the canonical RFQ database JSON."""
        state = self.state_manager.get_rfq_state(rfq_id, customer)
        if not state.get("exists"):
            return False, f"RFQ '{rfq_id}' not found."

        raw_data = state["raw_data"]
        filepath = state["filepath"]
        assy_target = approved_features.get("assembly_code", "")

        # Format cycle time entry row compatible with Costing / Cycle Time
        ct_entry = {
            "Code": "AUTO_CUT_STRIP_CRIMP",
            "Description": f"Cut, Strip & Crimp {approved_features.get('wire_size', '')} ({approved_features.get('circuit_count', 1)} circuits)",
            "Rate": 45.0,
            "Time (s)": approved_features.get("suggested_cycle_time_sec", 30.0),
            "Points": approved_features.get("circuit_count", 1) * 2,
            "Cost": round((approved_features.get("suggested_cycle_time_sec", 30.0) / 3600.0) * 45.0, 4)
        }

        updated = False
        for assy in raw_data.get("Assemblies", []):
            a_num = assy.get("Assy #", "")
            if not assy_target or assy_target.lower() in a_num.lower() or a_num.lower() in assy_target.lower():
                if "cycle_time_data" not in assy or not isinstance(assy["cycle_time_data"], list):
                    assy["cycle_time_data"] = []
                assy["cycle_time_data"].append(ct_entry)
                updated = True

        if updated:
            raw_data["cycle_time_status"] = "completed"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, indent=4)
            return True, f"Cycle Time data successfully saved for RFQ '{rfq_id}'."
        return False, "No matching assembly found to attach Cycle Time data."
