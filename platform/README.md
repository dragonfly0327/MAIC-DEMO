# ContinuumX Team 3 Platform (Phase 1)

Team 3 owns infrastructure, security, and AIOps for the ContinuumX Agentic
Platform. This package is the runnable Phase 1 scaffold delivering two things:

1. **Agent Monitoring Dashboard** - live agent health/status, task counts,
   resource usage, server up/down, error telemetry, live event log, and a
   human-in-the-loop approval queue.
2. **Encrypted agent-to-agent communication** - a reusable `AgentComms`
   messaging layer that Team 2's agents import to talk to each other, with
   payload bodies encrypted client-side.

Later phases add the full Team 3 infra (Postgres schema + RLS, tenant auth,
LLM firewall, ERP/MES gateway, Docker orchestration, remote diagnostics).

## Architecture

```
Agents (import AgentComms + crypto)          platform/ (FastAPI, content-blind broker)
  agent_a  --register/heartbeat (cpu/mem)-->  Agent Registry --+
  agent_b  --cleartext envelope + ---------->  Event Broker ----+--> WebSocket --> Dashboard
            encrypted body                     (pub/sub + JSONL)      /ws/monitor
  agent_b  <--deliver to agent:agent_b-------  Approvals API ---+
```

The broker only ever sees a **cleartext envelope wrapping an encrypted body**,
so it can route and the dashboard can monitor without exposing sensitive
content. Encryption/decryption happens inside each agent (`app/security/crypto.py`).

## Layout

| Path | Purpose |
| --- | --- |
| `app/config.py` | Env-driven settings (encryption key, backlog dir, timeouts, token) |
| `app/models.py` | Shared contracts: `Envelope`, `AgentInfo`, `ApprovalItem` |
| `app/broker/event_broker.py` | Pub/sub broker; `publish(channel, payload)` / `subscribe(channel)` + JSONL |
| `app/security/crypto.py` | Fernet body-only encryption (cleartext envelope) |
| `app/security/auth.py` | Shared bearer-token guard (Phase 1 stopgap) |
| `app/agents/registry.py` | Agent register/heartbeat + offline sweeper |
| `app/agents/routes.py` | Agent HTTP + WebSocket endpoints |
| `app/agents/comms.py` | Reusable `AgentComms` client library for agents |
| `app/hitl/approvals.py` | Human approval queue |
| `app/monitoring/routes.py` | REST snapshots + `/ws/monitor` firehose |
| `dashboard/` | Static monitoring UI (HTML + JS + Chart.js) |
| `agents/demo_agent.py` | Example agent + integration template for Team 2 |

## Run it

```bash
cd platform
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1) Start the platform + dashboard
uvicorn app.main:app --reload
# open http://127.0.0.1:8000/

# 2) In two more terminals, start two agents
python -m agents.demo_agent --id agent_a --peer agent_b --initiate
python -m agents.demo_agent --id agent_b --peer agent_a
```

You should see both agents appear on the dashboard, heartbeats update their
CPU/memory meters, and an encrypted `hello -> hello_ack -> byebye` exchange flow
through the live event log.

## Configuration

All settings use the `CX_` env prefix (see `app/config.py`):

| Env var | Default | Meaning |
| --- | --- | --- |
| `CX_ENCRYPTION_KEY` | dev key | Fernet key for payload encryption. **Override in production.** |
| `CX_AGENT_AUTH_TOKEN` | `dev-agent-token` | Shared bearer token for agent endpoints |
| `CX_BACKLOG_DIR` | `platform/data` | Where `master_backlog_events.jsonl` is written |
| `CX_HEARTBEAT_TIMEOUT_S` | `15` | Mark an agent offline after this many seconds of silence |

## Tests

```bash
cd platform
pytest
```

## Known gaps (intentional, deferred)

- **Key management**: Phase 1 uses one shared symmetric key. Broker-blind,
  per-recipient keys / KMS + rotation come in Phase 3.
- **`from` is unauthenticated** (spoofable) until sender identity is bound to a key.
- **Delivery is at-most-once fire-and-forget**: offline recipients drop messages
  (still logged). Durable queues/retry are Phase 3.
- **Auth is a shared bearer token**; per-tenant JWT + Postgres RLS is Phase 2.
- **State is in-memory + JSONL, single process**; Postgres is Phase 2, Redis (if
  needed for multi-instance) is Phase 3.
