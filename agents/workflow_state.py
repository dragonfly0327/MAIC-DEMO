# ==============================================================================
# --- ContinuumX Workflow State Manager ---
# Reads live workflow state directly from existing subsystem databases.
# DO NOT hardcode statuses; queries BOM Data, Sourcing, Costing, and Locks.
# ==============================================================================

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ContinuumX.WorkflowState")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class WorkflowStateManager:
    """
    Authoritative state provider querying live subsystem data files.
    """

    @classmethod
    def _ensure_module_path(cls, module_name: str) -> str:
        target_dir = os.path.normpath(os.path.join(BASE_DIR, "ref", module_name))
        if os.path.exists(target_dir) and target_dir not in sys.path:
            sys.path.append(target_dir)
        return target_dir

    @classmethod
    def find_rfq_file(cls, rfq_id: str) -> Optional[str]:
        """Searches BOM Data/ for an RFQ JSON file."""
        cls._ensure_module_path("BOM")
        try:
            from utils import BOM_DATA_DIR
            if not os.path.exists(BOM_DATA_DIR):
                return None

            clean_target = str(rfq_id).strip().lower().replace("rfq", "").replace("-", "").replace("_", "")

            for root, _, files in os.walk(BOM_DATA_DIR):
                for f in files:
                    if f.endswith(".json") and not f.endswith("metadata.json"):
                        f_base = os.path.splitext(f)[0].lower()
                        f_clean = f_base.replace("rfq", "").replace("-", "").replace("_", "")
                        if f_base == str(rfq_id).lower() or f_clean == clean_target:
                            return os.path.join(root, f)
        except Exception as e:
            logger.warning(f"Error finding RFQ file for {rfq_id}: {e}")
        return None

    @classmethod
    def get_session_lock_info(cls, rfq_id: str) -> Dict[str, Any]:
        """Checks if an RFQ is currently locked by a human user."""
        cls._ensure_module_path("BOM")
        try:
            from utils import DATA_PATH
            lock_file = os.path.join(DATA_PATH, "active_session_locks.json") if DATA_PATH else None
            if lock_file and os.path.exists(lock_file):
                with open(lock_file, "r", encoding="utf-8") as f:
                    locks = json.load(f)
                if rfq_id in locks:
                    return {
                        "is_locked": True,
                        "locked_by": locks[rfq_id].get("user", "Unknown"),
                        "locked_at": locks[rfq_id].get("timestamp", "")
                    }
        except Exception:
            pass
        return {"is_locked": False, "locked_by": None, "locked_at": None}

    @classmethod
    def get_rfq_workflow_state(cls, rfq_id: str) -> Dict[str, Any]:
        """
        Queries live subsystem data and returns the structured state of an RFQ.
        """
        rfq_file = cls.find_rfq_file(rfq_id)
        if not rfq_file or not os.path.exists(rfq_file):
            return {
                "exists": False,
                "rfq_id": rfq_id,
                "error": f"RFQ '{rfq_id}' not found in BOM database."
            }

        try:
            with open(rfq_file, "r", encoding="utf-8-sig") as f:
                raw_data = json.load(f)
        except Exception as e:
            return {
                "exists": False,
                "rfq_id": rfq_id,
                "error": f"Failed to read RFQ JSON: {e}"
            }

        actual_rfq = raw_data.get("RFQ") or raw_data.get("rfq_id") or rfq_id
        customer = raw_data.get("Customer") or raw_data.get("customer_name") or "Customer"
        current_stage = str(raw_data.get("status", "pending_bom")).strip()

        # Sub-statuses from existing system fields
        sourcing_status = str(raw_data.get("sourcing_status", "pending")).strip()
        cycle_time_status = str(raw_data.get("cycle_time_status", "pending")).strip()
        global_moqs = raw_data.get("Global MOQs", [])
        assemblies = raw_data.get("Assemblies", [])
        revert_pending = raw_data.get("revert_pending")

        # Check Costing quotation status
        costing_info = cls._check_costing_state(customer, actual_rfq)
        
        # Check Session Lock
        lock_info = cls.get_session_lock_info(actual_rfq)

        # Check Existing Subsystem Dispatch Eligibility (RPA query)
        eligible_dispatches = cls._check_system_dispatch_eligibility(
            actual_rfq, customer, raw_data, current_stage, sourcing_status, cycle_time_status
        )

        # Determine next available actions
        next_actions = cls._determine_next_actions(
            current_stage, sourcing_status, cycle_time_status, global_moqs, costing_info, eligible_dispatches
        )

        return {
            "exists": True,
            "rfq_id": actual_rfq,
            "customer": customer,
            "current_stage": current_stage.upper(),
            "raw_status": current_stage,
            "is_locked": lock_info["is_locked"],
            "locked_by": lock_info["locked_by"],
            "bom": {
                "status": "completed" if current_stage != "pending_bom" else ("review_ready" if global_moqs else "pending"),
                "global_moqs": global_moqs,
                "assemblies_count": len(assemblies),
                "dispatched_by": raw_data.get("bom_dispatched_by") or raw_data.get("dispatched_by")
            },
            "sourcing": {
                "status": sourcing_status,
                "is_completed": sourcing_status.lower() in ("completed", "approved"),
                "dispatched_by": raw_data.get("sourcing_dispatched_by")
            },
            "cycle_time": {
                "status": cycle_time_status,
                "is_completed": cycle_time_status.lower() in ("completed", "approved"),
                "dispatched_by": raw_data.get("cycle_time_dispatched_by")
            },
            "costing": costing_info,
            "revert_pending": revert_pending,
            "system_eligible_dispatches": eligible_dispatches,
            "next_available_actions": next_actions,
            "filepath": rfq_file
        }

    @classmethod
    def _check_costing_state(cls, customer: str, rfq_id: str) -> Dict[str, Any]:
        """Checks existing Costing Saved Quotations directory."""
        cls._ensure_module_path("Costing")
        from utils import BASE_DIR, load_server_path
        
        # Candidate directories for Saved Quotations
        safe_cust = customer.replace(" ", "_").replace("/", "_").replace("\\", "_")
        safe_rfq = rfq_id.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        server_path = load_server_path()
        candidates = []
        if server_path:
            candidates.append(os.path.join(server_path, "Saved Quotations", safe_cust, f"{safe_rfq}.json"))
            candidates.append(os.path.join(server_path, "Costing", "AppData", "Saved Quotations", safe_cust, f"{safe_rfq}.json"))
        candidates.append(os.path.normpath(os.path.join(BASE_DIR, "ref", "Costing", "AppData", "Saved Quotations", safe_cust, f"{safe_rfq}.json")))
        
        quotation_file = next((p for p in candidates if os.path.exists(p)), None)
        if quotation_file:
            try:
                with open(quotation_file, "r", encoding="utf-8") as f:
                    q_data = json.load(f)
                return {
                    "has_quotation": True,
                    "status": "saved",
                    "approval_status": q_data.get("approval_status", "Pending"),
                    "gross_margin": q_data.get("summary_metrics", {}).get("gross_margin_pct"),
                    "filepath": quotation_file
                }
            except Exception:
                pass

        return {
            "has_quotation": False,
            "status": "pending",
            "approval_status": None,
            "gross_margin": None,
            "filepath": None
        }

    @classmethod
    def _check_system_dispatch_eligibility(
        cls,
        rfq_id: str,
        customer: str,
        raw_data: Dict[str, Any],
        current_stage: str,
        sourcing_status: str,
        cycle_time_status: str
    ) -> List[str]:
        """
        Directly mirrors each subsystem's exact native dispatch window logic.
        Whatever appears in the module's dispatch window is 100% eligible here.
        """
        eligible = []
        c_stage = str(current_stage).strip().lower()

        # 1. BOM Dispatch Window Logic (ref/BOM/sourcing_wizard.py: BOMDatabaseSearchPanel)
        if c_stage not in ("pending_sourcing_and_cycle_time", "pending_costing", "completed"):
            has_moq = bool(
                raw_data.get("Global MOQs")
                or any(a.get("Assigned MOQs") for a in raw_data.get("Assemblies", []))
            )
            if not has_moq:
                # Check assigned_moqs_metadata.json
                cls._ensure_module_path("BOM")
                from utils import BOM_DATA_DIR
                meta_path = os.path.join(BOM_DATA_DIR, "assigned_moqs_metadata.json")
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                            for item in meta.get("completed_moqs", []):
                                if item.get("Customer") == customer and item.get("RFQ") == rfq_id:
                                    has_moq = True
                                    break
                    except Exception:
                        pass
            if has_moq:
                eligible.append("bom")

        # 2. Sourcing Dispatch Window Logic (ref/Sourcing/sourcing_wizard.py)
        if c_stage in ("pending_sourcing_and_cycle_time", "pending_cycle_time"):
            if sourcing_status.lower() in ("completed", "approved"):
                eligible.append("sourcing")

        # 3. Cycle Time Dispatch Window Logic (ref/Cycle Time/main.py: CycleTimeDispatchDialog)
        if c_stage in ("pending_sourcing_and_cycle_time", "pending_sourcing", "pending_cycle_time_dispatch"):
            if cycle_time_status.lower() in ("completed", "approved") or c_stage == "pending_sourcing":
                eligible.append("cycle_time")

        # 4. Costing Dispatch Window Logic (ref/Costing/summary_table_page.py)
        if c_stage == "pending_costing":
            q_info = cls._check_costing_state(customer, rfq_id)
            if q_info.get("has_quotation"):
                eligible.append("costing")

        return eligible

    @classmethod
    def _determine_next_actions(
        cls,
        current_stage: str,
        sourcing_status: str,
        cycle_time_status: str,
        global_moqs: List[int],
        costing_info: Dict[str, Any],
        eligible_dispatches: List[str]
    ) -> List[str]:
        """Returns the list of valid next tools based on live state."""
        actions = []

        # Priority 1: Execute available dispatches
        for dept in eligible_dispatches:
            actions.append(f"{dept}.execute_system_dispatch")

        # Priority 2: Subsystem actions based on stage
        if current_stage == "pending_bom":
            if not global_moqs:
                actions.append("bom.open_review_window")
        elif current_stage in ("pending_sourcing_and_cycle_time", "pending_sourcing"):
            if sourcing_status.lower() not in ("completed", "approved"):
                actions.append("sourcing.auto_calculate")
                actions.append("sourcing.open_review_window")
            if cycle_time_status.lower() not in ("completed", "approved"):
                actions.append("cycle_time.ai_extract_drawing")
                actions.append("cycle_time.open_review_window")
        elif current_stage == "pending_costing":
            if not costing_info["has_quotation"]:
                actions.append("costing.auto_calculate_quotation")
                actions.append("costing.open_review_window")
            elif costing_info["approval_status"] != "Approved":
                actions.append("costing.open_approval_composer")

        return actions
