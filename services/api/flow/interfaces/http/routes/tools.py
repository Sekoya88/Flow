from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from flow.infrastructure.tools.registry import all_specs
from flow.interfaces.http.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


@router.get("")
async def list_tools(_user_id: Annotated[UUID, Depends(get_current_user_id)]) -> dict:
    """Return all registered tool specs (metadata only, no run callable)."""
    return {
        "tools": [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters_schema": spec.parameters_schema,
                "required_capabilities": spec.required_capabilities,
            }
            for spec in all_specs()
        ]
    }
