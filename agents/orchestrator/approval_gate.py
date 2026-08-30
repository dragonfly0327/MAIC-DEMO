from typing import Dict, Any, List, Optional
from .workflow_state import WorkflowStateManager, WorkflowStage, WorkflowStatus

class ApprovalCheckpoint:
    CHECKPOINT_1_RFQ_EXTRACTION = "CHECKPOINT_1_RFQ_EXTRACTION"
    CHECKPOINT_2_BOM_COMPLETED = "CHECKPOINT_2_BOM_COMPLETED"
    CHECKPOINT_3_SOURCING_COMPLETED = "CHECKPOINT_3_SOURCING_COMPLETED"
    CHECKPOINT_4_CYCLE_TIME_PROPOSAL = "CHECKPOINT_4_CYCLE_TIME_PROPOSAL"
    CHECKPOINT_5_COSTING_COMPLETED = "CHECKPOINT_5_COSTING_COMPLETED"
    CHECKPOINT_6_WI_FINAL_REVIEW = "CHECKPOINT_6_WI_FINAL_REVIEW"

class ApprovalGateManager:
    """
    Manages human-in-the-loop review checkpoints.
    Halts automated execution, generates visual review cards for the Chatbot,
    and resumes execution once the human approves or edits the data.
    """
    def __init__(self, state_manager: Optional[WorkflowStateManager] = None):
        self.state_manager = state_manager or WorkflowStateManager()

    def create_gate(self, rfq_id: str, checkpoint: str, stage: str, summary_data: Dict[str, Any], customer: Optional[str] = None) -> Dict[str, Any]:
        """Halts the workflow and sets the persistent checkpoint."""
        self.state_manager.set_approval_checkpoint(rfq_id, checkpoint, stage, summary_data, customer)
        gate_info = {
            "rfq_id": rfq_id,
            "customer": customer or summary_data.get("customer", ""),
            "checkpoint": checkpoint,
            "stage": stage,
            "summary": summary_data,
            "status": WorkflowStatus.WAITING_FOR_HUMAN_APPROVAL
        }
        return gate_info

    def render_approval_card(self, gate_info: Dict[str, Any]) -> str:
        """Renders rich, structured Markdown text for the review card."""
        rfq_id = gate_info.get("rfq_id", "N/A")
        cust = gate_info.get("customer") or gate_info.get("summary", {}).get("customer", "N/A")
        checkpoint = gate_info.get("checkpoint", "")
        summary = gate_info.get("summary", {})

        if checkpoint == ApprovalCheckpoint.CHECKPOINT_1_RFQ_EXTRACTION:
            title = f"🛑 HUMAN REVIEW REQUIRED — RFQ Extraction ({rfq_id})"
            body = (
                f"• Customer: {cust}\n"
                f"• Commodity: {summary.get('commodity', 'N/A')}\n"
                f"• Project Title: {summary.get('project_title', 'N/A')}\n"
                f"• Target Price: {summary.get('target_price', 'Not Specified')}\n"
                f"• EAU: {summary.get('eau', 'Not Specified')}\n"
                f"• Default MOQs: {summary.get('default_moqs', 'Standard')}\n"
                f"• Custom MOQs: {summary.get('custom_moqs', 'None')}\n\n"
                f"Please review the extracted parameters above before launching BOM Verification."
            )
        elif checkpoint == ApprovalCheckpoint.CHECKPOINT_2_BOM_COMPLETED:
            title = f"🛑 HUMAN APPROVAL GATE — BOM Verification Completed ({rfq_id})"
            body = (
                f"• Customer: {cust}\n"
                f"• Total Assemblies: {summary.get('assembly_count', len(summary.get('assemblies', [])))}\n"
                f"• Assigned MOQs: {summary.get('assigned_moqs', 'Standard / Default')}\n"
                f"• Ready for Next Stage: Sourcing & Cycle Time (Parallel Execution)\n\n"
                f"Would you like to dispatch this RFQ to Sourcing & Cycle Time now?"
            )
        elif checkpoint == ApprovalCheckpoint.CHECKPOINT_3_SOURCING_COMPLETED:
            title = f"🛑 HUMAN APPROVAL GATE — Sourcing Results Completed ({rfq_id})"
            body = (
                f"• Customer: {cust}\n"
                f"• Winning Supplier: {summary.get('winning_supplier', 'Selected Suppliers')}\n"
                f"• Total Sourced Cost: {summary.get('total_sourcing_cost', 'Calculated')}\n"
                f"• Sourced Assemblies: {summary.get('assemblies_sourced', 'All (100%)')}\n\n"
                f"Would you like to approve and dispatch Sourcing results to Costing?"
            )
        elif checkpoint == ApprovalCheckpoint.CHECKPOINT_4_CYCLE_TIME_PROPOSAL:
            title = f"🛑 HUMAN VERIFICATION GATE — Cycle Time AI Drawing Analysis ({rfq_id})"
            features = summary.get("features", {})
            body = (
                f"• Drawing / Part: {summary.get('drawing_name', 'Drawing Attached')}\n"
                f"• Assembly Code: {features.get('assembly_code', 'A01')}\n"
                f"• Wire Spec: {features.get('wire_size', '24 AWG')} | Length: {features.get('wire_length', '350 mm')}\n"
                f"• Circuit Count: {features.get('circuit_count', '8')}\n"
                f"• Connector / Terminal: {features.get('connector', 'Standard')} / {features.get('terminal', 'Standard')}\n"
                f"• AI Confidence: {summary.get('confidence', 'High (95%)')}\n\n"
                f"Click 'Confirm' to save this into Cycle Time data or 'Edit' to adjust parameters."
            )
        elif checkpoint == ApprovalCheckpoint.CHECKPOINT_5_COSTING_COMPLETED:
            title = f"🛑 HUMAN APPROVAL GATE — Costing & Quotation Review ({rfq_id})"
            body = (
                f"• Customer: {cust}\n"
                f"• Final Unit Price: {summary.get('final_unit_price', 'Calculated')}\n"
                f"• Excess Material Cost: {summary.get('excess_cost', 'RM 0.00')}\n"
                f"• Target Price Margin: {summary.get('margin_status', 'Within Target')}\n\n"
                f"Would you like to approve the Costing summary and dispatch to NPI?"
            )
        elif checkpoint == ApprovalCheckpoint.CHECKPOINT_6_WI_FINAL_REVIEW:
            title = f"🛑 HUMAN FINAL REVIEW — Work Instruction Release ({rfq_id})"
            body = (
                f"• Customer: {cust}\n"
                f"• Document: {summary.get('wi_doc_name', 'Work Instruction Package')}\n"
                f"• Process Sequence & Visuals: Generated & Formatted\n\n"
                f"Please perform final verification before releasing the Work Instruction."
            )
        else:
            title = f"🛑 HUMAN APPROVAL GATE ({rfq_id})"
            body = f"• Stage: {gate_info.get('stage', 'N/A')}\n• Details: {summary}\n\nPlease confirm to continue."

        return f"{title}\n\n{body}"

    def get_consolidated_queue_table_data(self, gates_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Returns structured data for rendering a native styled GUI table in chat."""
        headers = ["#", "RFQ ID", "Customer Name", "Current Stage", "Assigned MOQs", "TP & EAU Status", "Next Stage Action", "Stage PIC"]
        rows = []
        for idx, g in enumerate(gates_list, start=1):
            rfq_id = g.get("rfq_id", "N/A")
            cust = g.get("customer") or g.get("summary", {}).get("customer", "N/A")
            summary = g.get("summary", {})
            curr_stage = g.get("current_stage") or summary.get("current_stage") or "BOM Verification"
            moqs = summary.get("assigned_moqs") or summary.get("default_moqs") or "Standard / Default"
            if isinstance(moqs, list):
                moq_str = ", ".join(str(m) for m in moqs)
            else:
                moq_str = str(moqs)

            # TP & EAU Status for BOM items
            raw_stg = g.get("stage", "")
            if raw_stg == "bom" or "BOM" in curr_stage:
                tp_st = g.get("tp_status") or summary.get("tp_status") or "Pending"
                eau_st = g.get("eau_status") or summary.get("eau_status") or "Pending"
                tp_eau_str = f"TP: {tp_st} | EAU: {eau_st}"
            else:
                tp_eau_str = "-"

            next_action = g.get("next_action") or "Sourcing & Cycle Time"
            pic = g.get("pic") or "Ai Tink"

            rows.append([
                str(idx),
                str(rfq_id),
                str(cust),
                str(curr_stage),
                str(moq_str),
                str(tp_eau_str),
                str(next_action),
                str(pic)
            ])

        return {
            "title": f"📋 Section 1: Ready to Sign-Off ({len(gates_list)} Actionable RFQs Waiting for Dispatch):",
            "headers": headers,
            "rows": rows,
            "footer": "💡 Choose a batch action or open the guided 1-by-1 review window below:"
        }

    def get_wip_pipeline_table_data(self, wip_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Returns structured data for rendering the Work-In-Progress pipeline table in chat."""
        headers = ["#", "RFQ ID", "Customer Name", "Current Stage", "Current Work Status / Milestone", "Stage PIC"]
        rows = []
        for idx, w in enumerate(wip_list, start=1):
            rows.append([
                str(idx),
                str(w.get("rfq_id", "N/A")),
                str(w.get("customer", "N/A")),
                str(w.get("stage", "N/A")),
                str(w.get("status_milestone", "In Progress")),
                str(w.get("pic", "Ai Tink"))
            ])
        return {
            "title": f"⏳ Section 2: Work-In-Progress (WIP) Pipeline Tracker ({len(wip_list)} Active RFQs):",
            "headers": headers,
            "rows": rows,
            "footer": "💡 To continue action on any RFQ above, launch its corresponding module on the left menu (or click a quick launch chip below)."
        }

    def render_consolidated_queue_card(self, gates_list: List[Dict[str, Any]]) -> str:
        """Renders a structured fallback table text card for all pending approval gates."""
        if not gates_list:
            return "🎉 All clear! There are currently 0 pending approval checkpoints in your queue."

        count = len(gates_list)
        title = f"📋 **Pending Approval Queue ({count} RFQ{'s' if count > 1 else ''} Waiting for Sign-off):**\n"

        headers = ["#", "RFQ ID", "Customer Name", "Current Stage", "Assigned MOQs", "Next Stage Action"]
        rows = []
        for idx, g in enumerate(gates_list, start=1):
            rfq_id = g.get("rfq_id", "N/A")
            cust = g.get("customer") or g.get("summary", {}).get("customer", "N/A")
            summary = g.get("summary", {})
            curr_stage = g.get("current_stage") or summary.get("current_stage") or "BOM Verification"
            next_action = g.get("next_action") or "Sourcing & Cycle Time"
            moqs = summary.get("assigned_moqs") or summary.get("default_moqs") or "Standard"
            if isinstance(moqs, list):
                moq_str = ", ".join(str(m) for m in moqs)
            else:
                moq_str = str(moqs)

            rows.append([
                str(idx),
                str(rfq_id),
                str(cust),
                str(curr_stage),
                str(moq_str),
                str(next_action)
            ])

        # Compute dynamic column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(val))

        sep_line = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
        header_row = "| " + " | ".join(f"{headers[i]:<{col_widths[i]}}" for i in range(len(headers))) + " |"

        table_lines = [sep_line, header_row, sep_line]
        for row in rows:
            table_lines.append("| " + " | ".join(f"{row[i]:<{col_widths[i]}}" for i in range(len(row))) + " |")
        table_lines.append(sep_line)

        table_str = "\n".join(table_lines)
        footer = "\n💡 *Choose a batch action or open the guided 1-by-1 review window below:*"

        return f"{title}```\n{table_str}\n```\n{footer}"

    def get_consolidated_queue_actions(self, count: int) -> List[str]:
        """Returns action suggestion chips for the consolidated approval queue."""
        return [
            "🔍 Open Guided Review Queue",
            f"🚀 Dispatch All ({count} RFQs)",
            "📋 View Approval Queue Summary"
        ]

    def get_approval_actions(self, checkpoint: str, rfq_id: str) -> List[str]:
        """Returns tailored Copilot suggestion chips for the active gate."""
        if checkpoint == ApprovalCheckpoint.CHECKPOINT_1_RFQ_EXTRACTION:
            return [
                "🚀 Launch BOM Verification",
                "✏️ Edit Parameters",
                "❌ Cancel Import"
            ]
        elif checkpoint == ApprovalCheckpoint.CHECKPOINT_2_BOM_COMPLETED:
            return [
                f"🚀 Dispatch RFQ {rfq_id} to Sourcing",
                f"⏱️ Start Cycle Time Analysis for {rfq_id}",
                f"🔍 Review BOM Details for {rfq_id}",
                f"↩️ Revert RFQ {rfq_id}"
            ]
        elif checkpoint == ApprovalCheckpoint.CHECKPOINT_3_SOURCING_COMPLETED:
            return [
                f"🚀 Dispatch RFQ {rfq_id} to Costing",
                f"📊 Review Sourcing Summary for {rfq_id}",
                f"↩️ Revert RFQ {rfq_id} to BOM"
            ]
        elif checkpoint == ApprovalCheckpoint.CHECKPOINT_4_CYCLE_TIME_PROPOSAL:
            return [
                f"✅ Confirm Cycle Time Data for {rfq_id}",
                f"✏️ Edit Cycle Time Values for {rfq_id}",
                f"📄 Review Drawing for {rfq_id}"
            ]
        elif checkpoint == ApprovalCheckpoint.CHECKPOINT_5_COSTING_COMPLETED:
            return [
                f"🚀 Dispatch RFQ {rfq_id} to NPI",
                f"📊 View Costing Breakdown for {rfq_id}",
                f"↩️ Revert RFQ {rfq_id} to Sourcing"
            ]
        elif checkpoint == ApprovalCheckpoint.CHECKPOINT_6_WI_FINAL_REVIEW:
            return [
                f"✅ Release Work Instruction for {rfq_id}",
                f"✏️ Modify Work Instruction for {rfq_id}",
                f"↩️ Revert to NPI"
            ]
        else:
            return [
                f"✅ Confirm & Continue for {rfq_id}",
                f"🔍 Review Details for {rfq_id}",
                f"↩️ Revert RFQ {rfq_id}"
            ]
