# ==============================================================================
# --- ContinuumX Guided Approval Queue Workspace ---
# A unified, single-window stepper review interface for all pending RFQs.
# Prevents multi-window clutter and ensures zero forgotten approvals.
# ==============================================================================

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, Optional, Callable


class GuidedApprovalQueueWindow(tk.Toplevel):
    """
    Guided 1-by-1 Approval Queue Stepper Dialog.
    Allows reviewing and dispatching pending RFQs sequentially in a single window.
    """

    def __init__(
        self,
        master: tk.Widget,
        active_gates: List[Dict[str, Any]],
        server_path: str,
        username: str = "ContinuumX Agent",
        on_queue_updated: Optional[Callable[[List[Dict[str, Any]]], None]] = None
    ):
        super().__init__(master)
        self.title("ContinuumX — Guided Approval Queue Workspace")
        self.geometry("840x640")
        self.minsize(750, 550)
        self.configure(bg="#F8FAFC")
        
        self.all_gates = list(active_gates)
        self.gates = list(active_gates)
        self.current_idx = 0
        self.server_path = server_path
        self.username = username
        self.on_queue_updated = on_queue_updated
        self.stage_filter_var = tk.StringVar(value="All Stages")
        
        # Center on master
        self.update_idletasks()
        try:
            w = 840
            h = 640
            x = max(0, master.winfo_x() + (master.winfo_width() - w) // 2)
            y = max(0, master.winfo_y() + (master.winfo_height() - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        self._build_ui()
        self._update_stage_filter_options()
        self._render_current_item()

    def _update_stage_filter_options(self):
        stage_counts = {}
        for g in self.all_gates:
            stg = g.get("current_stage") or "BOM Verification"
            stage_counts[stg] = stage_counts.get(stg, 0) + 1

        stage_order_ref = [
            "BOM Verification",
            "Sourcing",
            "Cycle Time",
            "Costing",
            "NPI Verification",
            "Work Instruction",
            "Completed"
        ]
        opts = [f"🌐 All Stages ({len(self.all_gates)})"]
        for stg in stage_order_ref:
            if stg in stage_counts:
                opts.append(f"📁 {stg} ({stage_counts[stg]})")
        # Add any unlisted stages
        for stg, cnt in stage_counts.items():
            if stg not in stage_order_ref:
                opts.append(f"📁 {stg} ({cnt})")

        self.cmb_stage["values"] = opts
        if not self.stage_filter_var.get() or self.stage_filter_var.get() not in opts:
            self.stage_filter_var.set(opts[0] if opts else "🌐 All Stages (0)")

    def _on_stage_filter_change(self, event=None):
        val = self.stage_filter_var.get()
        if "All Stages" in val:
            self.gates = list(self.all_gates)
        else:
            # Extract stage name from format "📁 <Stage> (<Count>)"
            stage_clean = val.replace("📁 ", "").split(" (")[0].strip()
            self.gates = [g for g in self.all_gates if (g.get("current_stage") or "").strip() == stage_clean]

        self.current_idx = 0
        self._render_current_item()

    def _build_ui(self):
        # 1. Top Header Banner
        header = tk.Frame(self, bg="#1E293B", height=65)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🛡️ Guided Approval & Dispatch Queue",
            font=("Segoe UI", 13, "bold"),
            fg="#FFFFFF",
            bg="#1E293B"
        ).pack(side="left", padx=20, pady=12)

        self.lbl_counter = tk.Label(
            header,
            text="",
            font=("Segoe UI", 10, "bold"),
            fg="#38BDF8",
            bg="#1E293B"
        )
        self.lbl_counter.pack(side="right", padx=20, pady=12)

        # 2. Stepper Navigation & Stage Filter Bar
        nav_bar = tk.Frame(self, bg="#E2E8F0", height=45)
        nav_bar.pack(fill="x", side="top")
        nav_bar.pack_propagate(False)

        self.btn_prev = tk.Button(
            nav_bar,
            text="◀ Previous",
            font=("Segoe UI", 9, "bold"),
            bg="#FFFFFF",
            fg="#1E293B",
            relief="flat",
            bd=1,
            cursor="hand2",
            command=self._prev_item
        )
        self.btn_prev.pack(side="left", padx=15, pady=8)

        self.lbl_stepper_info = tk.Label(
            nav_bar,
            text="",
            font=("Segoe UI", 10, "bold"),
            fg="#0F172A",
            bg="#E2E8F0"
        )
        self.lbl_stepper_info.pack(side="left", padx=10)

        # Filter Stage Combobox
        filter_f = tk.Frame(nav_bar, bg="#E2E8F0")
        filter_f.pack(side="right", padx=15, pady=8)

        self.btn_next = tk.Button(
            filter_f,
            text="Next ▶",
            font=("Segoe UI", 9, "bold"),
            bg="#FFFFFF",
            fg="#1E293B",
            relief="flat",
            bd=1,
            cursor="hand2",
            command=self._next_item
        )
        self.btn_next.pack(side="right", padx=(10, 0))

        from tkinter import ttk
        self.cmb_stage = ttk.Combobox(
            filter_f,
            textvariable=self.stage_filter_var,
            state="readonly",
            font=("Segoe UI", 9),
            width=22
        )
        self.cmb_stage.pack(side="right")
        self.cmb_stage.bind("<<ComboboxSelected>>", self._on_stage_filter_change)

        tk.Label(
            filter_f,
            text="Stage Filter:",
            font=("Segoe UI", 9, "bold"),
            fg="#475569",
            bg="#E2E8F0"
        ).pack(side="right", padx=(0, 5))

        # 3. Main Content Container
        self.content_frame = tk.Frame(self, bg="#F8FAFC", padx=25, pady=15)
        self.content_frame.pack(fill="both", expand=True)

        # 4. Bottom Action Footer
        footer = tk.Frame(self, bg="#FFFFFF", height=75, bd=1, relief="solid")
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        # Left Actions (Revert / Module launch)
        btn_left_f = tk.Frame(footer, bg="#FFFFFF")
        btn_left_f.pack(side="left", padx=15, pady=15)

        self.btn_revert = tk.Button(
            btn_left_f,
            text="↩️ Revert to BOM",
            font=("Segoe UI", 9),
            bg="#FEF2F2",
            fg="#991B1B",
            activebackground="#FEE2E2",
            relief="flat",
            bd=1,
            cursor="hand2",
            command=self._revert_current
        )

        tk.Button(
            btn_left_f,
            text="↗️ Open in Module",
            font=("Segoe UI", 9),
            bg="#F8FAFC",
            fg="#0F172A",
            relief="flat",
            bd=1,
            cursor="hand2",
            command=self._launch_current_module
        ).pack(side="left", padx=5)

        tk.Button(
            btn_left_f,
            text="⏭️ Skip for Later",
            font=("Segoe UI", 9),
            bg="#F1F5F9",
            fg="#475569",
            relief="flat",
            bd=1,
            cursor="hand2",
            command=self._next_item
        ).pack(side="left", padx=5)

        # Right Actions (Approve / Dispatch All)
        btn_right_f = tk.Frame(footer, bg="#FFFFFF")
        btn_right_f.pack(side="right", padx=15, pady=15)

        self.btn_dispatch_all = tk.Button(
            btn_right_f,
            text="⚡ Dispatch All Remaining",
            font=("Segoe UI", 9, "bold"),
            bg="#0284C7",
            fg="#FFFFFF",
            activebackground="#0369A1",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            padx=12,
            pady=4,
            command=self._dispatch_all_remaining
        )
        self.btn_dispatch_all.pack(side="left", padx=5)

        self.btn_approve_single = tk.Button(
            btn_right_f,
            text="🚀 Approve & Dispatch This RFQ",
            font=("Segoe UI", 10, "bold"),
            bg="#16A34A",
            fg="#FFFFFF",
            activebackground="#15803D",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            padx=15,
            pady=4,
            command=self._approve_current_item
        )
        self.btn_approve_single.pack(side="left", padx=5)

    def _render_current_item(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if not self.gates:
            self._render_empty_state()
            return

        self.current_idx = max(0, min(self.current_idx, len(self.gates) - 1))
        gate = self.gates[self.current_idx]
        total = len(self.gates)
        curr = self.current_idx + 1

        self.lbl_counter.config(text=f"Queue: {curr} of {total} Pending")
        self.lbl_stepper_info.config(text=f"RFQ {curr} of {total}: '{gate.get('rfq_id')}' (Customer: '{gate.get('customer')}')")
        
        self.btn_prev.config(state="normal" if self.current_idx > 0 else "disabled")
        self.btn_next.config(state="normal" if self.current_idx < total - 1 else "disabled")
        self.btn_dispatch_all.config(text=f"⚡ Dispatch All Remaining ({total})", state="normal")
        self.btn_approve_single.config(state="normal")

        # BOM stage items cannot revert backwards (BOM is Stage 1)
        raw_stg = gate.get("raw_stage") or gate.get("stage") or "pending_bom"
        if raw_stg in ("pending_bom", "bom", "", None):
            self.btn_revert.pack_forget()
        else:
            self.btn_revert.pack(side="left", padx=5)

        # Card Frame
        card = tk.Frame(self.content_frame, bg="#FFFFFF", bd=1, relief="solid", padx=20, pady=15)
        card.pack(fill="both", expand=True)

        rfq_id = gate.get("rfq_id", "N/A")
        cust = gate.get("customer", "N/A")
        curr_stage_name = gate.get("current_stage") or "BOM Verification"
        next_act_name = gate.get("next_action") or "Sourcing & Cycle Time"
        summary = gate.get("summary", {})

        # Title
        tk.Label(
            card,
            text=f"🛑 Human Approval Required — {rfq_id}",
            font=("Segoe UI", 13, "bold"),
            fg="#0F172A",
            bg="#FFFFFF"
        ).pack(anchor="w", pady=(0, 10))

        # Details Grid Frame
        grid_f = tk.Frame(card, bg="#FFFFFF")
        grid_f.pack(fill="x", pady=5)

        tp_st = summary.get("tp_status") or gate.get("tp_status") or "Pending"
        eau_st = summary.get("eau_status") or gate.get("eau_status") or "Pending"

        fields = [
            ("Customer Name:", cust),
            ("RFQ Number:", rfq_id),
            ("Current Stage:", curr_stage_name),
            ("Commodity:", summary.get("commodity", gate.get("commodity", "Wire Harness"))),
            ("Total Assemblies:", str(summary.get("assembly_count", len(summary.get("assemblies", [1]))))),
            ("Assigned MOQs:", str(summary.get("assigned_moqs", "Standard / Default"))),
            ("Target Price Status:", f"{tp_st}" if "BOM" in curr_stage_name else str(summary.get("target_price", "N/A"))),
            ("EAU Status:", f"{eau_st}" if "BOM" in curr_stage_name else (f"{summary.get('eau')} pcs" if summary.get('eau') else "N/A")),
            ("Stage PIC:", gate.get("pic", "Ai Tink")),
            ("Status / Stage:", f"{curr_stage_name} Completed ➔ Ready for {next_act_name}")
        ]

        for r_idx, (label, val) in enumerate(fields):
            tk.Label(
                grid_f,
                text=label,
                font=("Segoe UI", 9, "bold"),
                fg="#64748B",
                bg="#FFFFFF"
            ).grid(row=r_idx, column=0, sticky="w", pady=4, padx=(0, 15))

            tk.Label(
                grid_f,
                text=val,
                font=("Segoe UI", 9, "bold" if "Status" in label or "RFQ" in label else "normal"),
                fg="#0F172A" if "Status" not in label else "#0284C7",
                bg="#FFFFFF"
            ).grid(row=r_idx, column=1, sticky="w", pady=4)

        if "BOM" in curr_stage_name and (tp_st != "Completed" or eau_st != "Completed"):
            adv = tk.Frame(card, bg="#FFFBEB", bd=1, relief="solid", padx=12, pady=6)
            adv.pack(fill="x", pady=(0, 10))
            tk.Label(
                adv,
                text=f"ℹ️ Notice: Target Price: '{tp_st}' • EAU: '{eau_st}'. (These parameters are optional and do not block dispatch. You may proceed with dispatch or click '↗️ Open in Module' to assign them).",
                font=("Segoe UI", 9),
                fg="#92400E",
                bg="#FFFBEB",
                wraplength=680,
                justify="left"
            ).pack(anchor="w")

        # Highlight Box for Next Actions
        hl = tk.Frame(card, bg="#F0FDF4", bd=1, relief="solid", padx=15, pady=10)
        hl.pack(fill="x", pady=15)

        tk.Label(
            hl,
            text=f"✨ Ready for Dispatch to {next_act_name}:",
            font=("Segoe UI", 9, "bold"),
            fg="#166534",
            bg="#F0FDF4"
        ).pack(anchor="w")

        action_desc = gate.get("action_prompt") or f"Clicking 'Approve & Dispatch' will dispatch this RFQ to {next_act_name}, send official SMTP emails, and advance the queue."
        tk.Label(
            hl,
            text=action_desc,
            font=("Segoe UI", 9),
            fg="#15803D",
            bg="#F0FDF4",
            wraplength=680,
            justify="left"
        ).pack(anchor="w", pady=(2, 0))

    def _render_empty_state(self):
        self.lbl_counter.config(text="Queue: 0 Pending")
        self.lbl_stepper_info.config(text="All approvals completed")
        self.btn_prev.config(state="disabled")
        self.btn_next.config(state="disabled")
        self.btn_dispatch_all.config(state="disabled")
        self.btn_approve_single.config(state="disabled")
        self.btn_revert.pack_forget()

        empty_card = tk.Frame(self.content_frame, bg="#FFFFFF", bd=1, relief="solid", padx=30, pady=40)
        empty_card.pack(fill="both", expand=True)

        tk.Label(
            empty_card,
            text="🎉 All Clear! Approval Queue Empty",
            font=("Segoe UI", 16, "bold"),
            fg="#16A34A",
            bg="#FFFFFF"
        ).pack(pady=(20, 10))

        tk.Label(
            empty_card,
            text="All pending RFQs in your queue have been approved, dispatched, or resolved.\nYou can close this workspace and return to the main portal.",
            font=("Segoe UI", 10),
            fg="#64748B",
            bg="#FFFFFF",
            justify="center"
        ).pack(pady=(0, 25))

        tk.Button(
            empty_card,
            text="Close Workspace",
            font=("Segoe UI", 10, "bold"),
            bg="#1E293B",
            fg="#FFFFFF",
            relief="flat",
            padx=20,
            pady=6,
            cursor="hand2",
            command=self.destroy
        ).pack()

    def _prev_item(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self._render_current_item()

    def _next_item(self):
        if self.current_idx < len(self.gates) - 1:
            self.current_idx += 1
            self._render_current_item()

    def _approve_current_item(self):
        if not self.gates:
            return

        gate = self.gates[self.current_idx]
        rfq_id = gate.get("rfq_id")
        dept = gate.get("stage", "bom")

        try:
            from agents.tool_registry import ContinuumXToolRegistry
            success, msg = ContinuumXToolRegistry.execute_system_dispatch(
                dept=dept,
                rfq_id=rfq_id,
                username=self.username,
                comments=f"Approved via Guided Approval Queue ({gate.get('current_stage', 'Stage')})."
            )
            if success:
                # Remove from both lists
                self.all_gates = [g for g in self.all_gates if g.get("rfq_id") != rfq_id]
                self.gates.pop(self.current_idx)
                self._update_stage_filter_options()
                if self.on_queue_updated:
                    self.on_queue_updated(self.all_gates)
                self._render_current_item()
            else:
                messagebox.showwarning("Dispatch Notice", f"Could not dispatch RFQ '{rfq_id}':\n{msg}", parent=self)
        except Exception as ex:
            messagebox.showerror("Dispatch Error", f"Error during dispatch: {ex}", parent=self)

    def _dispatch_all_remaining(self):
        if not self.gates:
            return

        count = len(self.gates)
        confirm = messagebox.askyesno(
            "Confirm Batch Dispatch",
            f"Are you sure you want to dispatch all {count} remaining RFQ(s) in this view now?",
            parent=self
        )
        if not confirm:
            return

        from agents.tool_registry import ContinuumXToolRegistry
        from collections import defaultdict

        dept_groups = defaultdict(list)
        for g in self.gates:
            if g.get("rfq_id"):
                dept_groups[g.get("stage", "bom")].append(g.get("rfq_id"))

        all_success = []
        all_fails = []
        for dept, ids in dept_groups.items():
            s_list, f_list = ContinuumXToolRegistry.execute_batch_system_dispatch(
                dept=dept,
                rfq_ids=ids,
                username=self.username,
                comments="Batch approved via Guided Approval Queue."
            )
            all_success.extend(s_list)
            all_fails.extend(f_list)

        # Remove succeeded gates
        self.all_gates = [g for g in self.all_gates if g.get("rfq_id") not in all_success]
        self.gates = [g for g in self.gates if g.get("rfq_id") not in all_success]
        self._update_stage_filter_options()

        if self.on_queue_updated:
            self.on_queue_updated(self.all_gates)

        if all_fails:
            messagebox.showwarning("Batch Dispatch Finished", f"Dispatched {len(all_success)} RFQs successfully.\nFailed {len(all_fails)}:\n" + "\n".join(all_fails), parent=self)
        else:
            messagebox.showinfo("Batch Dispatch Completed", f"Successfully dispatched all {len(all_success)} RFQ(s)!\n1 Consolidated notification email sent to team PICs.", parent=self)
        self._render_current_item()

    def _revert_current(self):
        if not self.gates:
            return
        gate = self.gates[self.current_idx]
        rfq_id = gate.get("rfq_id")
        cust = gate.get("customer")

        try:
            from agents.tool_registry import ContinuumXToolRegistry
            success, msg = ContinuumXToolRegistry.revert_project(
                rfq_id=rfq_id,
                customer=cust,
                target_stage="pending_bom",
                reason="Reverted from Guided Approval Queue for re-verification.",
                requested_by=self.username,
                from_stage=gate.get("raw_stage")
            )
            if success:
                messagebox.showinfo("RFQ Reverted", f"RFQ '{rfq_id}' has been reverted to BOM Verification.", parent=self)
                self.all_gates = [g for g in self.all_gates if g.get("rfq_id") != rfq_id]
                self.gates.pop(self.current_idx)
                self._update_stage_filter_options()
                if self.on_queue_updated:
                    self.on_queue_updated(self.all_gates)
                self._render_current_item()
            else:
                messagebox.showwarning("Revert Notice", msg, parent=self)
        except Exception as ex:
            messagebox.showerror("Revert Error", f"Error reverting RFQ: {ex}", parent=self)

    def _launch_current_module(self):
        if not self.gates:
            return
        gate = self.gates[self.current_idx]
        stg = gate.get("stage", "bom")
        stage_to_feature = {
            "bom": "BOM",
            "sourcing": "Sourcing",
            "cycle_time": "Cycle Time",
            "costing": "Costing",
            "npi": "NPI",
            "wi": "WI"
        }
        feat = stage_to_feature.get(stg, "BOM")
        if hasattr(self.master, "launch_feature"):
            self.master.launch_feature(feat)
