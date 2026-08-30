"""Human-in-the-loop approval queue.

Agents can raise a decision that requires a human ("let user know agent status,
so they can make human decision to approve"). Operators approve/reject from the
dashboard. This in-memory queue mirrors the future ``staging_actions`` table so
Phase 2 migrates it straight into Postgres.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from app.broker.event_broker import broker
from app.models import ApprovalItem


class ApprovalStore:
    def __init__(self) -> None:
        self._items: dict[str, ApprovalItem] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        agent_id: str,
        step_name: str,
        summary: str = "",
        confidence_score: float = 0.0,
        transaction_uuid: str | None = None,
    ) -> ApprovalItem:
        item = ApprovalItem(
            approval_id=str(uuid.uuid4()),
            agent_id=agent_id,
            step_name=step_name,
            summary=summary,
            confidence_score=confidence_score,
            transaction_uuid=transaction_uuid,
        )
        async with self._lock:
            self._items[item.approval_id] = item
        await broker.publish(
            "approvals",
            {
                "event_type": "APPROVAL_REQUESTED",
                "approval_id": item.approval_id,
                "agent_id": agent_id,
                "step_name": step_name,
            },
        )
        return item

    async def decide(
        self, approval_id: str, approved: bool, operator_override: dict[str, Any] | None = None
    ) -> ApprovalItem | None:
        async with self._lock:
            item = self._items.get(approval_id)
            if item is None:
                return None
            item.status = "Approved" if approved else "Rejected"
            item.operator_override = operator_override or {}
            item.decided_at = datetime.now(timezone.utc).isoformat()
        await broker.publish(
            "approvals",
            {
                "event_type": "APPROVAL_DECIDED",
                "approval_id": approval_id,
                "status": item.status,
            },
        )
        return item

    async def list_pending(self) -> list[ApprovalItem]:
        async with self._lock:
            return [i for i in self._items.values() if i.status == "Pending Review"]

    async def list_all(self) -> list[ApprovalItem]:
        async with self._lock:
            return list(self._items.values())


approvals = ApprovalStore()
