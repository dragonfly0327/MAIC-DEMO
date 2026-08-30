# ==============================================================================
# --- ContinuumX Autonomous Orchestrator Engine ---
# Coordinates engineering lifecycle using the Tool Registry & System State.
# DO NOT hardcode business logic; coordinates existing subsystem functions.
# ==============================================================================

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("ContinuumX.Orchestrator")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ContinuumXOrchestrator:
    """
    Central Coordinator managing 24/7 autonomous and human-in-the-loop workflows.
    """

    def __init__(self, username: str = "ContinuumX Agent"):
        self.username = username

    def get_status(self, rfq_id: str) -> Dict[str, Any]:
        """Queries the live workflow state for an RFQ."""
        from agents.workflow_state import WorkflowStateManager
        return WorkflowStateManager.get_rfq_workflow_state(rfq_id)

    def trigger_human_review_gate(self, rfq_id: str, dept: str) -> Tuple[bool, str]:
        """
        Prepares data, opens the existing review window, and registers an Approval Gate.
        """
        from agents.approval_manager import ApprovalManager, ApprovalGateType
        from agents.tool_registry import ContinuumXToolRegistry
        
        gate_map = {
            "bom": ApprovalGateType.WAITING_FOR_BOM_REVIEW,
            "sourcing": ApprovalGateType.WAITING_FOR_SOURCING_REVIEW,
            "cycle_time": ApprovalGateType.WAITING_FOR_CYCLE_TIME_REVIEW,
            "costing": ApprovalGateType.WAITING_FOR_COSTING_REVIEW,
            "costing_email": ApprovalGateType.WAITING_FOR_COSTING_EMAIL_APPROVAL
        }

        gate_type = gate_map.get(dept.lower())
        if not gate_type:
            return False, f"Unknown review department: {dept}"

        # Register non-blocking state gate
        ApprovalManager.register_gate(rfq_id, gate_type)
        logger.info(f"Registered UI Gate {gate_type.value} for RFQ '{rfq_id}'")

        # Emit launch signal for UI to open existing window
        local_appdata = os.environ.get('LOCALAPPDATA', os.environ.get('TEMP', 'C:\\Temp'))
        contxs_dir = os.path.join(local_appdata, "ContXs")
        os.makedirs(contxs_dir, exist_ok=True)
        
        cmd_file = os.path.join(contxs_dir, f"agent_open_{dept}_review.json")
        with open(cmd_file, "w", encoding="utf-8") as f:
            json.dump({"rfq_id": rfq_id, "action": f"open_{dept}_review"}, f)

        return True, f"Opened existing {dept.upper()} Review UI for RFQ '{rfq_id}'. Waiting for human sign-off."

    def run_autonomous_cycle(self, rfq_id: str) -> Dict[str, Any]:
        """
        Executes a single coordinated pass for an RFQ:
        1. Checks live state
        2. Resolves any completed human gates
        3. Executes any system-eligible dispatches
        4. Returns execution summary
        """
        from agents.workflow_state import WorkflowStateManager
        from agents.approval_manager import ApprovalManager
        from agents.tool_registry import ContinuumXToolRegistry

        logs = []
        state = WorkflowStateManager.get_rfq_workflow_state(rfq_id)

        if not state.get("exists"):
            return {"success": False, "error": state.get("error"), "logs": logs}

        # 1. Check Session Locks
        if state["is_locked"] and state["locked_by"] != self.username:
            msg = f"RFQ '{rfq_id}' is currently locked by human user: {state['locked_by']}. Yielding."
            logs.append(msg)
            return {"success": True, "status": "LOCKED", "message": msg, "state": state, "logs": logs}

        # 2. Check and resolve any active human approval gates
        if ApprovalManager.has_pending_gate(rfq_id):
            gate_resolved = ApprovalManager.check_and_resolve_gate(rfq_id)
            if gate_resolved:
                logs.append("Human review gate was satisfied in existing UI!")
                # Refresh state after gate resolution
                state = WorkflowStateManager.get_rfq_workflow_state(rfq_id)
            else:
                gate = ApprovalManager.get_pending_gate(rfq_id)
                msg = f"RFQ '{rfq_id}' is waiting for human review in existing UI ({gate.gate_type.value})."
                logs.append(msg)
                return {"success": True, "status": "WAITING_FOR_HUMAN", "message": msg, "state": state, "logs": logs}

        # 3. Check for System-Filtered Eligible Dispatches
        eligible_dispatches = state.get("system_eligible_dispatches", [])
        dispatched_any = False

        for dept in eligible_dispatches:
            success, msg = ContinuumXToolRegistry.execute_system_dispatch(
                dept=dept,
                rfq_id=rfq_id,
                username=self.username
            )
            logs.append(f"Dispatch [{dept}]: {msg}")
            if success:
                dispatched_any = True

        if dispatched_any:
            # Refresh state after dispatches
            state = WorkflowStateManager.get_rfq_workflow_state(rfq_id)

        # 4. Final summary
        return {
            "success": True,
            "rfq_id": rfq_id,
            "current_stage": state["current_stage"],
            "next_actions": state["next_available_actions"],
            "state": state,
            "logs": logs
        }
