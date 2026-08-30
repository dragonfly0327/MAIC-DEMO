"""ContinuumX Team 3 platform - FastAPI entrypoint (Phase 1).

Wires together the event broker, agent registry + comms endpoints, monitoring
API, and the human-approval queue, and serves the static operations dashboard.
The agent heartbeat sweeper runs as a background task for the app's lifetime.

Run locally:

    cd platform
    pip install -r requirements.txt
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/ for the dashboard.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agents.registry import registry
from app.agents.routes import router as agents_router
from app.monitoring.routes import router as monitoring_router

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


@asynccontextmanager
async def lifespan(app: FastAPI):
    sweeper = asyncio.create_task(registry.run_sweeper())
    try:
        yield
    finally:
        sweeper.cancel()
        try:
            await asyncio.wait_for(sweeper, timeout=1.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass


app = FastAPI(
    title="ContinuumX Team 3 Platform",
    version="0.1.0",
    description="Agent monitoring dashboard + encrypted agent-to-agent comms.",
    lifespan=lifespan,
)

app.include_router(agents_router)
app.include_router(monitoring_router)


@app.get("/", include_in_schema=False)
async def dashboard_index():
    return FileResponse(DASHBOARD_DIR / "index.html")


# Serve dashboard static assets (js/css) under /static.
if DASHBOARD_DIR.exists():
    app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")
