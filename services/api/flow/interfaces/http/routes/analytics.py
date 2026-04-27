from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from flow.infrastructure.observability.logging import get_logger
from flow.interfaces.http.deps import get_current_user_id
from flow.interfaces.http.schemas import AnalyticsBatchIn

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
logger = get_logger(__name__)


@router.post("/events")
async def post_analytics_events(
    body: AnalyticsBatchIn,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> dict:
    """Lightweight client event sink (logged server-side; no third-party)."""
    for ev in body.events:
        logger.info("analytics.event", user_id=str(user_id), name=ev.name, props=ev.props)
    return {"ok": True, "received": len(body.events)}
