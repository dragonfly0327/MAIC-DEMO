"""Event broker pub/sub + error routing tests."""

from app.broker.event_broker import EventBroker


async def test_publish_reaches_subscriber():
    broker = EventBroker()
    queue = await broker.subscribe("agents")
    await broker.publish("agents", {"event_type": "HEARTBEAT", "agent_id": "a1"})
    event = await queue.get()
    assert event["event_type"] == "HEARTBEAT"
    assert event["agent_id"] == "a1"
    assert event["channel"] == "agents"


async def test_error_channel_flagged_and_listed():
    broker = EventBroker()
    await broker.publish("team2_errors", {"event_type": "TEAM2_SERVICE_ERROR", "detail": "boom"})
    errors = broker.recent_errors()
    assert len(errors) == 1
    assert errors[0]["is_error"] is True
    assert errors[0]["detail"] == "boom"


async def test_monitor_firehose_receives_all_channels():
    broker = EventBroker()
    monitor = await broker.subscribe("__monitor__")
    await broker.publish("agents", {"event_type": "AGENT_REGISTERED", "agent_id": "x"})
    event = await monitor.get()
    assert event["agent_id"] == "x"
