"""Centralized event broker (evolves ref/BOM/backlog_api.py).

The legacy ``backlog_api.py`` only appended JSON lines to disk. This turns it
into an in-process async publish/subscribe broker while preserving the durable
JSONL backlog.

Public API intentionally matches what Team 2 already assumes in their plan:

    event_broker.publish(channel="team2_errors", payload=event)

Subscribers receive events via ``asyncio.Queue`` objects. Phase 1 keeps all
state in-memory in a single process (no Redis); persistence is the JSONL file.
Delivery to live subscribers is at-most-once fire-and-forget.
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from pathlib import Path
from typing import Any

from app.config import get_settings

# Channels reserved for failure isolation. Errors published here also mirror to
# the monitoring "errors" stream so operators see them immediately.
ERROR_CHANNELS = {"team2_errors", "erp_gateway_errors", "platform_errors"}

# Firehose channel the monitoring WebSocket subscribes to.
MONITOR_CHANNEL = "__monitor__"


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._jsonl_path: Path = get_settings().backlog_jsonl
        # Ring buffer of recent events for dashboard replay-on-connect.
        self._recent: deque[dict[str, Any]] = deque(maxlen=get_settings().replay_tail)

    async def publish(self, channel: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Publish an event to a channel.

        The event is persisted to the JSONL backlog, buffered for replay, and
        fanned out to live subscribers of both ``channel`` and the monitor
        firehose. Errors are additionally tagged for the dashboard error pane.
        """
        event = {"channel": channel, **payload}
        event.setdefault("timestamp", _utcnow_iso())
        if channel in ERROR_CHANNELS:
            event["is_error"] = True

        self._persist(event)
        self._recent.append(event)

        async with self._lock:
            targets: set[asyncio.Queue] = set()
            targets |= self._subscribers.get(channel, set())
            targets |= self._subscribers.get(MONITOR_CHANNEL, set())

        for queue in targets:
            # Fire-and-forget: drop for slow/full consumers rather than block.
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
        return event

    async def subscribe(self, channel: str) -> asyncio.Queue:
        """Register a subscriber to a channel and return its delivery queue."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        async with self._lock:
            self._subscribers.setdefault(channel, set()).add(queue)
        return queue

    async def unsubscribe(self, channel: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            subs = self._subscribers.get(channel)
            if subs and queue in subs:
                subs.discard(queue)
                if not subs:
                    self._subscribers.pop(channel, None)

    def recent(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Return the buffered recent events (newest last) for replay."""
        events = list(self._recent)
        if limit is not None:
            events = events[-limit:]
        return events

    def recent_errors(self, limit: int = 50) -> list[dict[str, Any]]:
        errors = [e for e in self._recent if e.get("is_error")]
        return errors[-limit:]

    def _persist(self, event: dict[str, Any]) -> None:
        try:
            self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self._jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except OSError:
            # Never let a disk hiccup break the live event path.
            pass


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# Module-level singleton used across the app.
broker = EventBroker()
