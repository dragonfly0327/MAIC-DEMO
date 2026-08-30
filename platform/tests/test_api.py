"""End-to-end API tests: auth enforcement + addressed encrypted delivery."""

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.models import Envelope
from app.security.crypto import decrypt_payload, encrypt_payload

TOKEN = "dev-agent-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_register_requires_token(client):
    resp = client.post("/agents/register", json={"agent_id": "a1"})
    assert resp.status_code == 401


def test_register_with_token_succeeds(client):
    resp = client.post("/agents/register", json={"agent_id": "a1", "role": "demo"}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["agent_id"] == "a1"


def test_health_ok(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_addressed_message_delivered_and_decryptable(client):
    # agent_b subscribes to its inbound stream, agent_a sends it an encrypted msg.
    with client.websocket_connect(f"/agents/agent_b/stream?token={TOKEN}") as ws:
        env = Envelope(
            **{"from": "agent_a"},
            to="agent_b",
            msg_type="hello",
            encrypted_payload=encrypt_payload({"text": "hi b"}),
            transaction_uuid="tx-9",
        )
        resp = client.post("/agents/send", json=env.model_dump(by_alias=True), headers=AUTH)
        assert resp.status_code == 200

        event = ws.receive_json()
        assert event["event_type"] == "AGENT_MSG"
        assert event["from"] == "agent_a"
        assert event["to"] == "agent_b"
        # Body is encrypted on the wire but decryptable by the recipient.
        assert decrypt_payload(event["encrypted_payload"]) == {"text": "hi b"}


def test_register_with_quality_fields(client):
    resp = client.post(
        "/agents/register",
        json={
            "agent_id": "brain",
            "role": "orchestrator",
            "avg_confidence": 0.91,
            "accuracy_pct": 88.5,
            "reviewed_n": 120,
            "override_n": 4,
            "accuracy_pending": False,
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == "brain"
    assert body["avg_confidence"] == 0.91
    assert body["accuracy_pct"] == 88.5
    assert body["reviewed_n"] == 120
    assert body["accuracy_pending"] is False


def test_report_error_requires_token(client):
    resp = client.post("/agents/errors", json={"agent_id": "brain", "detail": "boom"})
    assert resp.status_code == 401


def test_report_error_appears_in_get_errors(client):
    resp = client.post(
        "/agents/errors",
        json={
            "agent_id": "brain",
            "error_type": "SIMULATED_TEST_ERROR",
            "detail": "pipeline diagnostic",
            "severity": "WARNING",
            "rfq_number": "RS26-8004",
            "module": "LLMGateway",
            "error_id": "ERR_TEST_001",
            "status": "RECOVERED_VIA_FALLBACK",
        },
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["is_error"] is True

    errors = client.get("/errors").json()
    assert any(e.get("error_id") == "ERR_TEST_001" and e.get("is_error") for e in errors)


def test_telemetry_snapshots_ok(client):
    err = client.get("/telemetry/errors")
    assert err.status_code == 200
    assert "recent_incidents" in err.json() or "total_incidents" in err.json()
    acc = client.get("/telemetry/accuracy")
    assert acc.status_code == 200
    body = acc.json()
    assert "audits" in body


def test_approval_create_and_decide(client):
    created = client.post(
        "/approvals",
        json={
            "agent_id": "costing",
            "step_name": "Quote release",
            "summary": "Approve costing summary for RS26-8004",
            "confidence_score": 0.82,
            "transaction_uuid": "RS26-8004",
        },
    )
    assert created.status_code == 200
    item = created.json()
    assert item["status"] == "Pending Review"
    approval_id = item["approval_id"]

    pending = client.get("/approvals?pending_only=true").json()
    assert any(p["approval_id"] == approval_id for p in pending)

    decided = client.post(
        f"/approvals/{approval_id}/decision",
        json={"approved": True},
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "Approved"
    leftover = client.get("/approvals?pending_only=true").json()
    assert all(p["approval_id"] != approval_id for p in leftover)


def test_approval_missing_returns_404(client):
    resp = client.post("/approvals/does-not-exist/decision", json={"approved": False})
    assert resp.status_code == 404


def test_fleet_agents_register_online(client):
    fleet = [
        ("brain", "orchestrator"),
        ("bom", "parser"),
        ("sourcing", "optimizer"),
        ("cycletime", "estimator"),
        ("costing", "calculator"),
        ("npi", "classifier"),
        ("wi", "generator"),
    ]
    for agent_id, role in fleet:
        resp = client.post(
            "/agents/heartbeat",
            json={"agent_id": agent_id, "role": role, "status": "idle"},
            headers=AUTH,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "idle"

    agents = client.get("/agents").json()
    ids = {a["agent_id"] for a in agents}
    assert {a for a, _ in fleet} <= ids
    by_id = {a["agent_id"]: a for a in agents}
    assert by_id["brain"]["status"] == "idle"
    assert by_id["sourcing"]["status"] != "offline"
