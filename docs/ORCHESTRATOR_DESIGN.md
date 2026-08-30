# ContinuumX Orchestrator Architecture & Tool Registry Design

## 1. Executive Summary & Core Architectural Principle

The **ContinuumX Agentic Platform** coordinates engineering workflows across the microservices:
`ref/BOM/`, `ref/Sourcing/`, `ref/Cycle Time/`, `ref/Costing/`, `ref/NPI/`, `ref/WI/`, and `ref/Project Management/`.

### The Fundamental Rule: Existing Systems are the Source of Truth
The ContinuumX Orchestrator does **NOT** recreate, replace, or duplicate existing business rules:
- **Dispatch**: The existing Dispatch Windows/filters determine which RFQs are eligible for dispatch. The Agent does NOT create artificial dispatch rules.
- **Revert**: The existing `request_revert()` function in `ref/Project Management/revert_workflow.py` is the single authoritative revert engine.
- **Calculations**: Sourcing winning MPNs (`SourcingEngine`), Cycle Time points (`CycleTimeModel`), and Quotations (`CostingModel`) are calculated by existing microservices.
- **Human Approval**: Human sign-off occurs inside the **Existing Subsystem UI Windows** (via existing buttons like `[ Confirm MOQs ]`, `[ Approve Calculations ]`, `[ Save ]`, `[ Save & Finish RFQ ]`). The Agent opens the UI window, stops and waits, and detects completion via existing system JSON state changes.

```
                      ┌────────────────────────────────────────┐
                      │          USER / CHATBOT BRAIN          │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │        CONTINUUMX ORCHESTRATOR         │
                      │         (agents/orchestrator.py)       │
                      └─────────┬───────────────────┬──────────┘
                                │                   │
                                ▼                   ▼
                      ┌───────────────────┐ ┌──────────────────┐
                      │   WORKFLOW STATE  │ │ APPROVAL MANAGER │
                      │ (workflow_state.py│ │(approval_manager)│
                      └─────────┬─────────┘ └────────┬─────────┘
                                │                    │
                                └─────────┬──────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │          AGENT TOOL REGISTRY           │
                      │       (agents/tool_registry.py)        │
                      └───────────────────┬────────────────────┘
                                          │
               ┌──────────────────────────┼──────────────────────────┐
               ▼                          ▼                          ▼
      ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
      │ ref/BOM/        │        │ ref/Sourcing/   │        │ ref/Costing/    │
      │ Existing Logic  │        │ Existing Logic  │        │ Existing Logic  │
      └─────────────────┘        └─────────────────┘        └─────────────────┘
```

---

## 2. Tool Classification & Permission Model

Every tool registered in `agents/tool_registry.py` is tagged with a permission tier:

### 1. `READ_ONLY` (Safe for continuous 24/7 background polling)
- **`bom.get_status`**: Ingests `{RFQ}.json`, returns stage, Customer, Global MOQs, and Assembly count.
- **`bom.get_data`**: Reads full verified BOM line items, components, and MPN mappings.
- **`sourcing.get_status`**: Reads `sourcing_status`, winning suppliers, and excess costs.
- **`sourcing.get_results`**: Returns calculated winning MPNs, prices, and MOQ excess details.
- **`cycle_time.get_status`**: Reads `cycle_time_status` and saved cycle times per assembly.
- **`costing.get_summary`**: Reads Gross Margin %, EAU revenue, unit prices from saved quotation.
- **`project.get_history`**: Reads timestamped audit trail and revert history.
- **`system.get_pics`**: Resolves stage PICs from `system_pics.json`.

### 2. `AUTOMATIC_ACTION` (Autonomous RPA background execution)
- **`bom.auto_verify`**: Reads raw Excel BOM, executes `DataLoader`, maps headers, sets Global MOQs, saves `{RFQ}.json`.
- **`sourcing.auto_calculate`**: Executes `SourcingEngine.process_all()` across all assemblies, saves results to disk.
- **`cycle_time.ai_extract_drawing`**: Extracts wire specs from drawing PDF/image, calculates cycle times, pre-fills process table.
- **`costing.auto_calculate_quotation`**: Merges Sourcing + CT data, runs `CostingModel.calculate_unit_price()`, writes draft quotation.

### 3. `HUMAN_APPROVAL` (Opens Subsystem UI Gate & Enters Waiting State)
- **`bom.open_review_window`**: Direct handshake loads target RFQ into `AssemblyMOQPanel` (Image 2).
- **`sourcing.open_review_window`**: Loads target RFQ into `SourcingUI` (Image 4).
- **`cycle_time.open_review_window`**: Loads target RFQ into `CycleTimeMaintenanceWindow` (Image 1) with pre-filled AI numbers.
- **`costing.open_review_window`**: Loads target RFQ into `DetailedCostingPage` (Image 3).
- **`costing.open_approval_composer`**: Opens executive `EmailComposerDialog` (Image 5).

