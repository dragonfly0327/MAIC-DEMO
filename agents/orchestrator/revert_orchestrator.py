import os
import sys
from typing import Dict, Any, Optional, Tuple
from .workflow_state import WorkflowStateManager

class RevertOrchestrator:
    """
    Intelligent Revert Coordinator operating on existing Project Management logic.
    Analyzes upstream dependency chains and enforces required re-processing paths.
    """
    def __init__(self, state_manager: Optional[WorkflowStateManager] = None):
        self.state_manager = state_manager or WorkflowStateManager()
        self.base_dir = self.state_manager.base_dir
        self._ensure_pm_in_path()

    def _ensure_pm_in_path(self):
        pm_path = os.path.normpath(os.path.join(self.base_dir, "ref", "Project Management"))
        if os.path.exists(pm_path) and pm_path not in sys.path:
            sys.path.append(pm_path)

    def analyze_revert_impact(self, rfq_id: str, target_stage: str) -> Dict[str, Any]:
        """Calculates which downstream stages must be re-run following a revert."""
        state = self.state_manager.get_rfq_state(rfq_id)
        current_status = state.get("status", "pending_bom") if state.get("exists") else "unknown"

        impacted_stages = []
        if target_stage in ["pending_bom", "bom"]:
            impacted_stages = ["Sourcing Operations (Supplier re-quote required)", "Cycle Time Analysis (Features check)", "Costing & Margin Calculation"]
            effective_target = "pending_bom"
        elif target_stage in ["pending_sourcing", "pending_sourcing_and_cycle_time", "sourcing"]:
            impacted_stages = ["Costing & Margin Calculation", "Quotation Output"]
            effective_target = "pending_sourcing_and_cycle_time"
        elif target_stage in ["pending_costing", "costing"]:
            impacted_stages = ["NPI Turn-on", "Work Instruction Release"]
            effective_target = "pending_costing"
        else:
            effective_target = target_stage

        return {
            "rfq_id": rfq_id,
            "current_stage": current_status,
            "target_stage": effective_target,
            "impacted_downstream_stages": impacted_stages,
            "reprocessing_required": bool(impacted_stages)
        }

    def execute_revert(self, rfq_id: str, target_stage: str, reason: str = "", parent_window=None, requested_by: str = "Admin") -> Tuple[bool, str]:
        """
        Executes revert workflow:
        1. Analyzes impact.
        2. Opens EmailComposerDialog for human confirmation & comments if parent_window provided.
        3. Invokes request_revert() to update database and reset downstream stages.
        4. Sends official SMTP revert email notification.
        """
        state = self.state_manager.get_rfq_state(rfq_id)
        if not state.get("exists"):
            return False, f"RFQ '{rfq_id}' not found in database."

        customer = state.get("customer", "")
        current_status = state.get("status", "pending_bom")
        impact = self.analyze_revert_impact(rfq_id, target_stage)
        eff_target = impact["target_stage"]

        stage_names = {
            "pending_bom": "BOM Verification",
            "pending_sourcing_and_cycle_time": "Sourcing & Cycle Time",
            "pending_costing": "Costing",
            "pending_npi": "NPI Gateway",
            "pending_wi": "Work Instruction (WI)",
            "completed": "Completed Process"
        }
        from_stage_name = stage_names.get(current_status, current_status)
        to_stage_name = stage_names.get(eff_target, eff_target)

        try:
            self._ensure_pm_in_path()
            from revert_workflow import (
                request_revert, send_revert_email, EmailComposerDialog,
                get_user_directory, get_user_email, get_system_pics
            )

            user_dir = get_user_directory()
            available_recipients = {n: info["email"].strip() for n, info in user_dir.items() if info.get("email")}
            sender_email = get_user_email(requested_by)

            # Resolve default To and CC PICs for target stage
            to_pics_config = get_system_pics(eff_target)
            target_to_names = to_pics_config.get("to", [])
            target_to_emails = [available_recipients.get(n, get_user_email(n)) for n in target_to_names if available_recipients.get(n, get_user_email(n))]
            
            target_cc_names = to_pics_config.get("cc", [])
            target_cc_emails = [available_recipients.get(n, get_user_email(n)) for n in target_cc_names if available_recipients.get(n, get_user_email(n))]
            if sender_email and sender_email not in target_cc_emails:
                target_cc_emails.append(sender_email)

            subject = f"[ContinuumX] Revert Request — RFQ {rfq_id} ({customer}) — Return to {to_stage_name}"
            body_template = f"""Dear {{recipient}},

A workflow revert has been requested for RFQ: {rfq_id} (Customer: {customer}).

From Stage:         {from_stage_name}
Returned To Stage:  {to_stage_name}
Requested By:       {requested_by}

Comments / Reason for Revert:
{{comments}}

💡 Note on data continuity: All manually-entered quotes, supplier pairings, and pricing are preserved. You will be prompted to load them upon re-opening the RFQ in your module.
"""

            to_emails = target_to_emails
            cc_emails = target_cc_emails
            custom_comments = reason or f"Revert to {to_stage_name} requested via AI Brain Assistant."
            custom_subject = subject

            # Open interactive system email composer window if parent_window is provided
            if parent_window:
                composer = EmailComposerDialog(
                    parent_window,
                    sender_name=requested_by,
                    sender_email=sender_email,
                    recipient_name=target_to_names,
                    recipient_email=target_to_emails,
                    subject=subject,
                    body_template=body_template,
                    default_cc=target_cc_emails,
                    available_recipients=available_recipients
                )
                parent_window.wait_window(composer)

                if not composer.result:
                    return False, "Revert cancelled by user (Email draft closed)."

                res = composer.result
                to_emails = res.get("to_emails", target_to_emails)
                cc_emails = res.get("cc_emails", target_cc_emails)
                custom_comments = res.get("comments", "")
                custom_subject = res.get("subject", subject)

            # Execute Project Management Revert Logic
            success, msg = request_revert(
                rfq_id=rfq_id,
                customer=customer,
                target_stage=eff_target,
                reason=custom_comments,
                requested_by=requested_by,
                bom_data_dir=self.state_manager.bom_data_dir
            )

            if success:
                # Send SMTP revert notification email
                send_revert_email(
                    recipients=to_emails if to_emails else target_to_emails,
                    rfq_id=rfq_id,
                    customer=customer,
                    from_stage=current_status,
                    to_stage=eff_target,
                    reason=custom_comments,
                    requested_by=requested_by,
                    cc_recipients=cc_emails,
                    subject=custom_subject
                )

                self.state_manager.clear_approval_checkpoint(rfq_id, approved_by=requested_by)
                return True, f"RFQ '{rfq_id}' successfully reverted to '{to_stage_name}'.\n\n• Notification email sent to {', '.join(to_emails) if to_emails else 'team'}.\n• Affected stages requiring reprocessing: {', '.join(impact['impacted_downstream_stages'])}."
            else:
                return False, f"Revert failed: {msg}"
        except Exception as ex:
            return False, f"Error executing revert via Project Management: {ex}"
