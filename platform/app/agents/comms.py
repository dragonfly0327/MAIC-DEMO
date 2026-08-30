"""AgentComms: the reusable agent-to-agent messaging layer.

This is the durable contract Team 2's agents adopt. An agent constructs an
``AgentComms``, then:

    comms = AgentComms(agent_id="rfq_parser", role="parser")
    await comms.register()
    comms.on("hello", handle_hello)
    await comms.start()                       # opens inbound stream
    await comms.send(to="matcher", msg_type="hello", payload={"text": "hi"})

Encryption happens *client-side* here: ``payload`` is encrypted into the
envelope's ``encrypted_payload`` before it ever reaches the broker, and inbound
messages are decrypted here before handlers run. The broker/monitoring layer
only sees cleartext envelope metadata.

The hello/byebye exchange is just the first validation test; any ``msg_type``
with any JSON ``payload`` works without changing the transport.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Optional

import httpx
import psutil
import websockets

from app.models import Envelope, HeartbeatIn
from app.security.crypto import decrypt_payload, encrypt_payload

# One host sample shared by every AgentComms in this process so cards do not
# show 0% / 100% jitter from sequential psutil.cpu_percent() first-call zeros.
_cpu_sample = 0.0
_cpu_ts = 0.0
psutil.cpu_percent(interval=None)


def _host_cpu_percent() -> float:
    global _cpu_sample, _cpu_ts
    now = time.monotonic()
    if now - _cpu_ts >= 1.0:
        _cpu_sample = min(100.0, float(psutil.cpu_percent(interval=None) or 0.0))
        _cpu_ts = now
    return _cpu_sample


Handler = Callable[["InboundMessage"], Awaitable[None] | None]


class InboundMessage:
    """A decrypted message delivered to a handler."""

    def __init__(self, sender: str, to: str, msg_type: str, payload: dict[str, Any],
                 transaction_uuid: Optional[str]) -> None:
        self.sender = sender
        self.to = to
        self.msg_type = msg_type
        self.payload = payload
        self.transaction_uuid = transaction_uuid

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"InboundMessage(from={self.sender!r}, type={self.msg_type!r}, payload={self.payload!r})"


class AgentComms:
    def __init__(
        self,
        agent_id: str,
        role: str = "generic",
        base_url: str = "http://127.0.0.1:8000",
        token: str = "dev-agent-token",
    ) -> None:
        self.agent_id = agent_id
        self.role = role
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._handlers: dict[str, list[Handler]] = {}
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        self._ws_task: Optional[asyncio.Task] = None
        self._hb_task: Optional[asyncio.Task] = None
        self._status = "idle"
        self._tasks = {"queued": 0, "running": 0, "on_hold": 0, "done": 0}
        self._quality = {
            "avg_confidence": 0.0,
            "accuracy_pct": 0.0,
            "reviewed_n": 0,
            "override_n": 0,
            "accuracy_pending": True,
        }

    # -- lifecycle -----------------------------------------------------------

    async def register(self) -> dict[str, Any]:
        resp = await self._client.post("/agents/register", json=self._heartbeat_body())
        resp.raise_for_status()
        return resp.json()

    async def start(self, heartbeat_interval_s: float = 5.0) -> None:
        """Open the inbound message stream and begin periodic heartbeats."""
        self._ws_task = asyncio.create_task(self._consume_stream())
        self._hb_task = asyncio.create_task(self._heartbeat_loop(heartbeat_interval_s))

    async def close(self) -> None:
        for task in (self._ws_task, self._hb_task):
            if task:
                task.cancel()
        await self._client.aclose()

    # -- messaging -----------------------------------------------------------

    def on(self, msg_type: str, handler: Handler) -> None:
        self._handlers.setdefault(msg_type, []).append(handler)

    async def send(
        self,
        to: str,
        msg_type: str,
        payload: dict[str, Any],
        transaction_uuid: Optional[str] = None,
    ) -> dict[str, Any]:
        envelope = Envelope(
            **{"from": self.agent_id},
            to=to,
            msg_type=msg_type,
            encrypted_payload=encrypt_payload(payload),
            transaction_uuid=transaction_uuid,
        )
        resp = await self._client.post("/agents/send", json=envelope.model_dump(by_alias=True))
        resp.raise_for_status()
        return resp.json()

    # -- status --------------------------------------------------------------

    def set_status(self, status: str) -> None:
        self._status = status

    def set_tasks(self, queued: int = 0, running: int = 0, on_hold: int = 0, done: int = 0) -> None:
        self._tasks = {"queued": queued, "running": running, "on_hold": on_hold, "done": done}

    def set_quality(
        self,
        avg_confidence: float = 0.0,
        accuracy_pct: float = 0.0,
        reviewed_n: int = 0,
        override_n: int = 0,
        accuracy_pending: bool = True,
    ) -> None:
        self._quality = {
            "avg_confidence": avg_confidence,
            "accuracy_pct": accuracy_pct,
            "reviewed_n": reviewed_n,
            "override_n": override_n,
            "accuracy_pending": accuracy_pending,
        }

    async def heartbeat(self) -> dict[str, Any]:
        resp = await self._client.post("/agents/heartbeat", json=self._heartbeat_body())
        resp.raise_for_status()
        return resp.json()

    # -- internals -----------------------------------------------------------

    def _heartbeat_body(self) -> dict[str, Any]:
        hb = HeartbeatIn(
            agent_id=self.agent_id,
            role=self.role,
            status=self._status,  # type: ignore[arg-type]
            tasks_queued=self._tasks["queued"],
            tasks_running=self._tasks["running"],
            tasks_on_hold=self._tasks["on_hold"],
            tasks_done=self._tasks["done"],
            cpu_percent=_host_cpu_percent(),
            mem_percent=psutil.virtual_memory().percent,
            avg_confidence=self._quality["avg_confidence"],
            accuracy_pct=self._quality["accuracy_pct"],
            reviewed_n=self._quality["reviewed_n"],
            override_n=self._quality["override_n"],
            accuracy_pending=self._quality["accuracy_pending"],
        )
        return hb.model_dump()

    async def _heartbeat_loop(self, interval_s: float) -> None:
        while True:
            try:
                await self.heartbeat()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(interval_s)

    async def _consume_stream(self) -> None:
        ws_url = self.base_url.replace("http", "ws", 1)
        uri = f"{ws_url}/agents/{self.agent_id}/stream?token={self.token}"
        while True:
            try:
                async with websockets.connect(uri) as ws:
                    async for raw in ws:
                        await self._dispatch(raw)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Reconnect after a short delay if the stream drops.
                await asyncio.sleep(1.0)

    async def _dispatch(self, raw: str) -> None:
        import json

        event = json.loads(raw)
        msg_type = event.get("msg_type")
        token = event.get("encrypted_payload")
        if token is None:
            return
        payload = decrypt_payload(token)
        message = InboundMessage(
            sender=event.get("from"),
            to=event.get("to"),
            msg_type=msg_type,
            payload=payload,
            transaction_uuid=event.get("transaction_uuid"),
        )
        for handler in self._handlers.get(msg_type, []):
            result = handler(message)
            if asyncio.iscoroutine(result):
                await result
