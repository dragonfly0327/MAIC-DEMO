# ==============================================================================
# --- ContinuumX Approval Manager ---
# Observes existing subsystem JSON state changes to detect human UI sign-offs.
# Non-blocking, event-driven state checking without chatbot typing requirements.
# ==============================================================================

import os
import sys
import json
import logging
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("ContinuumX.ApprovalManager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ApprovalGateType(Enum):
    WAITING_FOR_BOM_REVIEW = "WAITING_FOR_BOM_REVIEW"
    WAITING_FOR_SOURCING_REVIEW = "WAITING_FOR_SOURCING_REVIEW"
    WAITING_FOR_CYCLE_TIME_REVIEW = "WAITING_FOR_CYCLE_TIME_REVIEW"
    WAITING_FOR_COSTING_REVIEW = "WAITING_FOR_COSTING_REVIEW"
    WAITING_FOR_COSTING_EMAIL_APPROVAL = "WAITING_FOR_COSTING_EMAIL_APPROVAL"


class ApprovalGateRecord:
    def __init__(self, rfq_id: str, gate_type: ApprovalGateType, timeout_seconds: int = 86400):
        self.rfq_id = rfq_id
        self.gate_type = gate_type
        self.created_at = datetime.now()
        self.timeout_seconds = timeout_seconds
        self.status = "PENDING" # "PENDING", "RESOLVED", "TIMEOUT", "CANCELLED"
        self.resolved_at = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rfq_id": self.rfq_id,
            "gate_type": self.gate_type.value,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": self.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if self.resolved_at else None
        }


class ApprovalManager:
    """
    Tracks and checks human review gates by reading actual subsystem JSON data.
    """
    _active_gates: Dict[str, ApprovalGateRecord] = {}

    @classmethod
    def register_gate(cls, rfq_id: str, gate_type: ApprovalGateType, timeout_seconds: int = 86400) -> ApprovalGateRecord:
        """Registers a waiting gate for an RFQ."""
        gate = ApprovalGateRecord(rfq_id=rfq_id, gate_type=gate_type, timeout_seconds=timeout_seconds)
        cls._active_gates[rfq_id] = gate
        logger.info(f"Registered approval gate: {gate_type.value} for RFQ '{rfq_id}'")
        return gate

    @classmethod
    def has_pending_gate(cls, rfq_id: str) -> bool:
        """Returns True if an RFQ is currently waiting for human review."""
        gate = cls._active_gates.get(rfq_id)
        return gate is not None and gate.status == "PENDING"

    @classmethod
    def get_pending_gate(cls, rfq_id: str) -> Optional[ApprovalGateRecord]:
        return cls._active_gates.get(rfq_id)

    @classmethod
    def clear_gate(cls, rfq_id: str):
        if rfq_id in cls._active_gates:
            del cls._active_gates[rfq_id]

    @classmethod
    def check_and_resolve_gate(cls, rfq_id: str) -> bool:
        """
        Inspects the live system data to check if the human has clicked the confirmation button.
        Returns True if the gate has been satisfied.
        """
        gate = cls._active_gates.get(rfq_id)
        if not gate or gate.status != "PENDING":
            return True

        from agents.workflow_state import WorkflowStateManager
        state = WorkflowStateManager.get_rfq_workflow_state(rfq_id)

        if not state.get("exists"):
            return False

        resolved = False

        if gate.gate_type == ApprovalGateType.WAITING_FOR_BOM_REVIEW:
            # Resolved if Global MOQs populated or status advanced past pending_bom
            if state["bom"]["status"] == "completed" or bool(state["bom"]["global_moqs"]):
                resolved = True

        elif gate.gate_type == ApprovalGateType.WAITING_FOR_SOURCING_REVIEW:
            # Resolved if sourcing_status is marked 'completed' or 'approved'
            if state["sourcing"]["is_completed"]:
                resolved = True

        elif gate.gate_type == ApprovalGateType.WAITING_FOR_CYCLE_TIME_REVIEW:
            # Resolved if cycle_time_status is marked 'completed' or 'approved'
            if state["cycle_time"]["is_completed"]:
                resolved = True

        elif gate.gate_type == ApprovalGateType.WAITING_FOR_COSTING_REVIEW:
            # Resolved if quotation JSON file is saved
            if state["costing"]["has_quotation"]:
                resolved = True

        elif gate.gate_type == ApprovalGateType.WAITING_FOR_COSTING_EMAIL_APPROVAL:
            # Resolved if quotation approval_status is 'Approved'
            if state["costing"].get("approval_status") == "Approved":
                resolved = True

        if resolved:
            gate.status = "RESOLVED"
            gate.resolved_at = datetime.now()
            logger.info(f"Human review gate {gate.gate_type.value} CLEARED for RFQ '{rfq_id}'!")
            return True

        return False
