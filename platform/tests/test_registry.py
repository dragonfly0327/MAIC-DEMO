"""Agent registry heartbeat + offline sweeper tests."""

from datetime import datetime, timedelta, timezone

from app.agents.registry import AgentRegistry
from app.models import HeartbeatIn


async def test_heartbeat_registers_and_updates_status():
    reg = AgentRegistry()
    await reg.heartbeat(HeartbeatIn(
        agent_id="a1",
        status="busy",
        tasks_on_hold=3,
        avg_confidence=0.8,
        accuracy_pct=90.0,
        accuracy_pending=False,
    ))
    agents = await reg.list_agents()
    assert len(agents) == 1
    assert agents[0].status == "busy"
    assert agents[0].tasks_on_hold == 3
    assert agents[0].avg_confidence == 0.8
    assert agents[0].accuracy_pending is False


async def test_sweeper_marks_stale_agent_offline():
    reg = AgentRegistry()
    await reg.heartbeat(HeartbeatIn(agent_id="a1", status="idle"))

    # Simulate a stale heartbeat well beyond the timeout window.
    reg._last_seen["a1"] = datetime.now(timezone.utc) - timedelta(seconds=999)

    flipped = await reg._sweep_once()
    assert "a1" in flipped

    agent = await reg.get("a1")
    assert agent.status == "offline"

    # Idempotent: a second sweep does not re-flip an already-offline agent.
    assert await reg._sweep_once() == []
