"""GET /api/status — agent status endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status")
async def get_status(request: Request) -> dict:
    """Return current agent status (model, mode, sessions, cost)."""
    state: AppState = request.app.state.app_state
    return state.get_status()
