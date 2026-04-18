"""Usage summary HTTP endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Query, Request

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary")
async def get_usage_summary(
    request: Request,
    actor_id: str = Query(default="local-user", alias="actorId"),
    session_id: str | None = Query(default=None, alias="sessionId"),
) -> dict[str, object]:
    """Return one actor's usage dashboard summary."""
    state: AppState = request.app.state.app_state
    return state.get_usage_summary(actor_id=actor_id, session_id=session_id)
