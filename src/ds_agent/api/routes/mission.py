"""Mission context API endpoints for the Mission Header surface."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ds_agent.api.dependencies import require_session_mutation
from ds_agent.application.dtos.pause_agent_dto import PauseAgentRequestDTO
from ds_agent.application.usecases.pause_agent_usecase import PauseAgentUseCase

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/mission", tags=["mission"])


@router.get("/current")
async def get_current_mission(
    request: Request,
    session_id: Annotated[str, Query(alias="sessionId", min_length=1)],
) -> dict[str, Any]:
    """Return the current Mission Header context for one session."""

    state: AppState = request.app.state.app_state
    mission = state.get_mission_context(session_id)
    return {"mission": mission.model_dump(mode="json", by_alias=True)}  # type: ignore[attr-defined]


@router.post(
    "/pause",
    dependencies=[Depends(require_session_mutation("session", "mutate"))],
)
async def pause_mission(
    request: Request,
    body: PauseAgentRequestDTO,
) -> dict[str, Any]:
    """Pause the active run for one session via the Mission Header."""

    state: AppState = request.app.state.app_state
    if not body.session_id.strip():
        raise HTTPException(status_code=400, detail="sessionId is required")

    async def _abort(*, session_id: str) -> object | None:
        return await state.abort_run(session_id=session_id)

    result = await PauseAgentUseCase(_abort).execute(body)
    state.broadcast_mission_context_update(body.session_id)
    return result.model_dump(mode="json", by_alias=True)
