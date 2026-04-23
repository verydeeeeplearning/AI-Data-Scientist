from __future__ import annotations

from ds_agent.application.dtos.mission_context_dto import (
    MissionBudgetDTO,
    MissionConnectionDTO,
    MissionConstraintsDTO,
    MissionContextDTO,
    MissionGoalDTO,
    MissionModelDTO,
    MissionStageDTO,
)
from ds_agent.application.dtos.onboarding_finalize_dto import OnboardingFinalizeRequestDTO
from ds_agent.application.usecases.finalize_onboarding_usecase import (
    FinalizeOnboardingUseCase,
)
from ds_agent.domain.entities.goal import GoalRecord


def _mission_context() -> MissionContextDTO:
    return MissionContextDTO(
        goal=MissionGoalDTO(title="Mission title"),
        constraints=MissionConstraintsDTO(
            language="en",
            requiresApproval=True,
            localOnlyModel=False,
        ),
        stage=MissionStageDTO(current=1, total=4, label="Goal captured"),
        mode="supervised",
        model=MissionModelDTO(primary="anthropic/claude-sonnet-4-6"),
        budget=MissionBudgetDTO(
            spentUsd=0.0,
            limitUsd=10.0,
            elapsedSec=0.0,
            nearLimit=False,
        ),
        connection=MissionConnectionDTO(state="connected"),
    )


def _request() -> OnboardingFinalizeRequestDTO:
    return OnboardingFinalizeRequestDTO.model_validate(
        {
            "sessionId": "session-123",
            "useCaseId": "prediction",
            "starterPrompt": "Predict customer churn next quarter.",
            "responses": {
                "step1_useCase": "prediction",
                "step2_data": {"type": "sample", "sampleId": "builtin:prediction"},
                "step3_deliverables": ["report", "notebook"],
                "step4_mode": "balanced",
                "step5_model": "anthropic/claude-sonnet-4-6",
                "step6_confirmed": True,
            },
        }
    )


def test_finalize_onboarding_creates_task_contract_when_create_port_is_wired() -> None:
    create_calls: list[tuple[str, str]] = []

    use_case = FinalizeOnboardingUseCase(
        lookup_session=lambda session_id: None,
        ensure_session=lambda session_id, surface: {"session_id": session_id, "surface": surface},
        get_active_goal=lambda session_id: None,
        seed_goal=lambda session_id, message: {"session_id": session_id, "message": message},
        get_mission_context=lambda session_id: _mission_context(),
        get_active_task_contract_id=lambda session_id: None,
        create_task_contract=lambda request, session_id, business_goal: (
            create_calls.append((session_id, business_goal)) or "TC-100"
        ),
    )

    result = use_case.execute(_request())

    assert result.task_id == "TC-100"
    assert create_calls == [
        ("session-123", "Plan a prediction workflow and define the evaluation approach.")
    ]


def test_finalize_onboarding_reuses_existing_task_contract_before_creating() -> None:
    create_calls: list[str] = []

    use_case = FinalizeOnboardingUseCase(
        lookup_session=lambda session_id: object(),
        ensure_session=lambda session_id, surface: {"session_id": session_id, "surface": surface},
        get_active_goal=lambda session_id: None,
        seed_goal=lambda session_id, message: {"session_id": session_id, "message": message},
        get_mission_context=lambda session_id: _mission_context(),
        get_active_task_contract_id=lambda session_id: "TC-existing",
        create_task_contract=lambda request, session_id, business_goal: (
            create_calls.append(session_id) or "TC-new"
        ),
    )

    result = use_case.execute(_request())

    assert result.task_id == "TC-existing"
    assert create_calls == []


def test_finalize_onboarding_uses_existing_goal_text_for_new_contract() -> None:
    observed_business_goals: list[str] = []
    existing_goal = GoalRecord(
        goal_id="goal-1",
        session_id="session-123",
        summary="Investigate churn drivers already agreed with the user.",
        detail="Investigate churn drivers already agreed with the user.",
    )

    use_case = FinalizeOnboardingUseCase(
        lookup_session=lambda session_id: object(),
        ensure_session=lambda session_id, surface: {"session_id": session_id, "surface": surface},
        get_active_goal=lambda session_id: existing_goal,
        seed_goal=lambda session_id, message: {"session_id": session_id, "message": message},
        get_mission_context=lambda session_id: _mission_context(),
        get_active_task_contract_id=lambda session_id: None,
        create_task_contract=lambda request, session_id, business_goal: (
            observed_business_goals.append(business_goal) or "TC-101"
        ),
    )

    result = use_case.execute(
        OnboardingFinalizeRequestDTO.model_validate(
            {
                "sessionId": "session-123",
                "goal": "Replace the goal on retry.",
                "useCaseId": "prediction",
            }
        )
    )

    assert result.goal_seeded is False
    assert result.task_id == "TC-101"
    assert observed_business_goals == ["Investigate churn drivers already agreed with the user."]


def test_finalize_onboarding_seeds_weekly_kpi_goal_when_use_case_has_no_explicit_goal() -> None:
    seeded_messages: list[str] = []

    use_case = FinalizeOnboardingUseCase(
        lookup_session=lambda session_id: None,
        ensure_session=lambda session_id, surface: {"session_id": session_id, "surface": surface},
        get_active_goal=lambda session_id: None,
        seed_goal=lambda session_id, message: seeded_messages.append(message),
        get_mission_context=lambda session_id: _mission_context(),
    )

    result = use_case.execute(
        OnboardingFinalizeRequestDTO.model_validate(
            {
                "sessionId": "session-weekly",
                "useCaseId": "weekly_kpi_triage",
            }
        )
    )

    assert result.goal_seeded is True
    assert seeded_messages == ["Triage the weekly KPI movement and recommend the next action."]


def test_finalize_onboarding_seeds_ab_test_goal_when_use_case_has_no_explicit_goal() -> None:
    seeded_messages: list[str] = []

    use_case = FinalizeOnboardingUseCase(
        lookup_session=lambda session_id: None,
        ensure_session=lambda session_id, surface: {"session_id": session_id, "surface": surface},
        get_active_goal=lambda session_id: None,
        seed_goal=lambda session_id, message: seeded_messages.append(message),
        get_mission_context=lambda session_id: _mission_context(),
    )

    result = use_case.execute(
        OnboardingFinalizeRequestDTO.model_validate(
            {
                "sessionId": "session-ab-test",
                "useCaseId": "ab_test_analysis",
            }
        )
    )

    assert result.goal_seeded is True
    assert seeded_messages == ["Compare experiment outcomes and quantify the tradeoffs."]
