import os
import sys
import json
import configparser
from datetime import datetime
from typing import Dict, Any, Optional, List

# Standardized Base Directory Resolution Pattern
if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS') or "__compiled__" in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif '__file__' in globals():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
elif len(sys.argv) > 0 and sys.argv[0] and sys.argv[0] != '-c':
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0]))))
else:
    BASE_DIR = os.getcwd()

class WorkflowStage:
    EMAIL = "email"
    BOM = "bom"
    SOURCING = "sourcing"
    CYCLE_TIME = "cycle_time"
    COSTING = "costing"
    NPI = "npi"
    WI = "wi"
    COMPLETED = "completed"

class WorkflowStatus:
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_HUMAN_APPROVAL = "WAITING_FOR_HUMAN_APPROVAL"
    COMPLETED = "COMPLETED"
    REVERTED = "REVERTED"
    ERROR = "ERROR"

class WorkflowStateManager:
    """
    Manages persistent, auditable RFQ orchestration states.
    Reads and writes non-destructively to the canonical database JSON files
    stored in BOM Data/<Customer>/<RFQ>.json.
    """
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or BASE_DIR
        self.server_path = self._load_server_path()
        self.bom_data_dir = os.path.normpath(os.path.join(self.server_path, "BOM", "AppData", "BOM Data")) if self.server_path else ""

    def _load_server_path(self) -> str:
        candidate_cfgs = [
            os.path.join(self.base_dir, "config.ini"),
            os.path.normpath(os.path.join(self.base_dir, "..", "config.ini")),
            os.path.normpath(os.path.join(self.base_dir, "ref", "BOM", "config.ini"))
        ]
        for cfg_path in candidate_cfgs:
            if os.path.exists(cfg_path):
                try:
                    cfg = configparser.ConfigParser()
                    cfg.read(cfg_path, encoding='utf-8')
                    if 'Network' in cfg and 'ServerPath' in cfg['Network']:
                        sp = cfg['Network']['ServerPath'].strip()
                        if sp: return sp
                    if 'PATHS' in cfg and 'server_path' in cfg['PATHS']:
                        sp = cfg['PATHS']['server_path'].strip()
                        if sp: return sp
                except Exception:
                    pass
        # Dynamic default relative to self.base_dir
        return os.path.join(self.base_dir, "test_server_mock")

    def resolve_rfq_filepath(self, rfq_id: str, customer: Optional[str] = None) -> Optional[str]:
        """Finds the absolute path of an RFQ's JSON file in BOM Data."""
        if not self.bom_data_dir or not os.path.exists(self.bom_data_dir):
            # Fallback path lookup
            alt_dir = os.path.join(self.base_dir, "ref", "BOM", "AppData", "BOM Data")
            if os.path.exists(alt_dir):
                self.bom_data_dir = alt_dir
            else:
                return None

        clean_rfq = str(rfq_id).strip().lower()
        if customer:
            clean_cust = str(customer).replace(" ", "_").strip()
            cust_folder = os.path.join(self.bom_data_dir, clean_cust)
            if os.path.exists(cust_folder):
                for f in os.listdir(cust_folder):
                    if f.lower().endswith(".json"):
                        f_stem = os.path.splitext(f)[0].lower()
                        if f_stem == clean_rfq or f_stem.replace(" ", "_") == clean_rfq.replace(" ", "_"):
                            return os.path.join(cust_folder, f)

        # Global search in BOM Data across all customer directories
        for root_dir, _, files in os.walk(self.bom_data_dir):
            for f in files:
                if f.lower().endswith(".json") and not f.lower().endswith("_metadata.json"):
                    f_stem = os.path.splitext(f)[0].lower()
                    if f_stem == clean_rfq or f_stem.replace(" ", "_") == clean_rfq.replace(" ", "_"):
                        return os.path.join(root_dir, f)
        return None

    def get_rfq_state(self, rfq_id: str, customer: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves raw data and orchestration state for a given RFQ."""
        fpath = self.resolve_rfq_filepath(rfq_id, customer)
        if not fpath or not os.path.exists(fpath):
            return {"exists": False, "rfq_id": rfq_id, "error": "BOM JSON file not found."}

        try:
            with open(fpath, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)

            orch = data.get("orchestration", {})
            if not orch:
                # Infer default orchestration state from legacy fields
                curr_status = data.get("status", "pending_bom")
                src_status = data.get("sourcing_status", "pending")
                ct_status = data.get("cycle_time_status", "pending")

                orch = {
                    "workflow_status": WorkflowStatus.IN_PROGRESS,
                    "active_stage": curr_status,
                    "stages": {
                        WorkflowStage.EMAIL: {"status": WorkflowStatus.COMPLETED},
                        WorkflowStage.BOM: {"status": WorkflowStatus.COMPLETED if curr_status != "pending_bom" else WorkflowStatus.IN_PROGRESS},
                        WorkflowStage.SOURCING: {"status": WorkflowStatus.COMPLETED if src_status == "completed" else WorkflowStatus.IN_PROGRESS if curr_status in ["pending_sourcing", "pending_sourcing_and_cycle_time"] else WorkflowStatus.NOT_STARTED},
                        WorkflowStage.CYCLE_TIME: {"status": WorkflowStatus.COMPLETED if ct_status == "completed" else WorkflowStatus.IN_PROGRESS if curr_status in ["pending_sourcing_and_cycle_time", "pending_cycle_time"] else WorkflowStatus.NOT_STARTED},
                        WorkflowStage.COSTING: {"status": WorkflowStatus.COMPLETED if curr_status in ["pending_npi", "pending_wi", "completed"] else WorkflowStatus.IN_PROGRESS if curr_status == "pending_costing" else WorkflowStatus.NOT_STARTED},
                        WorkflowStage.NPI: {"status": WorkflowStatus.COMPLETED if curr_status in ["pending_wi", "completed"] else WorkflowStatus.IN_PROGRESS if curr_status == "pending_npi" else WorkflowStatus.NOT_STARTED},
                        WorkflowStage.WI: {"status": WorkflowStatus.COMPLETED if curr_status == "completed" else WorkflowStatus.IN_PROGRESS if curr_status == "pending_wi" else WorkflowStatus.NOT_STARTED}
                    },
                    "approval": {
                        "required": False,
                        "checkpoint": None,
                        "stage": None,
                        "summary": None
                    }
                }

            return {
                "exists": True,
                "filepath": fpath,
                "rfq_id": data.get("RFQ") or data.get("rfq_id") or rfq_id,
                "customer": data.get("Customer") or data.get("customer_name") or "",
                "commodity": data.get("Commodity") or "",
                "project_title": data.get("Project Title") or "",
                "status": data.get("status", "pending_bom"),
                "sourcing_status": data.get("sourcing_status", "pending"),
                "cycle_time_status": data.get("cycle_time_status", "pending"),
                "global_moqs": data.get("Global MOQs", []),
                "assemblies": data.get("Assemblies", []),
                "orchestration": orch,
                "raw_data": data
            }
        except Exception as e:
            return {"exists": False, "rfq_id": rfq_id, "error": str(e)}

    def _calc_tp_eau_status(self, data: Dict[str, Any]) -> tuple:
        """Evaluates Target Price and EAU assignation status ('Completed', 'Partial', 'Pending')."""
        assemblies = data.get("Assemblies", [])
        if not assemblies:
            return "Pending", "Pending"

        has_tp = False
        all_tp = True
        has_eau = False
        all_eau = True

        for assy in assemblies:
            assigned_moqs = assy.get("Assigned MOQs", [])
            if not assigned_moqs:
                all_tp = False
                all_eau = False
                continue

            tp_dict = assy.get("Target Prices", {})
            for moq in assigned_moqs:
                val = tp_dict.get(str(moq))
                try:
                    if val is not None and str(val).strip() != "" and float(val) > 0.0:
                        has_tp = True
                    else:
                        all_tp = False
                except (ValueError, TypeError):
                    all_tp = False

            eau_data = assy.get("EAU", {})
            if isinstance(eau_data, (int, float, str)):
                try:
                    if float(eau_data) > 0:
                        has_eau = True
                    else:
                        all_eau = False
                except (ValueError, TypeError):
                    all_eau = False
            elif isinstance(eau_data, dict):
                for moq in assigned_moqs:
                    val = eau_data.get(str(moq))
                    try:
                        if val is not None and str(val).strip() != "" and float(val) > 0.0:
                            has_eau = True
                        else:
                            all_eau = False
                    except (ValueError, TypeError):
                        all_eau = False
            else:
                all_eau = False

        tp_status = "Completed" if all_tp else ("Partial" if has_tp else "Pending")
        eau_status = "Completed" if all_eau else ("Partial" if has_eau else "Pending")
        return tp_status, eau_status

    def save_orchestration_state(self, rfq_id: str, customer: Optional[str], orch_state: Dict[str, Any]) -> bool:
        """Persists updated orchestration block back into the RFQ JSON."""
        fpath = self.resolve_rfq_filepath(rfq_id, customer)
        if not fpath or not os.path.exists(fpath):
            return False

        try:
            with open(fpath, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)

            data["orchestration"] = orch_state
            
            # Atomic write
            temp_path = fpath + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            if os.path.exists(fpath):
                os.remove(fpath)
            os.rename(temp_path, fpath)
            return True
        except Exception as ex:
            print(f"[WorkflowState Error] Failed to save state for RFQ {rfq_id}: {ex}")
            return False

    def set_approval_checkpoint(self, rfq_id: str, checkpoint_id: str, stage: str, summary_data: Dict[str, Any], customer: Optional[str] = None) -> bool:
        """Enters WAITING_FOR_HUMAN_APPROVAL checkpoint for an RFQ."""
        state = self.get_rfq_state(rfq_id, customer)
        if not state.get("exists"):
            return False

        orch = state.get("orchestration", {})
        orch["workflow_status"] = WorkflowStatus.WAITING_FOR_HUMAN_APPROVAL
        orch["active_stage"] = stage
        orch["approval"] = {
            "required": True,
            "checkpoint": checkpoint_id,
            "stage": stage,
            "summary": summary_data,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return self.save_orchestration_state(rfq_id, customer, orch)

    def clear_approval_checkpoint(self, rfq_id: str, approved_by: str = "Admin", customer: Optional[str] = None) -> bool:
        """Clears approval gate and sets status back to IN_PROGRESS upon user confirmation."""
        state = self.get_rfq_state(rfq_id, customer)
        if not state.get("exists"):
            return False

        orch = state.get("orchestration", {})
        orch["workflow_status"] = WorkflowStatus.IN_PROGRESS
        if "approval" in orch:
            orch["approval"]["required"] = False
            orch["approval"]["approved_by"] = approved_by
            orch["approval"]["approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return self.save_orchestration_state(rfq_id, customer, orch)

    def get_all_active_approval_gates(self, user_role: Optional[str] = None, username: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Scans all RFQ JSONs in database across ALL STAGES:
        1. BOM Verification (pending_bom) -> Ready for Sourcing & Cycle Time
        2. Sourcing (pending_sourcing_and_cycle_time / pending_sourcing) -> Ready for Costing
        3. Cycle Time (pending_sourcing_and_cycle_time / pending_cycle_time) -> Ready for Costing
        4. Costing (pending_costing) -> Ready for NPI Verification
        5. NPI Verification (pending_npi) -> Ready for Work Instruction
        6. Work Instruction (pending_wi) -> Ready to Complete
        """
        if not self.bom_data_dir or not os.path.exists(self.bom_data_dir):
            return []

        # Read assigned_moqs_metadata.json for confirmed MOQs
        assigned_pairs = {}
        meta_path = os.path.join(self.bom_data_dir, "assigned_moqs_metadata.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    for item in meta.get("completed_moqs", []):
                        assigned_pairs[(item.get("Customer"), item.get("RFQ"))] = item
            except Exception:
                pass

        # 1. Load Dynamic Role Permissions (role_permissions.json)
        role_allowed_stages = {
            "System Administrator": ["bom", "sourcing", "cycle_time", "costing", "npi", "wi"],
            "Top Management": ["bom", "sourcing", "cycle_time", "costing", "npi", "wi"],
            "Admin": ["bom", "sourcing", "cycle_time", "costing", "npi", "wi"],
            "Engineering": ["bom", "npi", "wi"],
            "Sourcing": ["sourcing", "cycle_time"],
            "Costing": ["costing"],
            "QAQC": ["npi", "wi"]
        }
        sec_dir = os.path.join(self.server_path, "security") if hasattr(self, "server_path") and self.server_path else ""
        if sec_dir and os.path.exists(os.path.join(sec_dir, "role_permissions.json")):
            try:
                with open(os.path.join(sec_dir, "role_permissions.json"), 'r', encoding='utf-8') as pf:
                    loaded_perms = json.load(pf)
                    mod_to_stage = {
                        "BOM": "bom",
                        "Sourcing": "sourcing",
                        "Cycle Time": "cycle_time",
                        "Costing": "costing",
                        "NPI": "npi",
                        "WI": "wi"
                    }
                    for r, mods in loaded_perms.items():
                        role_allowed_stages[r] = [mod_to_stage[m] for m in mods if m in mod_to_stage]
            except Exception:
                pass

        allowed_dept_stages = role_allowed_stages.get(user_role, ["bom", "sourcing", "cycle_time", "costing", "npi", "wi"])
        is_admin = (not user_role) or user_role in ("System Administrator", "Top Management", "Admin")

        # 2. Load System PICs Vault (system_pics.json)
        system_pics_vault = {}
        pics_candidates = [
            os.path.join(sec_dir, "system_pics.json") if sec_dir else "",
            os.path.join(self.bom_data_dir, "..", "..", "Project Management", "system_pics.json") if self.bom_data_dir else ""
        ]
        for pc in pics_candidates:
            if pc and os.path.exists(pc):
                try:
                    with open(pc, 'r', encoding='utf-8') as pf:
                        system_pics_vault = json.load(pf)
                        break
                except Exception:
                    pass

        def is_user_incharge_of_stage(stage_code: str, raw_d: Dict[str, Any]) -> bool:
            if is_admin or not username:
                return True
            # Check explicit stage PIC in RFQ
            explicit_pic = raw_d.get(f"{stage_code}_assigned_by") or raw_d.get("dispatched_by") or raw_d.get("assigned_by")
            if explicit_pic and str(explicit_pic).strip().lower() == str(username).strip().lower():
                return True
            # Check system_pics default PIC
            cfg = system_pics_vault.get(stage_code, {})
            to_list = [str(u).strip().lower() for u in cfg.get("to", [])]
            cc_list = [str(u).strip().lower() for u in cfg.get("cc", [])]
            return str(username).strip().lower() in to_list or str(username).strip().lower() in cc_list

        active_gates = []
        seen_rfq_stages = set()

        for root_dir, _, files in os.walk(self.bom_data_dir):
            for f in files:
                if f.lower().endswith(".json") and not f.lower().endswith("metadata.json"):
                    try:
                        fpath = os.path.join(root_dir, f)
                        with open(fpath, 'r', encoding='utf-8-sig') as jf:
                            data = json.load(jf)

                        rfq_id = data.get("RFQ") or os.path.splitext(f)[0]
                        customer = data.get("Customer") or os.path.basename(root_dir)
                        current_status = data.get("status", "pending_bom")
                        s_st = str(data.get("sourcing_status", "")).strip().lower()
                        ct_st = str(data.get("cycle_time_status", "")).strip().lower()
                        commodity = data.get("Commodity") or "Wire Harness"

                        moqs = data.get("Global MOQs", [])
                        if not moqs:
                            for assy in data.get("Assemblies", []):
                                if assy.get("Assigned MOQs"):
                                    moqs = assy.get("Assigned MOQs")
                                    break
                        if (customer, rfq_id) in assigned_pairs and not moqs:
                            moqs = assigned_pairs[(customer, rfq_id)].get("moqs", "Standard")
                        moq_str = ", ".join(str(m) for m in moqs) if isinstance(moqs, list) else str(moqs or "Standard / Default")

                        # 1. BOM STAGE QUEUE (BOM -> Sourcing & CT)
                        if "bom" in allowed_dept_stages and is_user_incharge_of_stage("pending_bom", data):
                            is_dispatched = current_status in ("pending_sourcing_and_cycle_time", "pending_costing", "completed")
                            has_moq = bool(moqs or (customer, rfq_id) in assigned_pairs)
                            if not is_dispatched and has_moq and (rfq_id, "bom") not in seen_rfq_stages:
                                seen_rfq_stages.add((rfq_id, "bom"))
                                tp_st, eau_st = self._calc_tp_eau_status(data)
                                active_gates.append({
                                    "rfq_id": rfq_id,
                                    "customer": customer,
                                    "commodity": commodity,
                                    "checkpoint": "CHECKPOINT_2_BOM_COMPLETED",
                                    "stage": "bom",
                                    "current_stage": "BOM Verification",
                                    "raw_stage": current_status,
                                    "next_action": "Sourcing & Cycle Time",
                                    "action_prompt": "Clicking 'Approve & Dispatch' will dispatch this RFQ to Sourcing and Cycle Time in parallel.",
                                    "pic": data.get("bom_assigned_by") or data.get("dispatched_by") or "Ai Tink",
                                    "tp_status": tp_st,
                                    "eau_status": eau_st,
                                    "tp_eau_status": f"TP: {tp_st} | EAU: {eau_st}",
                                    "summary": {
                                        "customer": customer,
                                        "current_stage": "BOM Verification",
                                        "assigned_moqs": moq_str,
                                        "assembly_count": len(data.get("Assemblies", [1])),
                                        "eau": data.get("EAU"),
                                        "target_price": data.get("Target Price"),
                                        "tp_status": tp_st,
                                        "eau_status": eau_st
                                    },
                                    "created_at": data.get("Last Update (Time)", "")
                                })

                        # 2. SOURCING STAGE QUEUE (Sourcing -> Costing)
                        if "sourcing" in allowed_dept_stages and is_user_incharge_of_stage("pending_sourcing", data):
                            if current_status in ("pending_sourcing_and_cycle_time", "pending_sourcing") and s_st in ("completed", "approved"):
                                if (rfq_id, "sourcing") not in seen_rfq_stages:
                                    seen_rfq_stages.add((rfq_id, "sourcing"))
                                    next_act = "Costing" if ct_st in ("completed", "approved") else "Wait for Cycle Time"
                                    active_gates.append({
                                        "rfq_id": rfq_id,
                                        "customer": customer,
                                        "commodity": commodity,
                                        "checkpoint": "CHECKPOINT_3_SOURCING_COMPLETED",
                                        "stage": "sourcing",
                                        "current_stage": "Sourcing",
                                        "raw_stage": current_status,
                                        "next_action": next_act,
                                        "action_prompt": "Clicking 'Approve & Dispatch' will mark Sourcing completed and dispatch this RFQ to Costing.",
                                        "pic": data.get("sourcing_assigned_by") or data.get("dispatched_by") or "TengAiTink",
                                        "summary": {
                                            "customer": customer,
                                            "current_stage": "Sourcing",
                                            "assigned_moqs": moq_str,
                                            "assembly_count": len(data.get("Assemblies", [1])),
                                            "sourcing_status": s_st.capitalize(),
                                            "cycle_time_status": ct_st.capitalize()
                                        },
                                        "created_at": data.get("Last Update (Time)", "")
                                    })

                        # 3. CYCLE TIME STAGE QUEUE (Cycle Time -> Costing)
                        if "cycle_time" in allowed_dept_stages and is_user_incharge_of_stage("pending_cycle_time", data):
                            if current_status in ("pending_sourcing_and_cycle_time", "pending_cycle_time") and ct_st in ("completed", "approved"):
                                if (rfq_id, "cycle_time") not in seen_rfq_stages:
                                    seen_rfq_stages.add((rfq_id, "cycle_time"))
                                    next_act = "Costing" if s_st in ("completed", "approved") else "Wait for Sourcing"
                                    active_gates.append({
                                        "rfq_id": rfq_id,
                                        "customer": customer,
                                        "commodity": commodity,
                                        "checkpoint": "CHECKPOINT_4_CYCLE_TIME_PROPOSAL",
                                        "stage": "cycle_time",
                                        "current_stage": "Cycle Time",
                                        "raw_stage": current_status,
                                        "next_action": next_act,
                                        "action_prompt": "Clicking 'Approve & Dispatch' will mark Cycle Time completed and dispatch this RFQ to Costing.",
                                        "pic": data.get("cycle_time_assigned_by") or data.get("dispatched_by") or "TengAiTink",
                                        "summary": {
                                            "customer": customer,
                                            "current_stage": "Cycle Time",
                                            "assigned_moqs": moq_str,
                                            "assembly_count": len(data.get("Assemblies", [1])),
                                            "cycle_time_status": ct_st.capitalize(),
                                            "sourcing_status": s_st.capitalize()
                                        },
                                        "created_at": data.get("Last Update (Time)", "")
                                    })

                        # 4. COSTING STAGE QUEUE (Costing -> NPI)
                        if "costing" in allowed_dept_stages and is_user_incharge_of_stage("pending_costing", data):
                            if current_status == "pending_costing" and (rfq_id, "costing") not in seen_rfq_stages:
                                seen_rfq_stages.add((rfq_id, "costing"))
                                active_gates.append({
                                    "rfq_id": rfq_id,
                                    "customer": customer,
                                    "commodity": commodity,
                                    "checkpoint": "CHECKPOINT_5_COSTING_COMPLETED",
                                    "stage": "costing",
                                    "current_stage": "Costing",
                                    "raw_stage": current_status,
                                    "next_action": "NPI Verification",
                                    "action_prompt": "Clicking 'Approve & Dispatch' will dispatch the calculated quotation to NPI Verification.",
                                    "pic": data.get("costing_assigned_by") or data.get("dispatched_by") or "TengAiTink",
                                    "summary": {
                                        "customer": customer,
                                        "current_stage": "Costing",
                                        "assigned_moqs": moq_str,
                                        "assembly_count": len(data.get("Assemblies", [1]))
                                    },
                                    "created_at": data.get("Last Update (Time)", "")
                                })

                        # 5. NPI STAGE QUEUE (NPI -> WI)
                        if "npi" in allowed_dept_stages and is_user_incharge_of_stage("pending_npi", data):
                            if current_status == "pending_npi" and (rfq_id, "npi") not in seen_rfq_stages:
                                seen_rfq_stages.add((rfq_id, "npi"))
                                active_gates.append({
                                    "rfq_id": rfq_id,
                                    "customer": customer,
                                    "commodity": commodity,
                                    "checkpoint": "CHECKPOINT_6_WI_FINAL_REVIEW",
                                    "stage": "npi",
                                    "current_stage": "NPI Verification",
                                    "raw_stage": current_status,
                                    "next_action": "Work Instruction (WI)",
                                    "action_prompt": "Clicking 'Approve & Dispatch' will approve NPI verification and dispatch to Work Instruction.",
                                    "pic": data.get("npi_assigned_by") or data.get("dispatched_by") or "TengAiTink",
                                    "summary": {
                                        "customer": customer,
                                        "current_stage": "NPI Verification",
                                        "assigned_moqs": moq_str,
                                        "assembly_count": len(data.get("Assemblies", [1]))
                                    },
                                    "created_at": data.get("Last Update (Time)", "")
                                })

                        # 6. WORK INSTRUCTION QUEUE (WI -> Complete)
                        if "wi" in allowed_dept_stages and is_user_incharge_of_stage("pending_wi", data):
                            if current_status == "pending_wi" and (rfq_id, "wi") not in seen_rfq_stages:
                                seen_rfq_stages.add((rfq_id, "wi"))
                                active_gates.append({
                                    "rfq_id": rfq_id,
                                    "customer": customer,
                                    "commodity": commodity,
                                    "checkpoint": "CHECKPOINT_6_WI_FINAL_REVIEW",
                                    "stage": "wi",
                                    "current_stage": "Work Instruction",
                                    "raw_stage": current_status,
                                    "next_action": "Completed Process",
                                    "action_prompt": "Clicking 'Approve & Release' will release the final Work Instruction and complete this RFQ process.",
                                    "pic": data.get("wi_assigned_by") or data.get("dispatched_by") or "TengAiTink",
                                    "summary": {
                                        "customer": customer,
                                        "current_stage": "Work Instruction",
                                        "assigned_moqs": moq_str,
                                        "assembly_count": len(data.get("Assemblies", [1]))
                                    },
                                    "created_at": data.get("Last Update (Time)", "")
                                })

                    except Exception:
                        pass

        # Sort active gates sequentially: BOM -> Sourcing -> Cycle Time -> Costing -> NPI -> WI
        stage_sort_order = {
            "bom": 1,
            "sourcing": 2,
            "cycle_time": 3,
            "costing": 4,
            "npi": 5,
            "wi": 6,
            "completed": 7
        }
        active_gates.sort(key=lambda g: (stage_sort_order.get(g.get("stage", "bom"), 99), str(g.get("rfq_id", ""))))

        return active_gates

    def get_pipeline_operations_summary(self, user_role: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
        """
        Scans all RFQs in the database and compiles the complete Daily Morning Operations Briefing:
        - actionable_rfqs: RFQs ready for sign-off & dispatch
        - in_progress_wip: RFQs currently being processed by engineers
        - completed_rfqs: Finished RFQs
        - kpi_counts: Snapshot metrics
        """
        if not self.bom_data_dir or not os.path.exists(self.bom_data_dir):
            return {"actionable": [], "wip": [], "completed": [], "kpi": {"ready": 0, "wip": 0, "completed": 0, "total": 0}}

        actionable = self.get_all_active_approval_gates(user_role=user_role, username=username)
        actionable_ids = {g.get("rfq_id") for g in actionable if g.get("rfq_id")}

        wip = []
        completed = []

        stage_names_map = {
            "pending_bom": "BOM Verification",
            "pending_sourcing_and_cycle_time": "Sourcing & Cycle Time",
            "pending_sourcing": "Sourcing",
            "pending_cycle_time": "Cycle Time",
            "pending_costing": "Costing",
            "pending_npi": "NPI Verification",
            "pending_wi": "Work Instruction",
            "completed": "Completed"
        }

        stage_sort_order = {
            "BOM Verification": 1,
            "Sourcing & Cycle Time": 2,
            "Sourcing": 2,
            "Cycle Time": 2,
            "Costing": 3,
            "NPI Verification": 4,
            "Work Instruction": 5,
            "Completed": 6
        }

        seen_wip = set()

        for root_dir, _, files in os.walk(self.bom_data_dir):
            for f in files:
                if f.lower().endswith(".json") and not f.lower().endswith("metadata.json"):
                    try:
                        fpath = os.path.join(root_dir, f)
                        with open(fpath, 'r', encoding='utf-8-sig') as jf:
                            data = json.load(jf)

                        rfq_id = data.get("RFQ") or os.path.splitext(f)[0]
                        customer = data.get("Customer") or os.path.basename(root_dir)
                        current_status = data.get("status", "pending_bom")
                        curr_stage_name = stage_names_map.get(current_status, current_status.replace("_", " ").title())

                        if current_status == "completed":
                            completed.append({
                                "rfq_id": rfq_id,
                                "customer": customer,
                                "stage": "Completed",
                                "pic": data.get("wi_assigned_by") or data.get("dispatched_by") or "Sysadmin"
                            })
                            continue

                        # If not already in actionable queue, it is Work-In-Progress (WIP)
                        if rfq_id not in actionable_ids and rfq_id not in seen_wip:
                            seen_wip.add(rfq_id)
                            pic = data.get(f"{current_status}_assigned_by") or data.get("dispatched_by") or data.get("bom_assigned_by") or "Ai Tink"

                            # Determine specific work status milestone
                            if current_status == "pending_bom":
                                milestone = "🟡 BOM Draft (Pending MOQ Assignment)"
                            elif current_status in ("pending_sourcing_and_cycle_time", "pending_sourcing", "pending_cycle_time"):
                                milestone = "🔵 In Sourcing & CT Analysis"
                            elif current_status == "pending_costing":
                                milestone = "🟣 In Quotation Calculation"
                            elif current_status == "pending_npi":
                                milestone = "🔬 In NPI Manufacturing Review"
                            elif current_status == "pending_wi":
                                milestone = "📋 In WI Authoring"
                            else:
                                milestone = "⏳ Work in Progress"

                            wip.append({
                                "rfq_id": rfq_id,
                                "customer": customer,
                                "stage": curr_stage_name,
                                "pic": pic,
                                "status_milestone": milestone,
                                "sort_order": stage_sort_order.get(curr_stage_name, 99)
                            })
                    except Exception:
                        pass

        # Sort WIP sequentially
        wip.sort(key=lambda w: (w.get("sort_order", 99), str(w.get("rfq_id", ""))))

        total_count = len(actionable) + len(wip) + len(completed)
        return {
            "actionable": actionable,
            "wip": wip,
            "completed": completed,
            "kpi": {
                "ready": len(actionable),
                "wip": len(wip),
                "completed": len(completed),
                "total": total_count
            }
        }
