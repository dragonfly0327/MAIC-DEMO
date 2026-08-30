from typing import Dict, Any, List, Optional
from .workflow_state import WorkflowStateManager, WorkflowStage, WorkflowStatus

class DependencyEvaluator:
    """
    Evaluates stage readiness and parallel execution eligibility based on
    actual system files and deterministic data dependencies.
    """
    def __init__(self, state_manager: Optional[WorkflowStateManager] = None):
        self.state_manager = state_manager or WorkflowStateManager()

    def evaluate_rfq(self, rfq_id: str, customer: Optional[str] = None) -> Dict[str, Any]:
        """Evaluates data readiness for all stages of an RFQ."""
        state = self.state_manager.get_rfq_state(rfq_id, customer)
        if not state.get("exists"):
            return {
                "exists": False,
                "rfq_id": rfq_id,
                "can_start_bom": True, # Can import new BOM
                "can_start_sourcing": False,
                "can_start_cycle_time": False,
                "can_start_costing": False,
                "can_start_npi": False,
                "can_start_wi": False,
                "parallel_workstreams": []
            }

        raw = state.get("raw_data", {})
        status = state.get("status", "pending_bom")
        src_status = state.get("sourcing_status", "pending")
        ct_status = state.get("cycle_time_status", "pending")
        assemblies = state.get("assemblies", [])
        has_moqs = bool(state.get("global_moqs") or any("Assigned MOQs" in a for a in assemblies))

        # 1. BOM Completion Check
        bom_completed = (status != "pending_bom") and bool(assemblies) and has_moqs

        # 2. Sourcing Readiness & Completion
        sourcing_ready = bom_completed and (src_status != "completed")
        sourcing_completed = (src_status == "completed") or (status in ["pending_costing", "pending_npi", "pending_wi", "completed"])

        # 3. Cycle Time Readiness & Completion (Independent / Parallel Workstream)
        cycle_time_ready = bom_completed and (ct_status != "completed")
        cycle_time_completed = (ct_status == "completed") or any(bool(a.get("cycle_time_data")) for a in assemblies)

        # 4. Costing Readiness & Completion
        # Rule: Costing is ready once Sourcing is completed, even if Cycle Time is not completed yet,
        # because the Costing module provides embedded Cycle Time data entry.
        costing_ready = sourcing_completed and (status == "pending_costing" or status == "pending_sourcing_and_cycle_time")
        costing_completed = status in ["pending_npi", "pending_wi", "completed"]

        # 5. NPI & WI Readiness
        npi_ready = costing_completed and (status == "pending_npi")
        npi_completed = status in ["pending_wi", "completed"]
        wi_ready = npi_completed and (status == "pending_wi")
        wi_completed = (status == "completed")

        # Determine Parallel Workstreams
        parallel_active = []
        if sourcing_ready:
            parallel_active.append(WorkflowStage.SOURCING)
        if cycle_time_ready:
            parallel_active.append(WorkflowStage.CYCLE_TIME)

        return {
            "exists": True,
            "rfq_id": rfq_id,
            "customer": state.get("customer", ""),
            "current_status": status,
            "bom_completed": bom_completed,
            "sourcing_ready": sourcing_ready,
            "sourcing_completed": sourcing_completed,
            "cycle_time_ready": cycle_time_ready,
            "cycle_time_completed": cycle_time_completed,
            "costing_ready": costing_ready,
            "costing_completed": costing_completed,
            "npi_ready": npi_ready,
            "npi_completed": npi_completed,
            "wi_ready": wi_ready,
            "wi_completed": wi_completed,
            "parallel_available": parallel_active,
            "is_parallel_sourcing_ct": (sourcing_ready and cycle_time_ready)
        }
