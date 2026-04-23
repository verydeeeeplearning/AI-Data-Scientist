"""Bootstrap one backend session from onboarding completion."""

from __future__ import annotations

import uuid
from typing import Protocol

from ds_agent.application.dtos.mission_context_dto import MissionContextDTO
from ds_agent.application.dtos.onboarding_finalize_dto import (
    OnboardingFinalizeRequestDTO,
    OnboardingFinalizeResultDTO,
)
from ds_agent.domain.entities.goal import GoalRecord

_DEFAULT_SESSION_SURFACE = "ws"
_DEFAULT_GOALS_BY_USE_CASE: dict[str, str] = {
    "data_analysis": "Run an exploratory analysis and surface the main findings.",
    "eda": "Run an exploratory analysis and surface the main findings.",
    "reporting": "Prepare a reporting-ready analysis with clear takeaways.",
    "prediction": "Plan a prediction workflow and define the evaluation approach.",
    "dashboard": "Define a dashboard-ready analysis and the metrics to track.",
    "sql_analysis": "Investigate the data with SQL and summarize the key findings.",
    "sql_exploration": "Investigate the data with SQL and summarize the key findings.",
    "kpi_triage": "Triage the weekly KPI movement and recommend the next action.",
    "weekly_kpi_triage": "Triage the weekly KPI movement and recommend the next action.",
    "experiment_compare": "Compare experiment outcomes and quantify the tradeoffs.",
    "ab_test_analysis": "Compare experiment outcomes and quantify the tradeoffs.",
    "deployment_prep": "Prepare a deployment handoff with validation and operational checks.",
    "general": "Define the first data-science mission and expected outcome.",
}


class LookupSessionPort(Protocol):
    def __call__(self, session_id: str) -> object | None: ...


class EnsureSessionPort(Protocol):
    def __call__(self, session_id: str, surface: str) -> object: ...


class GetActiveGoalPort(Protocol):
    def __call__(self, session_id: str) -> GoalRecord | None: ...


class SeedGoalPort(Protocol):
    def __call__(self, session_id: str, message: str) -> object: ...


class GetMissionContextPort(Protocol):
    def __call__(self, session_id: str) -> MissionContextDTO: ...


class GetActiveTaskContractIdPort(Protocol):
    def __call__(self, session_id: str) -> str | None: ...


class CreateTaskContractPort(Protocol):
    def __call__(
        self,
        request: OnboardingFinalizeRequestDTO,
        session_id: str,
        business_goal: str,
    ) -> str: ...


class FinalizeOnboardingUseCase:
    """Create or reuse one session and return a Mission-ready snapshot."""

    def __init__(
        self,
        *,
        lookup_session: LookupSessionPort,
        ensure_session: EnsureSessionPort,
        get_active_goal: GetActiveGoalPort,
        seed_goal: SeedGoalPort,
        get_mission_context: GetMissionContextPort,
        get_active_task_contract_id: GetActiveTaskContractIdPort | None = None,
        create_task_contract: CreateTaskContractPort | None = None,
    ) -> None:
        self._lookup_session = lookup_session
        self._ensure_session = ensure_session
        self._get_active_goal = get_active_goal
        self._seed_goal = seed_goal
        self._get_mission_context = get_mission_context
        self._get_active_task_contract_id = get_active_task_contract_id
        self._create_task_contract = create_task_contract

    def execute(self, request: OnboardingFinalizeRequestDTO) -> OnboardingFinalizeResultDTO:
        session_id = request.session_id or uuid.uuid4().hex[:8]
        created_session = self._lookup_session(session_id) is None
        self._ensure_session(session_id, _DEFAULT_SESSION_SURFACE)

        active_goal = self._get_active_goal(session_id)
        goal_seeded = False
        goal_seed_text = self._resolve_goal_seed(request)
        if active_goal is None and goal_seed_text is not None:
            self._seed_goal(session_id, goal_seed_text)
            goal_seeded = True

        task_id = self._resolve_task_contract_id(
            request=request,
            session_id=session_id,
            active_goal=active_goal,
            goal_seed_text=goal_seed_text,
        )
        mission = self._get_mission_context(session_id)
        return OnboardingFinalizeResultDTO(
            sessionId=session_id,
            createdSession=created_session,
            goalSeeded=goal_seeded,
            taskId=task_id,
            mission=mission,
        )

    @staticmethod
    def _resolve_goal_seed(request: OnboardingFinalizeRequestDTO) -> str | None:
        if request.goal is not None:
            return request.goal

        use_case_id = request.use_case_id or _extract_use_case_id(request.responses)
        if use_case_id is not None:
            default_goal = _DEFAULT_GOALS_BY_USE_CASE.get(use_case_id.strip().lower())
            if default_goal is not None:
                return default_goal

        return request.starter_prompt

    def _resolve_task_contract_id(
        self,
        *,
        request: OnboardingFinalizeRequestDTO,
        session_id: str,
        active_goal: GoalRecord | None,
        goal_seed_text: str | None,
    ) -> str | None:
        if self._get_active_task_contract_id is None or self._create_task_contract is None:
            return None

        existing_task_id = self._get_active_task_contract_id(session_id)
        if existing_task_id is not None:
            return existing_task_id

        business_goal = _resolve_contract_business_goal(
            active_goal=active_goal,
            goal_seed_text=goal_seed_text,
        )
        if business_goal is None:
            return None
        return self._create_task_contract(request, session_id, business_goal)


def _extract_use_case_id(responses: dict[str, object] | None) -> str | None:
    if not isinstance(responses, dict):
        return None

    candidate = responses.get("step1_useCase")
    if candidate is None:
        candidate = responses.get("step1_use_case")
    if candidate is None:
        return None

    normalized = str(candidate).strip()
    return normalized or None


def _resolve_contract_business_goal(
    *,
    active_goal: GoalRecord | None,
    goal_seed_text: str | None,
) -> str | None:
    if active_goal is not None:
        summary = active_goal.summary.strip()
        if summary:
            return summary
        detail = active_goal.detail.strip()
        if detail:
            return detail
    return goal_seed_text
