"""Agent registry: health, status, task counts, and resource usage.

Agents register once, then send periodic heartbeats carrying self-reported
status, task counts, and resource usage (cpu/mem via psutil on the agent side).
A background sweeper marks agents ``offline`` when their heartbeats go stale -
this is what drives the "server down or not" signal on the dashboard.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.broker.event_broker import broker
from app.config import get_settings
from app.models import AgentInfo, HeartbeatIn


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}
        self._last_seen: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def register(self, hb: HeartbeatIn) -> AgentInfo:
        now = _utcnow()
        async with self._lock:
            existing = self._agents.get(hb.agent_id)
            info = AgentInfo(
                agent_id=hb.agent_id,
                role=hb.role,
                status=hb.status,
                tasks_queued=hb.tasks_queued,
                tasks_running=hb.tasks_running,
                tasks_on_hold=hb.tasks_on_hold,
                tasks_done=hb.tasks_done,
                cpu_percent=hb.cpu_percent,
                mem_percent=hb.mem_percent,
                avg_confidence=hb.avg_confidence,
                accuracy_pct=hb.accuracy_pct,
                reviewed_n=hb.reviewed_n,
                override_n=hb.override_n,
                accuracy_pending=hb.accuracy_pending,
                last_seen=_iso(now),
                registered_at=existing.registered_at if existing else _iso(now),
            )
            self._agents[hb.agent_id] = info
            self._last_seen[hb.agent_id] = now
        await broker.publish(
            "agents",
            {"event_type": "AGENT_REGISTERED", "agent_id": hb.agent_id, "role": hb.role},
        )
        return info

    async def heartbeat(self, hb: HeartbeatIn) -> AgentInfo:
        now = _utcnow()
        async with self._lock:
            if hb.agent_id not in self._agents:
                # Auto-register on first heartbeat for resilience.
                info = AgentInfo(agent_id=hb.agent_id, registered_at=_iso(now))
            else:
                info = self._agents[hb.agent_id]
            info.role = hb.role
            info.status = hb.status
            info.tasks_queued = hb.tasks_queued
            info.tasks_running = hb.tasks_running
            info.tasks_on_hold = hb.tasks_on_hold
            info.tasks_done = hb.tasks_done
            info.cpu_percent = hb.cpu_percent
            info.mem_percent = hb.mem_percent
            info.avg_confidence = hb.avg_confidence
            info.accuracy_pct = hb.accuracy_pct
            info.reviewed_n = hb.reviewed_n
            info.override_n = hb.override_n
            info.accuracy_pending = hb.accuracy_pending
            info.last_seen = _iso(now)
            self._agents[hb.agent_id] = info
            self._last_seen[hb.agent_id] = now
        await broker.publish(
            "agents",
            {
                "event_type": "HEARTBEAT",
                "agent_id": hb.agent_id,
                "status": hb.status,
                "cpu_percent": hb.cpu_percent,
                "mem_percent": hb.mem_percent,
                "tasks_on_hold": hb.tasks_on_hold,
            },
        )
        return info

    async def list_agents(self) -> list[AgentInfo]:
        async with self._lock:
            return list(self._agents.values())

    async def get(self, agent_id: str) -> AgentInfo | None:
        async with self._lock:
            return self._agents.get(agent_id)

    async def _sweep_once(self) -> list[str]:
        """Mark stale agents offline; return the ids newly flipped offline."""
        settings = get_settings()
        cutoff = _utcnow().timestamp() - settings.heartbeat_timeout_s
        flipped: list[str] = []
        async with self._lock:
            for agent_id, info in self._agents.items():
                last = self._last_seen.get(agent_id)
                if last is None:
                    continue
                if last.timestamp() < cutoff and info.status != "offline":
                    info.status = "offline"
                    flipped.append(agent_id)
        for agent_id in flipped:
            await broker.publish(
                "agents",
                {"event_type": "AGENT_OFFLINE", "agent_id": agent_id},
            )
        return flipped

    async def run_sweeper(self) -> None:
        """Background loop; started as a FastAPI startup task in main.py."""
        settings = get_settings()
        while True:
            try:
                await self._sweep_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # keep the loop alive on transient errors
                pass
            await asyncio.sleep(settings.sweeper_interval_s)


registry = AgentRegistry()
