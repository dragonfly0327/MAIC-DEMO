"""Phase 1 auth: a single shared bearer token guarding agent endpoints.

This is an intentional stopgap for the demo. Phase 2 replaces it with
per-tenant JWT validation and Postgres Row-Level Security in
``tenant_middleware.py``.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_agent_token(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {get_settings().agent_auth_token}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing agent token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def token_is_valid(authorization: str | None) -> bool:
    return authorization == f"Bearer {get_settings().agent_auth_token}"
