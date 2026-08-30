"""Agent-facing HTTP + WebSocket endpoints.

Agents use these to register, heartbeat, send messages to other agents, and
subscribe to their own inbound message stream. All routes require the shared
agent bearer token (Phase 1).

The broker never inspects ``encrypted_payload`` - it only routes the cleartext
envelope to the recipient's channel (``agent:<to>``).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.agents.registry import registry
from app.broker.event_broker import broker
from app.models import Envelope, HeartbeatIn, AgentErrorIn
from app.security.auth import require_agent_token, token_is_valid

router = APIRouter(prefix="/agents", tags=["agents"])


def agent_channel(agent_id: str) -> str:
    return f"agent:{agent_id}"


@router.post("/register", dependencies=[Depends(require_agent_token)])
async def register(hb: HeartbeatIn):
    info = await registry.register(hb)
    return info


@router.post("/heartbeat", dependencies=[Depends(require_agent_token)])
async def heartbeat(hb: HeartbeatIn):
    info = await registry.heartbeat(hb)
    return info


@router.post("/send", dependencies=[Depends(require_agent_token)])
async def send(envelope: Envelope):
    """Route an already-encrypted envelope to the recipient's channel.

    Delivery is at-most-once fire-and-forget: if the recipient has no live
    subscriber the message is still logged to the backlog for the dashboard,
    but not queued for later delivery.
    """
    event = envelope.model_dump(by_alias=True)
    event["event_type"] = "AGENT_MSG"
    await broker.publish(agent_channel(envelope.to), event)
    # Mirror a redacted record onto the monitor firehose (no payload leak; the
    # payload is encrypted anyway, but we keep the stream lean).
    await broker.publish(
        "agent_messages",
        {
            "event_type": "AGENT_MSG",
            "from": envelope.sender,
            "to": envelope.to,
            "msg_type": envelope.msg_type,
            "transaction_uuid": envelope.transaction_uuid,
        },
    )
    return {"status": "routed", "to": envelope.to, "msg_type": envelope.msg_type}


@router.post("/errors", dependencies=[Depends(require_agent_token)])
async def report_error(body: AgentErrorIn):
    """Mirror a desktop ErrorTelemetryStore incident onto the live error channel."""
    event = await broker.publish(
        "team2_errors",
        {
            "event_type": body.event_type or "TEAM2_SERVICE_ERROR",
            "agent_id": body.agent_id,
            "error_type": body.error_type,
            "detail": body.detail,
            "severity": body.severity,
            "transaction_uuid": body.transaction_uuid or body.rfq_number,
            "module": body.module or body.agent_id,
            "error_id": body.error_id,
            "status": body.status,
            "rfq_number": body.rfq_number,
            "customer": body.customer,
        },
    )
    return {"status": "logged", "error_id": body.error_id, "is_error": event.get("is_error", True)}


# Note: listing the agent fleet is an operator/monitoring concern and is served
# (without the agent token) by GET /agents in app/monitoring/routes.py. We do
# NOT define GET /agents here to avoid a route collision that would shadow the
# dashboard's unauthenticated poll and return 401.


@router.websocket("/{agent_id}/stream")
async def agent_stream(websocket: WebSocket, agent_id: str):
    """Inbound message stream for a single agent.

    Auth is passed as a ``token`` query param since browsers/WS clients cannot
    always set Authorization headers.
    """
    token = websocket.query_params.get("token")
    if not token_is_valid(f"Bearer {token}"):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    channel = agent_channel(agent_id)
    queue = await broker.subscribe(channel)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    finally:
        await broker.unsubscribe(channel, queue)
