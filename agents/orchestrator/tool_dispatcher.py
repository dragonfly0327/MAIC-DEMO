import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from .workflow_state import WorkflowStateManager, WorkflowStage, WorkflowStatus

class MicroserviceToolDispatcher:
    """
    Exposes controlled callable tools wrapping existing microservice functions.
    Preserves existing email notifications, audit trails, and status transitions.
    """
    def __init__(self, state_manager: Optional[WorkflowStateManager] = None):
        self.state_manager = state_manager or WorkflowStateManager()
        self.base_dir = self.state_manager.base_dir
        self._ensure_pm_in_path()

    def _ensure_pm_in_path(self):
        pm_path = os.path.normpath(os.path.join(self.base_dir, "ref", "Project Management"))
        if os.path.exists(pm_path) and pm_path not in sys.path:
            sys.path.append(pm_path)

    def dispatch_bom_to_sourcing_and_ct(self, rfq_id: str, parent_window=None, username: str = "Admin", comments: str = "") -> Tuple[bool, str]:
        """
        Executes BOM dispatch workflow:
        1. Opens EmailComposerDialog for human review/custom message if parent_window provided.
        2. Sends SMTP dispatch email to Sourcing & Cycle Time teams.
        3. Sets status to 'pending_sourcing_and_cycle_time'.
        4. Appends timestamped audit trail to history.
        5. Updates assigned_moqs_metadata.json and backlog log.
        """
        state = self.state_manager.get_rfq_state(rfq_id)
        if not state.get("exists"):
            return False, f"RFQ '{rfq_id}' not found in BOM database."

        raw_data = state["raw_data"]
        filepath = state["filepath"]
        cust_name = state["customer"]

        try:
            self._ensure_pm_in_path()
            from revert_workflow import (
                get_user_directory, get_user_email, get_system_pics,
                send_dispatch_email, EmailComposerDialog
            )
            
            user_dir = get_user_directory()
            available_recipients = {n: info["email"].strip() for n, info in user_dir.items() if info.get("email")}
            sender_email = get_user_email(username)
            agent_sender_name = f"ContinuumX AI Agent ({username})" if username and username != "Admin" else "ContinuumX AI Agent"

            # Resolve default To and CC PICs from system_pics.json
            pics_config = get_system_pics("pending_sourcing_and_cycle_time")
            target_to_names = pics_config.get("to", [])
            target_cc_names = pics_config.get("cc", [])
            
            target_to_emails = [available_recipients.get(n, get_user_email(n)) for n in target_to_names]
            target_cc_emails = [available_recipients.get(n, get_user_email(n)) for n in target_cc_names]
            
            # Ensure current user is CC'd so both next department and current user receive notification
            if sender_email and sender_email not in target_cc_emails:
                target_cc_emails.append(sender_email)

            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            subject = f"[ContinuumX] RFQ Dispatch Notification - RFQ {rfq_id} ({cust_name}) - BOM Verification Completed"

            body_template = f"""Dear {{recipient}},

The BOM Verification and target price assignation has been successfully completed and dispatched for the following RFQ:

--------------------------------------------------
RFQ Number:     {rfq_id}
Customer:       {cust_name}
From Stage:     BOM Verification
Sent To Stage:  Sourcing & Cycle Time
Dispatched By:  {agent_sender_name}
Dispatched At:  {now_str}
--------------------------------------------------

Comments / Message:
{{comments}}

Please review the status and proceed with Sourcing and Cycle Time assignments.
"""

            to_emails = target_to_emails
            cc_emails = target_cc_emails
            custom_comments = comments
            custom_subject = subject

            # Open interactive system email composer window if parent_window is provided
            if parent_window:
                composer = EmailComposerDialog(
                    parent_window,
                    sender_name=agent_sender_name,
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
                    return False, "Dispatch cancelled by user (Email draft closed)."

                res = composer.result
                to_emails = res.get("to_emails", target_to_emails)
                cc_emails = res.get("cc_emails", target_cc_emails)
                custom_comments = res.get("comments", "")
                custom_subject = res.get("subject", subject)

            send_dispatch_email(
                recipients=to_emails if to_emails else target_to_emails,
                rfq_id=rfq_id,
                customer=cust_name,
                from_stage="BOM Verification",
                to_stage="Sourcing & Cycle Time",
                comments=custom_comments or "BOM verification completed and dispatched via ContinuumX Brain.",
                dispatched_by=agent_sender_name,
                cc_recipients=cc_emails,
                subject=custom_subject
            )

            # Update JSON status
            raw_data["status"] = "pending_sourcing_and_cycle_time"
            raw_data["sourcing_status"] = "pending"
            raw_data["cycle_time_status"] = "pending"
            raw_data["bom_dispatched_by"] = agent_sender_name

            if "history" not in raw_data or not isinstance(raw_data["history"], list):
                raw_data["history"] = []

            now = datetime.now()
            raw_data["history"].append({
                "Date": now.strftime("%d.%m.%Y"),
                "Time": now.strftime("%H:%M:%S"),
                "Changed By": agent_sender_name,
                "stage": "pending_bom",
                "Field Name": "Stage Dispatch",
                "Old Value": "pending_bom",
                "New Value": "pending_sourcing_and_cycle_time"
            })

            # Save updated file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, indent=4)

            # Update metadata & backlog
            try:
                ameta_path = os.path.join(self.state_manager.bom_data_dir, "assigned_moqs_metadata.json")
                if os.path.exists(ameta_path):
                    with open(ameta_path, 'r', encoding='utf-8') as f:
                        ameta = json.load(f)
                    if not any(x.get("RFQ") == rfq_id for x in ameta.get("completed_moqs", [])):
                        ameta.get("completed_moqs", []).append({
                            "Customer": cust_name,
                            "RFQ": rfq_id,
                            "Timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                            "AssignedBy": agent_sender_name
                        })
                        with open(ameta_path, 'w', encoding='utf-8') as f:
                            json.dump(ameta, f, indent=4)
            except Exception:
                pass

            # Update orchestration state
            self.state_manager.clear_approval_checkpoint(rfq_id, approved_by=agent_sender_name)
            return True, f"RFQ '{rfq_id}' successfully dispatched to Sourcing & Cycle Time."

        except Exception as e:
            return False, f"Failed to dispatch BOM for RFQ '{rfq_id}': {e}"

    def dispatch_sourcing_to_costing(self, rfq_id: str, parent_window=None, username: str = "Admin", comments: str = "") -> Tuple[bool, str]:
        """
        Executes Sourcing dispatch logic:
        1. Opens EmailComposerDialog for human review/custom message if parent_window provided.
        2. Sends SMTP dispatch email to Costing team.
        3. Sets status to 'pending_costing' and sourcing_status to 'completed'.
        4. Appends audit trail to history.
        """
        state = self.state_manager.get_rfq_state(rfq_id)
        if not state.get("exists"):
            return False, f"RFQ '{rfq_id}' not found."

        raw_data = state["raw_data"]
        filepath = state["filepath"]
        cust_name = state["customer"]

        try:
            self._ensure_pm_in_path()
            from revert_workflow import (
                get_user_directory, get_user_email, get_system_pics,
                send_dispatch_email, EmailComposerDialog
            )
            
            user_dir = get_user_directory()
            available_recipients = {n: info["email"].strip() for n, info in user_dir.items() if info.get("email")}
            sender_email = get_user_email(username)
            agent_sender_name = f"ContinuumX AI Agent ({username})" if username and username != "Admin" else "ContinuumX AI Agent"

            to_pics_config = get_system_pics("pending_costing")
            target_to_names = to_pics_config.get("to", [])
            target_to_emails = [available_recipients.get(n, get_user_email(n)) for n in target_to_names]
            
            cc_pics_config = get_system_pics("pending_cycle_time")
            _cc_names = cc_pics_config.get("to", []) + cc_pics_config.get("cc", [])
            target_cc_emails = [available_recipients.get(n, get_user_email(n)) for n in _cc_names if available_recipients.get(n, get_user_email(n))]
            if sender_email and sender_email not in target_cc_emails:
                target_cc_emails.append(sender_email)

            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            subject = f"[ContinuumX] RFQ Dispatch Notification — RFQ {rfq_id} ({cust_name}) — Sourcing Completed"

            body_template = f"""Dear {{recipient}},

Sourcing and Cycle Time results have been successfully completed and dispatched for the following RFQ:

--------------------------------------------------
RFQ Number:     {rfq_id}
Customer:       {cust_name}
From Stage:     Sourcing Operations
Sent To Stage:  Costing
Dispatched By:  {agent_sender_name}
Dispatched At:  {now_str}
--------------------------------------------------

Comments / Message:
{{comments}}

Please review the status and proceed with the costing layout design.
"""

            to_emails = target_to_emails
            cc_emails = target_cc_emails
            custom_comments = comments
            custom_subject = subject

            if parent_window:
                composer = EmailComposerDialog(
                    parent_window,
                    sender_name=agent_sender_name,
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
                    return False, "Dispatch cancelled by user (Email draft closed)."

                res = composer.result
                to_emails = res.get("to_emails", target_to_emails)
                cc_emails = res.get("cc_emails", target_cc_emails)
                custom_comments = res.get("comments", "")
                custom_subject = res.get("subject", subject)

            send_dispatch_email(
                recipients=to_emails if to_emails else target_to_emails,
                rfq_id=rfq_id,
                customer=cust_name,
                from_stage="Sourcing Operations",
                to_stage="Costing",
                comments=custom_comments or "Sourcing results completed and dispatched to Costing via Brain.",
                dispatched_by=agent_sender_name,
                cc_recipients=cc_emails,
                subject=custom_subject
            )

            raw_data["status"] = "pending_costing"
            raw_data["sourcing_status"] = "completed"
            raw_data["sourcing_dispatched_by"] = agent_sender_name

            if "history" not in raw_data or not isinstance(raw_data["history"], list):
                raw_data["history"] = []

            now = datetime.now()
            raw_data["history"].append({
                "Date": now.strftime("%d.%m.%Y"),
                "Time": now.strftime("%H:%M:%S"),
                "Changed By": agent_sender_name,
                "stage": "pending_sourcing",
                "Field Name": "Stage Dispatch",
                "Old Value": "pending_sourcing",
                "New Value": "pending_costing"
            })

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, indent=4)

            self.state_manager.clear_approval_checkpoint(rfq_id, approved_by=username)
            return True, f"RFQ '{rfq_id}' successfully dispatched to Costing."

        except Exception as e:
            return False, f"Failed to dispatch Sourcing for RFQ '{rfq_id}': {e}"

    def dispatch_costing_to_npi(self, rfq_id: str, parent_window=None, username: str = "Admin", comments: str = "") -> Tuple[bool, str]:
        """Executes Costing dispatch to NPI stage with optional email composer window."""
        state = self.state_manager.get_rfq_state(rfq_id)
        if not state.get("exists"):
            return False, f"RFQ '{rfq_id}' not found."

        raw_data = state["raw_data"]
        filepath = state["filepath"]
        cust_name = state["customer"]

        try:
            self._ensure_pm_in_path()
            from revert_workflow import get_user_directory, get_user_email, get_system_pics, send_dispatch_email, EmailComposerDialog

            to_pics_config = get_system_pics("pending_npi")
            target_to_names = to_pics_config.get("to", [])
            user_dir = get_user_directory()
            available_recipients = {n: info["email"].strip() for n, info in user_dir.items() if info.get("email")}
            target_to_emails = [available_recipients.get(n, get_user_email(n)) for n in target_to_names]
            sender_email = get_user_email(username)
            agent_sender_name = f"ContinuumX AI Agent ({username})" if username and username != "Admin" else "ContinuumX AI Agent"

            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            subject = f"[ContinuumX] RFQ Dispatch Notification — RFQ {rfq_id} ({cust_name}) — Costing Completed"

            body_template = f"""Dear {{recipient}},

Costing calculation and quotation layout have been finalized for the following RFQ:

--------------------------------------------------
RFQ Number:     {rfq_id}
Customer:       {cust_name}
From Stage:     Costing
Sent To Stage:  NPI Gateway
Dispatched By:  {agent_sender_name}
Dispatched At:  {now_str}
--------------------------------------------------

Comments / Message:
{{comments}}

Please proceed with NPI Gateway validation and RPN classification.
"""

            to_emails = target_to_emails
            cc_emails = [sender_email] if sender_email else []
            custom_comments = comments
            custom_subject = subject

            if parent_window:
                composer = EmailComposerDialog(
                    parent_window,
                    sender_name=agent_sender_name,
                    sender_email=sender_email,
                    recipient_name=target_to_names,
                    recipient_email=target_to_emails,
                    subject=subject,
                    body_template=body_template,
                    default_cc=cc_emails,
                    available_recipients=available_recipients
                )
                parent_window.wait_window(composer)

                if not composer.result:
                    return False, "Dispatch cancelled by user (Email draft closed)."

                res = composer.result
                to_emails = res.get("to_emails", target_to_emails)
                cc_emails = res.get("cc_emails", cc_emails)
                custom_comments = res.get("comments", "")
                custom_subject = res.get("subject", subject)

            send_dispatch_email(
                recipients=to_emails if to_emails else target_to_emails,
                rfq_id=rfq_id,
                customer=cust_name,
                from_stage="Costing",
                to_stage="NPI Gateway",
                comments=custom_comments or "Costing finalized and dispatched to NPI.",
                dispatched_by=agent_sender_name,
                cc_recipients=cc_emails,
                subject=custom_subject
            )

            raw_data["status"] = "pending_npi"
            raw_data["costing_dispatched_by"] = agent_sender_name

            if "history" not in raw_data or not isinstance(raw_data["history"], list):
                raw_data["history"] = []

            now = datetime.now()
            raw_data["history"].append({
                "Date": now.strftime("%d.%m.%Y"),
                "Time": now.strftime("%H:%M:%S"),
                "Changed By": agent_sender_name,
                "stage": "pending_costing",
                "Field Name": "Stage Dispatch",
                "Old Value": "pending_costing",
                "New Value": "pending_npi"
            })

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, indent=4)

            self.state_manager.clear_approval_checkpoint(rfq_id, approved_by=agent_sender_name)
            return True, f"RFQ '{rfq_id}' successfully dispatched to NPI."
        except Exception as e:
            return False, f"Failed to dispatch Costing: {e}"
