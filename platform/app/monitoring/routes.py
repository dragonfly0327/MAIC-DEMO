"""Monitoring API: REST snapshots + a live WebSocket firehose.

Powers the Team 3 operations dashboard: agent health/status, task and resource
meters, server up/down, live log stream, error alerts, and the human approval
queue. These endpoints are operator-facing (no agent token required in Phase 1;
lock down in Phase 2 alongside tenant auth).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, WebSocket, WebSocketDisconnect

from app.broker.event_broker import MONITOR_CHANNEL, broker
from app.agents.registry import registry
from app.hitl.approvals import approvals
from app.config import get_settings

router = APIRouter(tags=["monitoring"])


@router.get("/health")
async def health():
    """Liveness probe for the platform process (used by Docker healthchecks)."""
    return {"status": "ok"}


@router.get("/agents")
async def get_agents():
    return await registry.list_agents()


@router.get("/events")
async def get_events(limit: int = 100):
    return broker.recent(limit=limit)


@router.get("/errors")
async def get_errors(limit: int = 50):
    return broker.recent_errors(limit=limit)


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


@router.get("/telemetry/errors")
async def get_telemetry_errors():
    """File-backed ErrorTelemetryStore snapshot (works before agents register)."""
    settings = get_settings()
    summary = _read_json(settings.telemetry_dir / "latest_errors_summary.json", {})
    if not summary:
        incidents = _read_json(settings.telemetry_dir / "agent_errors.json", [])
        summary = {
            "total_incidents": len(incidents) if isinstance(incidents, list) else 0,
            "incidents_by_module": {},
            "incidents_by_category": {},
            "recent_incidents": incidents[-15:] if isinstance(incidents, list) else [],
        }
    return summary


@router.get("/telemetry/accuracy")
async def get_telemetry_accuracy():
    """File-backed AccuracyTelemetryStore audits for the quality table/chart."""
    settings = get_settings()
    audits = _read_json(settings.telemetry_dir / "accuracy_audit.json", [])
    if not isinstance(audits, list):
        audits = []
    latest = _read_json(settings.telemetry_dir / "latest_accuracy_summary.json", {})
    return {"audits": audits, "latest": latest or (audits[-1] if audits else {})}


@router.get("/approvals")
async def get_approvals(pending_only: bool = True):
    return await (approvals.list_pending() if pending_only else approvals.list_all())


@router.post("/approvals")
async def create_approval(body: dict = Body(...)):
    item = await approvals.create(
        agent_id=body.get("agent_id", "unknown"),
        step_name=body.get("step_name", "review"),
        summary=body.get("summary", ""),
        confidence_score=body.get("confidence_score", 0.0),
        transaction_uuid=body.get("transaction_uuid"),
    )
    return item


@router.post("/approvals/{approval_id}/decision")
async def decide_approval(approval_id: str, body: dict = Body(...)):
    approved = bool(body.get("approved", False))
    item = await approvals.decide(approval_id, approved, body.get("operator_override"))
    if item is None:
        raise HTTPException(status_code=404, detail="approval not found")
    return item


@router.websocket("/ws/monitor")
async def ws_monitor(websocket: WebSocket):
    """Live event stream for the dashboard.

    On connect we replay a bounded tail of recent events so a freshly opened or
    reloaded dashboard is not blank, then stream new events as they arrive.
    """
    await websocket.accept()
    queue = await broker.subscribe(MONITOR_CHANNEL)
    try:
        for event in broker.recent():
            await websocket.send_json(event)
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    finally:
        await broker.unsubscribe(MONITOR_CHANNEL, queue)
