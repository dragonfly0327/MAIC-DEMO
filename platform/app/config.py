"""Central configuration for the Team 3 platform.

All runtime settings resolve from environment variables (prefix ``CX_``) with
sensible development defaults so the service runs with zero external infra.
This replaces the legacy ``config.ini`` lookup used in
``ref/BOM/backlog_api.py``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-relative default so the demo runs without any env setup.
_DEFAULT_BACKLOG_DIR = Path(__file__).resolve().parent.parent / "data"
# Desktop ErrorTelemetryStore / AccuracyTelemetryStore live at repo data/telemetry.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_TELEMETRY_DIR = _REPO_ROOT / "data" / "telemetry"

# Deterministic dev key so encrypt/decrypt works across processes in the demo.
# NEVER use this default in production - override CX_ENCRYPTION_KEY.
_DEV_ENCRYPTION_KEY = "c9V3nUq0Zr8m1kFhVQ2mJ0mYb7yq3nQx1p3l6H8oQ0A="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CX_", env_file=".env", extra="ignore")

    # Application-level payload encryption key (Fernet, url-safe base64, 32 bytes).
    encryption_key: str = _DEV_ENCRYPTION_KEY

    # Shared bearer token guarding agent-facing endpoints (Phase 1 stopgap;
    # real per-tenant JWT + RLS arrives in Phase 2 tenant_middleware.py).
    agent_auth_token: str = "dev-agent-token"

    # Directory where the event backlog JSONL is persisted.
    backlog_dir: Path = _DEFAULT_BACKLOG_DIR

    # An agent is marked offline if no heartbeat is seen within this window.
    heartbeat_timeout_s: float = 15.0

    # How often the background sweeper checks for stale agents.
    sweeper_interval_s: float = 5.0

    # Number of recent events replayed to a dashboard on connect.
    replay_tail: int = 100

    # Desktop telemetry JSON/CSV written by agents/telemetry_tracker.py.
    telemetry_dir: Path = _DEFAULT_TELEMETRY_DIR

    @property
    def backlog_jsonl(self) -> Path:
        return self.backlog_dir / "master_backlog_events.jsonl"

    def fernet(self) -> Fernet:
        return Fernet(self.encryption_key.encode())


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.backlog_dir.mkdir(parents=True, exist_ok=True)
    return settings
