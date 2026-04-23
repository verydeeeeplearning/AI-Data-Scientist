"""HTTP endpoints for onboarding backend handoff."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

from fastapi import APIRouter, Depends, Request

from ds_agent.api.dependencies import require_session_mutation
from ds_agent.application.dtos.mission_context_dto import MissionContextDTO
from ds_agent.application.dtos.onboarding_finalize_dto import OnboardingFinalizeRequestDTO
from ds_agent.application.usecases.finalize_onboarding_usecase import (
    FinalizeOnboardingUseCase,
)
from ds_agent.application.usecases.onboarding_task_contract_adapter import (
    build_task_contract_draft_from_onboarding,
)
from ds_agent.infrastructure.task_contract_container import build_task_contract_container

if TYPE_CHECKING:
    from ds_agent.api.ws_handler import AppState

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.post(
    "/finalize",
    dependencies=[Depends(require_session_mutation("session", "mutate"))],
)
async def finalize_onboarding(
    request: Request,
    body: OnboardingFinalizeRequestDTO,
) -> dict[str, Any]:
    """Bootstrap or reuse one session for onboarding completion."""

    state: AppState = request.app.state.app_state

    def get_mission_context(session_id: str) -> MissionContextDTO:
        # AppState.get_mission_context accepts optional `latest_run` and
        # `active_agent` kwargs; the use case only ever needs the session
        # variant, so adapt the call here and narrow the return type.
        return cast(MissionContextDTO, state.get_mission_context(session_id))

    create_task_contract = None
    get_active_task_contract_id = None
    if _onboarding_auto_draft_enabled():
        workspace_dir = str(state.config.agent.workspace_dir)
        container = build_task_contract_container(workspace_dir)

        def resolve_active_task_contract_id(session_id: str) -> str | None:
            bundle = container.store.get_active_bundle(session_id)
            if bundle is None:
                return None
            return bundle.contract.task_id

        def create_onboarding_task_contract(
            request_body: OnboardingFinalizeRequestDTO,
            session_id: str,
            business_goal: str,
        ) -> str:
            active_goal = state._goal_store.get_active_goal(session_id)
            draft = build_task_contract_draft_from_onboarding(
                request=request_body,
                session_id=session_id,
                business_goal=business_goal,
                active_goal=active_goal,
            )
            result = container.create.execute(draft)
            return str(result["task_id"])

        get_active_task_contract_id = resolve_active_task_contract_id
        create_task_contract = create_onboarding_task_contract

    usecase = FinalizeOnboardingUseCase(
        lookup_session=state._runtime_sessions.get,
        ensure_session=state._runtime_sessions.ensure,
        get_active_goal=state._goal_store.get_active_goal,
        seed_goal=state._goal_store.ensure_from_message,
        get_mission_context=get_mission_context,
        get_active_task_contract_id=get_active_task_contract_id,
        create_task_contract=create_task_contract,
    )
    result = usecase.execute(body)
    return result.model_dump(mode="json", by_alias=True)


def _onboarding_auto_draft_enabled() -> bool:
    value = os.environ.get("ONBOARDING_AUTO_DRAFT_CONTRACT_V1", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}
