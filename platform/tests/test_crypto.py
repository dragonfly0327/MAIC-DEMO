"""Encryption + envelope confidentiality tests."""

import json

import pytest

from app.models import Envelope
from app.security.crypto import DecryptionError, decrypt_payload, encrypt_payload


def test_encrypt_decrypt_round_trip():
    payload = {"text": "hello there", "n": 42}
    token = encrypt_payload(payload)
    assert token != json.dumps(payload)
    assert decrypt_payload(token) == payload


def test_tampered_token_fails_authentication():
    token = encrypt_payload({"text": "secret"})
    tampered = token[:-4] + "AAAA"
    with pytest.raises(DecryptionError):
        decrypt_payload(tampered)


def test_envelope_metadata_cleartext_body_opaque():
    """The envelope exposes routing metadata but not the payload content."""
    secret = {"drawing_ref": "CONFIDENTIAL-IP-123", "price": 9999}
    env = Envelope(
        **{"from": "agent_a"},
        to="agent_b",
        msg_type="hello",
        encrypted_payload=encrypt_payload(secret),
        transaction_uuid="tx-1",
    )
    wire = env.model_dump(by_alias=True)

    # Metadata is readable for routing/monitoring.
    assert wire["from"] == "agent_a"
    assert wire["to"] == "agent_b"
    assert wire["msg_type"] == "hello"
    assert wire["transaction_uuid"] == "tx-1"

    # Body content is not present in cleartext anywhere in the wire form.
    serialized = json.dumps(wire)
    assert "CONFIDENTIAL-IP-123" not in serialized
    assert "9999" not in serialized

    # But an authorized holder of the key can recover it.
    assert decrypt_payload(wire["encrypted_payload"]) == secret
