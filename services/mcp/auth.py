from __future__ import annotations

from contextvars import ContextVar
from typing import Any

import jwt

from .config import settings

current_mcp_context: ContextVar[dict[str, Any]] = ContextVar("mcp_context", default={})


async def verify_jwt_token(token: str) -> dict[str, Any]:
    """Validate Flow JWT and return {workspace_id, user_id, token}."""
    try:
        payload = jwt.decode(token, settings.flow_jwt_secret, algorithms=["HS256"])
        context: dict[str, Any] = {
            "workspace_id": payload.get("workspace_id"),
            "user_id": payload.get("sub"),
            "token": token,
        }
        current_mcp_context.set(context)
        return context
    except jwt.ExpiredSignatureError as e:
        raise ValueError("Token expired") from e
    except jwt.InvalidTokenError as e:
        raise ValueError("Invalid token") from e


def get_current_context() -> dict[str, Any]:
    return current_mcp_context.get()
