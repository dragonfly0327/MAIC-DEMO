# -*- coding: utf-8 -*-
"""Sync bridge from the Tkinter desktop agents onto the Team 3 platform.

AgentComms is async. Launcher and module workers are sync. This module runs one
asyncio loop on a daemon thread and registers the seven config.ini module agents.
Fails open if the platform process is not running.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from typing import Dict, Optional

if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS") or "__compiled__" in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif "__file__" in globals():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
elif len(sys.argv) > 0 and sys.argv[0] and sys.argv[0] != "-c":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
else:
    BASE_DIR = os.getcwd()

_PLATFORM_DIR = os.path.join(BASE_DIR, "platform")
if os.path.isdir(_PLATFORM_DIR) and _PLATFORM_DIR not in sys.path:
    sys.path.append(_PLATFORM_DIR)

FLEET = (
    ("brain", "orchestrator"),
    ("bom", "parser"),
    ("sourcing", "optimizer"),
    ("cycletime", "estimator"),
    ("costing", "calculator"),
    ("npi", "classifier"),
    ("wi", "generator"),
)

QUALITY_AGENTS = {"brain", "bom"}


def _audit_is_human_reviewed(audit: dict) -> bool:
    status = str(audit.get("verification_status", "")).lower()
    grade = str(audit.get("accuracy_grade", "")).lower()
    amended = int(audit.get("amended_cells_count") or 0)
    if audit.get("is_learned_pattern_applied") and amended == 0:
        return True
    if amended > 0:
        return True
    return "ground truth" in status or "human corrected" in grade or "human_verified" in status


def quality_from_audit(audit: dict) -> dict:
    if not audit:
        return {
            "avg_confidence": 0.0,
            "accuracy_pct": 0.0,
            "reviewed_n": 0,
            "override_n": 0,
            "accuracy_pending": True,
        }
    conf_pct = float(audit.get("ai_confidence_avg_pct") or 0.0)
    human = _audit_is_human_reviewed(audit)
    acc = float(audit.get("overall_accuracy_pct") or 0.0) if human else 0.0
    return {
        "avg_confidence": round(conf_pct / 100.0, 4),
        "accuracy_pct": acc if human else 0.0,
        "reviewed_n": int(audit.get("total_evaluated_cells") or 0),
        "override_n": int(audit.get("amended_cells_count") or 0),
        "accuracy_pending": not human,
    }


class DesktopAgentBridge:
    _instance: Optional["DesktopAgentBridge"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_bridge()
            return cls._instance

    @classmethod
    def instance(cls) -> "DesktopAgentBridge":
        return cls()

    def _init_bridge(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._comms: Dict[str, object] = {}
        self._started = False
        self._base_url = os.environ.get("CX_PLATFORM_URL", "http://127.0.0.1:8000").rstrip("/")
        self._token = os.environ.get("CX_AGENT_AUTH_TOKEN", "dev-agent-token")

    def start_all(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(target=self._run_loop, name="cx-platform-bridge", daemon=True)
        self._thread.start()

    def request_approval(
        self,
        agent_id: str = "costing",
        step_name: str = "review",
        summary: str = "",
        confidence_score: float = 0.0,
        transaction_uuid: Optional[str] = None,
    ) -> Optional[dict]:
        """Fail-open POST onto the dashboard HITL queue."""
        try:
            import urllib.request

            payload = {
                "agent_id": agent_id,
                "step_name": step_name,
                "summary": summary,
                "confidence_score": confidence_score,
                "transaction_uuid": transaction_uuid,
            }
            req = urllib.request.Request(
                f"{self._base_url}/approvals",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            print(f"[PlatformBridge] approval request skipped: {exc}")
            return None

    def set_status(self, agent_id: str, status: str) -> None:
        comms = self._comms.get(agent_id)
        if comms is not None:
            try:
                comms.set_status(status)
            except Exception:
                pass

    def record_task(self, agent_id: str, done: bool = True) -> None:
        comms = self._comms.get(agent_id)
        if comms is None:
            return
        try:
            tasks = getattr(comms, "_tasks", {"queued": 0, "running": 0, "on_hold": 0, "done": 0})
            if done:
                comms.set_tasks(
                    queued=tasks.get("queued", 0),
                    running=max(0, tasks.get("running", 0) - 1),
                    on_hold=tasks.get("on_hold", 0),
                    done=tasks.get("done", 0) + 1,
                )
                comms.set_status("idle")
            else:
                comms.set_tasks(
                    queued=tasks.get("queued", 0),
                    running=tasks.get("running", 0) + 1,
                    on_hold=tasks.get("on_hold", 0),
                    done=tasks.get("done", 0),
                )
                comms.set_status("busy")
        except Exception:
            pass

    def _run_loop(self) -> None:
        try:
            from app.agents.comms import AgentComms
        except Exception as exc:
            print(f"[PlatformBridge] AgentComms unavailable: {exc}")
            self._started = False
            return

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._boot(AgentComms))
            self._loop.run_forever()
        except Exception as exc:
            print(f"[PlatformBridge] loop exited: {exc}")
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _boot(self, AgentComms) -> None:
        for agent_id, role in FLEET:
            comms = AgentComms(
                agent_id=agent_id,
                role=role,
                base_url=self._base_url,
                token=self._token,
            )
            self._comms[agent_id] = comms
            try:
                # Heartbeats first so a down platform still auto-registers later.
                await comms.start(heartbeat_interval_s=5.0)
                await comms.register()
            except Exception as exc:
                print(f"[PlatformBridge] {agent_id} register deferred: {exc}")
        self._refresh_quality()
        self._loop.call_later(8.0, self._schedule_quality)

    def _schedule_quality(self) -> None:
        try:
            self._refresh_quality()
        except Exception:
            pass
        if self._loop and self._loop.is_running():
            self._loop.call_later(8.0, self._schedule_quality)

    def _refresh_quality(self) -> None:
        try:
            from agents.telemetry_tracker import AccuracyTelemetryStore

            audit = AccuracyTelemetryStore().get_latest_audit() or {}
            payload = quality_from_audit(audit)
            for agent_id in QUALITY_AGENTS:
                comms = self._comms.get(agent_id)
                if comms is None:
                    continue
                comms.set_quality(**payload)
        except Exception:
            pass


if __name__ == "__main__":
    print("[PlatformBridge] starting 7-agent fleet heartbeats → http://127.0.0.1:8000/")
    DesktopAgentBridge.instance().start_all()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[PlatformBridge] stopped")