### 4. `CONDITIONAL_AUTOMATIC_DISPATCH` (System-Filtered RPA Dispatch)
- **`bom.get_eligible_dispatches`** / **`bom.execute_system_dispatch`**: Reads eligible RFQs from `BOMDatabaseSearchPanel(is_dispatch=True)`. If target RFQ is in the system list, executes existing `dispatch_rfq_workflow()`.
- **`sourcing.get_eligible_dispatches`** / **`sourcing.execute_system_dispatch`**: Reads eligible RFQs from Sourcing dispatch query. If target RFQ is in the list, executes existing `dispatch_sourcing_workflow()`.
- **`cycle_time.get_eligible_dispatches`** / **`cycle_time.execute_system_dispatch`**: Reads eligible RFQs from `DispatchSelectionDialog`. If target RFQ is in the list, executes existing `open_dispatch_dialog()`.
- **`costing.get_eligible_dispatches`** / **`costing.execute_system_dispatch`**: Reads eligible RFQs from `CostingAnalysisWindow._load_dispatchable_rfqs()`. If target RFQ is in the list, executes existing `_open_dispatch_rfq()`.

### 5. `HIGH_RISK` (Requires Explicit Human Command)
- **`project.revert`**: Calls official `request_revert()`, sets `revert_pending`, restores BOM temporary session in `Temp/`, and sends SMTP revert notification email.

---

## 3. Workflow State Model (`agents/workflow_state.py`)

The Orchestrator asks:
```python
state = WorkflowStateManager.get_rfq_workflow_state("1009")
```
and receives dynamic, live data:

```json
{
    "rfq_id": "1009",
    "customer": "Radysis",
    "current_stage": "PENDING_SOURCING_AND_CYCLE_TIME",
    "is_locked": false,
    "locked_by": null,
    "bom": {
        "status": "completed",
        "global_moqs": [100, 200, 500, 1000],
        "assemblies_count": 2,
        "dispatched_by": "Sysadmin"
    },
    "sourcing": {
        "status": "completed",
        "calc_mode": "total_usage",
        "dispatched_by": null
    },
    "cycle_time": {
        "status": "pending",
        "has_ai_prefill": true
    },
    "costing": {
        "status": "not_started",
        "has_quotation": false
    },
    "revert_pending": null,
    "system_eligible_dispatches": ["sourcing"],
    "next_available_actions": [
        "cycle_time.open_review_window",
        "sourcing.execute_system_dispatch"
    ]
}
```

---

## 4. Human Approval Model (`agents/approval_manager.py`)

Human review occurs entirely inside the **Existing Subsystem UI**.

```text
Orchestrator initiates UI Gate
              ↓
Calls open_review_window() -> Subsystem UI pops up
              ↓
ApprovalManager registers: WAITING_FOR_SOURCING_REVIEW
              ↓
Orchestrator yields / waits (No chatbot typing required!)
              ↓
Human reviews cards & clicks [ Approve Calculations ] (btn_approve)
              ↓
Existing Subsystem UI executes on_approve():
Sets raw_data["sourcing_status"] = "completed"
              ↓
ApprovalManager detects: sourcing_status == "completed"
              ↓
Approval Gate CLEARED -> Orchestrator resumes workflow
```

### Supported Approval Gate States:
1. `WAITING_FOR_BOM_REVIEW`: Waits until `Global MOQs` is set and BOM is saved.
2. `WAITING_FOR_SOURCING_REVIEW`: Waits until `sourcing_status == "completed"`.
3. `WAITING_FOR_CYCLE_TIME_REVIEW`: Waits until `cycle_time_status == "completed"`.
4. `WAITING_FOR_COSTING_REVIEW`: Waits until quotation JSON is saved in `Saved Quotations/`.
5. `WAITING_FOR_COSTING_EMAIL_APPROVAL`: Waits until executive approval status is `"Approved"`.

---

## 5. Dispatch Model (System-Filtered Robotic Execution)

The Orchestrator does **NOT** enforce its own dispatch rules. It operates as an RPA user over the existing dispatch filters:

```text
Orchestrator checks for dispatch readiness
              ↓
Invokes get_eligible_dispatches() on existing subsystem
              ↓
Subsystem runs its existing search query:
  • BOM: BOMDatabaseSearchPanel(is_dispatch=True).bom_records
  • Sourcing: Existing Sourcing dispatch filter
  • Cycle Time: DispatchSelectionDialog.all_records
  • Costing: CostingAnalysisWindow._load_dispatchable_rfqs()
              ↓
Is target RFQ present in system's eligible records?
  ├─ NO  -> Cannot dispatch yet. Yield and continue other work.
  └─ YES -> Call existing dispatch function!
              ↓
Existing Dispatch Function runs:
  1. acquire_session_lock(rfq_id, username)
  2. get_system_pics(to_stage)
  3. send_dispatch_email(To, CC, Comments)
  4. atomic_write_json(filepath, updated_raw_data)
  5. release_session_lock(rfq_id, username)
```

---

## 6. Revert Model (Central Revert Engine Integration)

