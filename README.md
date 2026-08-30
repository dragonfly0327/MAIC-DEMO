# ContinuumX Agentic Platform — Technical Tech Stack & Blueprint

ContinuumX is a secure, multi-tenant agentic platform designed for High-Mix Low-Volume (HMLV) smart manufacturing and semiconductor assembly. It automates the lifecycle from engineering drawings and RFQs to visual bills-of-materials (BOM) extraction, semantic parts matching, cost optimization, and automated shopfloor work instructions.

This repository integrates an intelligence overlay on top of existing factory Manufacturing Execution Systems (MES) and ERPs, incorporating real-time telemetry-driven rescheduling and automated equipment diagnostics.

> **ContinuumXppsLauncher**: ContinuumX Enterprise Solutions Portal for SMEs — the desktop launcher and application suite (BOM, Costing, Cycle Time, NPI, Sourcing, WI, Project Management) that ships alongside this platform.

---

## 1. Key System Features

*   **Autonomous RFQ-to-Work-Instruction Pipeline**: Converts PDF schematics and bills-of-materials into optimized procurement pathways and assembly steps.
*   **Hybrid AI Data Routing**: Routes public data to fast cloud LLMs (Gemini Flash) and sensitive customer drawing IP to local edge VLM nodes (Llama-3-Vision).
*   **Closed-Loop Telemetry & Rescheduling**: Ingests real-time machine sensors (OPC-UA/MQTT) and updates manufacturing schedules dynamically via a Mixed-Integer Linear Programming (MILP) solver when outages or PO rescheduling events happen.
*   **Point-of-Failure Isolation Contract**: Implements a strict boundary contract between teams using a single `transaction_uuid` context state in PostgreSQL.

---

## 2. Platform Planned Tech Stack

The architecture is partitioned into frontend staging, backend logical services, data context memory, security firewalls, and deployment orchestrations.

| Stack Layer | Technologies & Tools | Platform Role & Advantage | Responsibility |
| :--- | :--- | :--- | :--- |
| **Front-End Portal** | • Next.js (React)<br>• Vanilla CSS<br>• HTML5 Semantic tags | Renders the staging dashboard showing side-by-side BOM cards, price diffs, confidence scores, and real-time execution logs. | **Team 2** (UI Design)<br>**Team 1** (UAT feedback) |
| **Backend Core** | • Python 3.10+<br>• FastAPI / Flask Web Framework | Powers stateless logic microservices and handles multi-tenant JSON payloads. | **Team 2** (Logic)<br>**Team 3** (APIs/Routing) |
| **Database & Search** | • PostgreSQL 15+<br>• `pgvector` extension<br>• JSONB memory state columns | pgvector runs cosine similarity queries (> 0.85 threshold) for semantic part matching. JSONB stores active session states. | **Team 3** (Schema & RLS)<br>**Team 2** (Query logic) |
| **AI Orchestration** | • Gemini 3.5 Flash (Cloud API)<br>• Llama-3-Vision (Local GPU)<br>• Embeddings & RAG pipelines | Gemini Flash acts as the fast reasoning brain. Llama-3-Vision parses engineering schematics locally on edge nodes. | **Team 2** (System prompts)<br>**Team 3** (Router & Infra) |
| **Optimization Math** | • PuLP Solver Engine<br>• SciPy Linear Programming | Mixed-Integer Linear Programming (MILP) solver optimizing total sourcing costs under MOQ constraints and machine capacities. | **Team 2** (MILP models) |
| **Document Compiler** | • WeasyPrint / ReportLab | Generates customer quotation files and IPC-A-620 work instructions directly to PDFs, bypassing Excel dependencies. | **Team 2** (PDF engines) |
| **Security & Isolation** | • Postgres Row-Level Security<br>• LLM Security Firewall<br>• Tenant JWT Tokens | RLS prevents cross-tenant data leaks. LLM firewall blocks prompt-injection attempts and outgoing PII leakage. | **Team 3** (Security policies) |
| **Event Logging** | • Redis Broker Queue<br>• Event Backlog Streams | Handles asynchronous events and error backlogs mapped to the transaction UUID for quick diagnostics. | **Team 3** (Broker setup)<br>**Team 2** (Service error pubs) |
| **Edge IoT Integration** | • OPC-UA Protocols<br>• MQTT Telemetry Listeners | Streams live crimper/cutter metrics (heat, vibration, crimp force) to predict tooling wear and trigger auto-rerouting. | **Team 3** (Telemetry agent)<br>**Team 2** (Cost estimator) |
| **ERP / MES Gateway** | • REST API Webhooks<br>• Direct SQL database writes<br>• Headless RPA Workers | Connects to Siemens, SAP, Oracle, or a mock ERP endpoint `/mock-erp` to push work orders or check schedules. | **Team 3** (Gateway integrations) |
| **Infrastructure & CI** | • Docker & Docker-Compose<br>• Systemd Daemons<br>• Ansible/Terraform | Manages container reboots, edge auto-startup on boot, and automated rolling rollbacks if health probes fail. | **Team 3** (DevOps / AIOps) |

