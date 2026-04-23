from __future__ import annotations

from ds_agent.application.dtos.onboarding_finalize_dto import OnboardingFinalizeRequestDTO
from ds_agent.application.usecases.onboarding_task_contract_adapter import (
    build_task_contract_draft_from_onboarding,
)


def _request(*, use_case_id: str, mode: str) -> OnboardingFinalizeRequestDTO:
    return OnboardingFinalizeRequestDTO.model_validate(
        {
            "sessionId": "session-123",
            "useCaseId": use_case_id,
            "responses": {
                "step1_useCase": use_case_id,
                "step2_data": {"type": "database_deferred"},
                "step4_mode": mode,
                "step5_model": "anthropic/claude-sonnet-4-6",
                "step6_confirmed": True,
            },
        }
    )


def test_build_task_contract_draft_from_onboarding_defaults_weekly_kpi_triage() -> None:
    draft = build_task_contract_draft_from_onboarding(
        request=_request(use_case_id="weekly_kpi_triage", mode="fast"),
        session_id="session-123",
        business_goal="Investigate the weekly activation drop.",
    )

    assert draft.contract_type == "kpi_triage"
    assert draft.mission == "weekly-kpi-triage"
    assert draft.authority is not None
    assert draft.authority.value == "delegate"
    assert draft.audience is not None
    assert draft.audience.value == "senior_staff"
    assert [(item.type, item.audience, item.format) for item in draft.required_deliverables] == [
        ("ds_appendix", "ds_peer", "markdown"),
        ("exec_brief", "executive", "pptx"),
    ]
    assert draft.goal_brief.ds_problem_statement == (
        "Triage the weekly KPI movement, identify the likely driver, and assign the next action."
    )
    assert draft.goal_brief.comparison_baseline == (
        "The prior weekly baseline and the most comparable recent period."
    )
    assert draft.goal_brief.decision_to_make == (
        "Decide whether to escalate, remediate, or monitor the KPI movement."
    )
    assert draft.goal_brief.expected_effort == "S"


def test_build_task_contract_draft_from_onboarding_defaults_ab_test_analysis() -> None:
    draft = build_task_contract_draft_from_onboarding(
        request=_request(use_case_id="ab_test_analysis", mode="controlled"),
        session_id="session-123",
        business_goal="Validate the checkout experiment outcome.",
    )

    assert draft.contract_type == "experiment_compare"
    assert draft.mission == "ab-test-analysis"
    assert draft.authority is not None
    assert draft.authority.value == "supervised"
    assert draft.audience is not None
    assert draft.audience.value == "executive"
    assert [(item.type, item.audience, item.format) for item in draft.required_deliverables] == [
        ("ds_appendix", "ds_peer", "markdown"),
        ("exec_brief", "executive", "pptx"),
    ]
    assert draft.goal_brief.ds_problem_statement == (
        "Validate the A/B test design, quantify the effect size, and prepare the "
        "ship-or-hold recommendation."
    )
    assert draft.goal_brief.comparison_baseline == (
        "The control cohort, pre-launch expectations, and guardrail metrics."
    )
    assert draft.goal_brief.decision_to_make == (
        "Decide whether to ship, iterate, or stop based on the experiment evidence."
    )
    assert draft.goal_brief.expected_effort == "M"
