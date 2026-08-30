"""Shared data contracts for the Team 3 platform.

Defining these once keeps the broker, comms layer, registry, and dashboard in
agreement. ``Envelope`` in particular is the durable message contract Team 2's
agents will adopt - only ``encrypted_payload`` is confidential; every other
field stays cleartext so the broker can route and the dashboard can monitor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ENVELOPE_SCHEMA_VERSION = "1.0"

AgentStatus = Literal["idle", "busy", "offline"]
ApprovalStatus = Literal["Pending Review", "Approved", "Rejected"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Envelope(BaseModel):
    """Generic agent-to-agent message.

    The ``encrypted_payload`` holds a Fernet token produced by the sending
    agent; the broker never decrypts it. All other fields are cleartext
    metadata used for routing, correlation, and monitoring.
    """

    model_config = {"populate_by_name": True}

    schema_version: str = ENVELOPE_SCHEMA_VERSION
    # ``from`` is a Python keyword, so store as ``sender`` with a "from" alias.
    sender: str = Field(alias="from")
    to: str
    msg_type: str
    encrypted_payload: str
    transaction_uuid: Optional[str] = None
    timestamp: str = Field(default_factory=_utcnow_iso)


class HeartbeatIn(BaseModel):
    """Payload an agent posts on register/heartbeat."""

    agent_id: str
    role: str = "generic"
    status: AgentStatus = "idle"
    tasks_queued: int = 0
    tasks_running: int = 0
    tasks_on_hold: int = 0
    tasks_done: int = 0
    cpu_percent: float = 0.0
    mem_percent: float = 0.0
    avg_confidence: float = 0.0
    accuracy_pct: float = 0.0
    reviewed_n: int = 0
    override_n: int = 0
    accuracy_pending: bool = True
    transaction_uuid: Optional[str] = None


class AgentInfo(BaseModel):
    """Registry view of an agent, surfaced to the dashboard."""

    agent_id: str
    role: str = "generic"
    status: AgentStatus = "idle"
    tasks_queued: int = 0
    tasks_running: int = 0
    tasks_on_hold: int = 0
    tasks_done: int = 0
    cpu_percent: float = 0.0
    mem_percent: float = 0.0
    avg_confidence: float = 0.0
    accuracy_pct: float = 0.0
    reviewed_n: int = 0
    override_n: int = 0
    accuracy_pending: bool = True
    last_seen: str = Field(default_factory=_utcnow_iso)
    registered_at: str = Field(default_factory=_utcnow_iso)


class AgentErrorIn(BaseModel):
    """Incident mirrored from ErrorTelemetryStore onto the broker."""

    agent_id: str = "brain"
    event_type: str = "TEAM2_SERVICE_ERROR"
    error_type: str = "UNHANDLED"
    detail: str = ""
    severity: str = "ERROR"
    transaction_uuid: Optional[str] = None
    module: Optional[str] = None
    error_id: Optional[str] = None
    status: Optional[str] = None
    rfq_number: Optional[str] = None
    customer: Optional[str] = None


class ApprovalItem(BaseModel):
    """Human-in-the-loop decision surfaced to an operator.

    Mirrors the future ``staging_actions`` table so Phase 2 can migrate this
    straight into Postgres.
    """

    approval_id: str
    transaction_uuid: Optional[str] = None
    agent_id: str
    step_name: str
    summary: str = ""
    confidence_score: float = 0.0
    status: ApprovalStatus = "Pending Review"
    operator_override: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utcnow_iso)
    decided_at: Optional[str] = None
