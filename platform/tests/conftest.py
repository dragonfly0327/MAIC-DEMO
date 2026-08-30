"""Test fixtures. Route the backlog JSONL to a temp dir before app import."""

import os
import tempfile
from pathlib import Path

# Must be set before any ``app.*`` import so get_settings() picks it up.
_TMP = Path(tempfile.mkdtemp(prefix="cx_test_"))
os.environ.setdefault("CX_BACKLOG_DIR", str(_TMP))
os.environ.setdefault("CX_HEARTBEAT_TIMEOUT_S", "1.0")
os.environ.setdefault("CX_SWEEPER_INTERVAL_S", "0.2")
