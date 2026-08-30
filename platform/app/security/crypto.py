"""Application-level payload encryption for inter-agent messages.

Design decision (Phase 1): we encrypt ONLY the message *body*, never the
envelope metadata. This keeps content confidential in the broker, the JSONL
backlog, and the monitoring dashboard, while still allowing the broker to route
messages and the dashboard/LLM firewall to inspect metadata.

Fernet provides authenticated encryption (AES-128-CBC + HMAC-SHA256), so
tampering is detected on decrypt.

Known limitation: Phase 1 uses a single shared symmetric key. Anyone holding
the key (including the broker, if given it) can decrypt. True broker-blind,
end-to-end confidentiality requires per-recipient/asymmetric keys or a KMS with
rotation - deferred to Phase 3. The envelope ``from`` field is also currently
unauthenticated (spoofable) until sender identity is bound to a key.
"""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class DecryptionError(Exception):
    """Raised when a payload cannot be decrypted or fails authentication."""


def _fernet() -> Fernet:
    return get_settings().fernet()


def encrypt_payload(payload: dict[str, Any]) -> str:
    """Serialize and encrypt a message body, returning a Fernet token string."""
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _fernet().encrypt(raw).decode("utf-8")


def decrypt_payload(token: str) -> dict[str, Any]:
    """Decrypt and deserialize a Fernet token back into the message body."""
    try:
        raw = _fernet().decrypt(token.encode("utf-8"))
    except InvalidToken as exc:  # tampered, wrong key, or malformed
        raise DecryptionError("payload failed authentication/decryption") from exc
    return json.loads(raw.decode("utf-8"))


def generate_key() -> str:
    """Convenience helper to mint a fresh Fernet key for deployment configs."""
    return Fernet.generate_key().decode("utf-8")