When a revert is requested:
1. Orchestrator calls `ToolRegistry.revert_project(...)`.
2. Direct invocation of `request_revert()` in `ref/Project Management/revert_workflow.py`.
3. `request_revert()` sets `revert_pending`, appends to `revert_history`, resets downstream flags (`sourcing_status="pending"`, `cycle_time_status="pending"`), and if reverting to `pending_bom`, reconstructs `BOM_Session_{uuid}.json` in `BOM/AppData/Temp/` so the BOM line items are immediately editable again!
4. Sends SMTP revert email via `send_revert_email()`.

---

## 7. Cycle Time AI Model

Cycle Time AI is an independent pipeline that pre-populates the existing UI:

```text
Drawing PDF / Image
        ↓
MarkItDown / Vision Ingestion
        ↓
LLM Extraction (Wire AWG, Strip Length, Terminal Part #s, Circuit Count)
        ↓
Deterministic Cycle Time Calculator (cutting, stripping, crimping, testing seconds)
        ↓
Pre-fill CycleTimeMaintenanceWindow (Image 1)
        ↓
Human reviews numbers & clicks [ Save ]
        ↓
Cycle Time Subsystem saves JSON & sets cycle_time_status = "completed"
```

---

## 8. Orchestrator Decision Loop

```python
class ContinuumXOrchestrator:
    def process_rfq(self, rfq_id: str, username: str = "ContinuumX Agent"):
        # 1. Inspect live workflow state
        state = WorkflowStateManager.get_rfq_workflow_state(rfq_id)
        
        # 2. Check if locked by another user
        if state["is_locked"]:
            return f"RFQ '{rfq_id}' is currently locked by {state['locked_by']}."

        # 3. Check for active human approval gate
        if ApprovalManager.has_pending_gate(rfq_id):
            is_resolved = ApprovalManager.check_and_resolve_gate(rfq_id)
            if not is_resolved:
                return f"RFQ '{rfq_id}' is waiting for human review in existing UI."

        # 4. Check if eligible for existing system dispatch
        eligible_dispatches = state["system_eligible_dispatches"]
        for dept in eligible_dispatches:
            # Execute existing dispatch function
            success, msg = ToolRegistry.execute_system_dispatch(dept, rfq_id, username)
            if success:
                logger.info(f"Auto-dispatched {dept} for {rfq_id}: {msg}")
                # Refresh state after dispatch
                state = WorkflowStateManager.get_rfq_workflow_state(rfq_id)

        # 5. Determine next available action
        next_actions = state["next_available_actions"]
        if next_actions:
            target_tool = next_actions[0]
            # Execute tool...
```

---

## 9. Error Handling & Session Lock Safety

1. **Session Locks**: Every modifying action validates `acquire_session_lock(rfq_id, username)`. If locked, the agent aborts and reports the lock owner.
2. **Atomic Writes**: Every status modification uses `atomic_write_json()` to eliminate partial write risks on network shares.
3. **No Direct Overwriting**: The Agent never sets JSON status keys directly; it always calls the existing subsystem handler.

---

## 10. End-to-End Example RFQ Lifecycle Trace

```text
1. Customer Email received with BOM Excel + Drawing PDF
   ↳ Agent calls bom.auto_verify() -> Saves BOM Data/Radysis/RFQ1009.json
   
2. Agent checks BOM dispatch eligibility:
   ↳ BOM requires MOQ sign-off -> Agent calls bom.open_review_window("1009")
   ↳ Image 2 pops up -> User clicks [ Confirm MOQs & Target Prices ]
   ↳ State changes -> Agent detects MOQ completed -> Calls bom.execute_system_dispatch()
   ↳ BOM Dispatched -> State becomes pending_sourcing_and_cycle_time
   
3. Parallel Execution: Sourcing & Cycle Time
   ↳ Sourcing: Agent runs sourcing.auto_calculate() -> Prepares calculations
   ↳ Sourcing: Agent calls sourcing.open_review_window() -> User clicks [ Approve Calculations ]
   ↳ Sourcing: sourcing_status = "completed" -> Agent calls sourcing.execute_system_dispatch()
   
   ↳ Cycle Time: Agent runs cycle_time.ai_extract_drawing() -> Pre-fills process table
   ↳ Cycle Time: Agent calls cycle_time.open_review_window() -> User clicks [ Save ]
   ↳ Cycle Time: cycle_time_status = "completed" -> Agent calls cycle_time.execute_system_dispatch()
   
4. Costing Subsystem
   ↳ Both Sourcing and CT dispatched -> State becomes pending_costing
   ↳ Agent calls costing.auto_calculate_quotation() -> Builds full quotation matrix
   ↳ Agent calls costing.open_review_window() -> User reviews Image 3 & clicks [ Save & Finish RFQ ]
   ↳ Agent calls costing.open_approval_composer() -> Image 5 pops up -> User sends approval email
   ↳ Executive approves -> Agent calls costing.execute_system_dispatch() -> Dispatches to NPI!
```