---

## 3. Implemented Code

Runnable Team 3 code lives in [platform/](platform/). See [platform/README.md](platform/README.md) for full setup and architecture.

**Phase 1 (implemented): Agent Monitoring Dashboard + encrypted agent-to-agent communication.**

*   **Event Broker** ([platform/app/broker/event_broker.py](platform/app/broker/event_broker.py)) - async pub/sub exposing `publish(channel, payload)` / `subscribe(channel)`, JSONL-persisted backlog, isolated error queues.
*   **Agent Registry** ([platform/app/agents/registry.py](platform/app/agents/registry.py)) - register/heartbeat with self-reported CPU/memory, task counts, and a background sweeper that flips stale agents to `offline` (drives the "server down" signal).
*   **AgentComms** ([platform/app/agents/comms.py](platform/app/agents/comms.py)) - reusable messaging layer Team 2's agents import; encrypts the payload body client-side (`app/security/crypto.py`) while leaving the envelope metadata cleartext so the broker can route and the dashboard can monitor.
*   **Monitoring Dashboard** ([platform/dashboard/](platform/dashboard/)) - live agent health cards, resource meters, fleet status chart, error telemetry, live event log, and a human-in-the-loop approval queue.
*   **Demo Agent** ([platform/agents/demo_agent.py](platform/agents/demo_agent.py)) - integration template exchanging encrypted `hello -> hello_ack -> byebye`.

Quick start:

```bash
cd platform
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app        # dashboard at http://127.0.0.1:8000/
```

Phases 2-3 (Postgres schema + RLS, tenant JWT middleware, LLM firewall, ERP/MES gateway, Docker orchestration + rollback, remote diagnostics) remain planned in [implementation_plan_team3.md](AgenticPlatform/implementation_plan_team3.md).

---

## 4. Project Documentation Directory

To learn more about the implementation guidelines, governance policies, and team tasks, refer to the documents in the [AgenticPlatform](file:///d:/ContinuumX%20Internal/AgenticPlatform/AgenticPlatform) folder:

*   **[Master Implementation Plan](file:///d:/ContinuumX%20Internal/AgenticPlatform/AgenticPlatform/implementation_plan.md)**: Coordinates cross-functional execution.
*   **[Architecture Flowcharts & Diagrams](file:///d:/ContinuumX%20Internal/AgenticPlatform/AgenticPlatform/flowchart.md)**: Visualizes the end-to-end data pipeline, data privacy routing, sequence logs, and deployment profiles.
*   **[Platform Overview](file:///d:/ContinuumX%20Internal/AgenticPlatform/AgenticPlatform/platform_overview.md)**: High-level system architecture, team collaboration matrix, and fail-safe recovery rules.
*   **[Corporate AI Governance Guidelines](file:///d:/ContinuumX%20Internal/AgenticPlatform/AgenticPlatform/ai_governance_guidelines.md)**: Details the safety checkpoints, validation gates, and compliance trails.
*   **[Team 1: Business Operations & Product Mapping](file:///d:/ContinuumX%20Internal/AgenticPlatform/AgenticPlatform/implementation_plan_team1.md)**: Customer requirement schemas and Pilot shadow mode templates.
*   **[Team 2: Sourcing, Costing, & Staging UI](file:///d:/ContinuumX%20Internal/AgenticPlatform/AgenticPlatform/implementation_plan_team2.md)**: Details the VLM parser, semantic matcher, MILP solver, and React UI layout.
*   **[Team 3: Infrastructure, Database, & Security](file:///d:/ContinuumX%20Internal/AgenticPlatform/AgenticPlatform/implementation_plan_team3.md)**: Details event queues, RLS, middleware, WebSocket remote diagnostics, and CI/CD rollbacks.
*   **[30-Day Project Timeline](file:///d:/ContinuumX%20Internal/AgenticPlatform/AgenticPlatform/timeline.md)**: Development milestones and weekly checkpoint gates.
*   **[Pitch Deck Summary](file:///d:/ContinuumX%20Internal/AgenticPlatform/AgenticPlatform/pitch_deck_summary.md)**: Structured presentation outline for direct NotebookLM import.
