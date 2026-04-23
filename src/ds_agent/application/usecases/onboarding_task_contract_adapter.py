"""Adapt onboarding finalize payloads into task-contract draft DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ds_agent.application.dtos.onboarding_finalize_dto import OnboardingFinalizeRequestDTO
from ds_agent.application.dtos.task_contract import TaskContractDraftDTO
from ds_agent.domain.entities.goal import GoalRecord
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode
from ds_agent.domain.value_objects.use_case_mapping import resolve_use_case

_DELIVERABLE_ID_TO_SPEC: dict[str, dict[str, str]] = {
    "chart_summary": {"type": "dashboard", "audience": "pm", "format": "html"},
    "report": {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
    "notebook": {"type": "notebook", "audience": "ml_engineer", "format": "ipynb"},
    "presentation": {"type": "exec_brief", "audience": "executive", "format": "pptx"},
}


@dataclass(frozen=True, slots=True)
class _GoalBriefTemplate:
    ds_problem_statement: str
    comparison_baseline: str
    decision_to_make: str
    expected_effort: str


_GOAL_BRIEF_TEMPLATES: dict[str, _GoalBriefTemplate] = {
    "data_analysis": _GoalBriefTemplate(
        ds_problem_statement="Perform exploratory analysis and surface the main drivers.",
        comparison_baseline="Descriptive statistics and the current reporting baseline.",
        decision_to_make="Decide which findings merit action or deeper follow-up.",
        expected_effort="S",
    ),
    "reporting": _GoalBriefTemplate(
        ds_problem_statement="Synthesize the analysis into a stakeholder-ready narrative.",
        comparison_baseline="Current reporting outputs and recent period comparisons.",
        decision_to_make="Decide what conclusions and actions should be communicated.",
        expected_effort="S",
    ),
    "prediction": _GoalBriefTemplate(
        ds_problem_statement="Frame the supervised prediction problem and evaluation plan.",
        comparison_baseline="A baseline model and the current heuristic process.",
        decision_to_make="Decide whether a predictive model is viable and what to ship next.",
        expected_effort="M",
    ),
    "dashboard": _GoalBriefTemplate(
        ds_problem_statement="Define the KPIs, slices, and views needed for the dashboard.",
        comparison_baseline="Existing KPI reporting and current dashboard coverage.",
        decision_to_make="Decide which dashboard views and metrics should be prioritized.",
        expected_effort="S",
    ),
    "sql_exploration": _GoalBriefTemplate(
        ds_problem_statement="Investigate the dataset with SQL-oriented analysis.",
        comparison_baseline="Current KPI pulls and known query outputs.",
        decision_to_make="Decide which findings or follow-up queries are needed.",
        expected_effort="S",
    ),
    "weekly_kpi_triage": _GoalBriefTemplate(
        ds_problem_statement=(
            "Triage the weekly KPI movement, identify the likely driver, "
            "and assign the next action."
        ),
        comparison_baseline="The prior weekly baseline and the most comparable recent period.",
        decision_to_make="Decide whether to escalate, remediate, or monitor the KPI movement.",
        expected_effort="S",
    ),
    "ab_test_analysis": _GoalBriefTemplate(
        ds_problem_statement=(
            "Validate the A/B test design, quantify the effect size, "
            "and prepare the ship-or-hold recommendation."
        ),
        comparison_baseline="The control cohort, pre-launch expectations, and guardrail metrics.",
        decision_to_make=(
            "Decide whether to ship, iterate, or stop based on the experiment evidence."
        ),
        expected_effort="M",
    ),
    "general": _GoalBriefTemplate(
        ds_problem_statement="Clarify the first data-science workflow and next analysis step.",
        comparison_baseline="Current qualitative understanding and available descriptive data.",
        decision_to_make="Decide the next best analysis path and expected output.",
        expected_effort="S",
    ),
}


def build_task_contract_draft_from_onboarding(
    *,
    request: OnboardingFinalizeRequestDTO,
    session_id: str,
    business_goal: str,
    active_goal: GoalRecord | None = None,
) -> TaskContractDraftDTO:
    """Build a task-contract draft from the coarse onboarding payload."""

    use_case_id = _resolve_use_case_id(request)
    spec = resolve_use_case(use_case_id)
    resolved_use_case_id = spec.use_case_id
    mode = _resolve_mode(request.responses)

    return TaskContractDraftDTO.model_validate(
        {
            "session_id": session_id,
            "contract_type": spec.contract_type,
            "business_goal": business_goal,
            "goal_brief": _goal_brief_payload(
                business_goal=business_goal,
                use_case_id=resolved_use_case_id,
                active_goal=active_goal,
            ),
            "required_deliverables": _deliverables_payload(
                request.responses,
                spec.default_deliverable_specs,
            ),
            "allowed_data_sources": [],
            "forbidden_data_patterns": [],
            "budget": {},
            "autonomy": {},
            "decision_owner": None,
            "decision_deadline": None,
            "definition_of_done": None,
            "authority": _authority_for_mode(mode, default_authority=spec.default_authority),
            "audience": _default_audience(spec.default_audience),
            "mission": spec.default_mission,
            "created_by": "user",
        }
    )


def _resolve_use_case_id(request: OnboardingFinalizeRequestDTO) -> str:
    if request.use_case_id is not None:
        return request.use_case_id
    responses = request.responses or {}
    candidate = responses.get("step1_useCase")
    if candidate is None:
        candidate = responses.get("step1_use_case")
    if candidate is None:
        return "general"
    value = str(candidate).strip()
    return value or "general"


def _resolve_mode(responses: dict[str, Any] | None) -> str | None:
    if not isinstance(responses, dict):
        return None
    candidate = responses.get("step4_mode")
    if candidate is None:
        return None
    value = str(candidate).strip().lower()
    return value or None


def _goal_brief_payload(
    *,
    business_goal: str,
    use_case_id: str,
    active_goal: GoalRecord | None,
) -> dict[str, str | None]:
    template = _GOAL_BRIEF_TEMPLATES.get(use_case_id, _GOAL_BRIEF_TEMPLATES["general"])
    business_question = active_goal.summary if active_goal is not None else business_goal
    return {
        "business_question": business_question,
        "ds_problem_statement": template.ds_problem_statement,
        "hypothesis": None,
        "comparison_baseline": template.comparison_baseline,
        "decision_to_make": template.decision_to_make,
        "expected_effort": template.expected_effort,
    }


def _deliverables_payload(
    responses: dict[str, Any] | None,
    default_specs: tuple[dict[str, str], ...],
) -> list[dict[str, str]]:
    selected_ids: list[str] = []
    if isinstance(responses, dict):
        raw_selected = responses.get("step3_deliverables")
        if isinstance(raw_selected, list):
            selected_ids = [str(item).strip() for item in raw_selected if str(item).strip()]

    if not selected_ids:
        return [dict(spec) for spec in default_specs]

    deliverables: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for deliverable_id in selected_ids:
        spec = _DELIVERABLE_ID_TO_SPEC.get(deliverable_id)
        if spec is None:
            continue
        signature = (spec["type"], spec["audience"], spec["format"])
        if signature in seen:
            continue
        seen.add(signature)
        deliverables.append(dict(spec))

    if deliverables:
        return deliverables
    return [dict(spec) for spec in default_specs]


def _authority_for_mode(mode: str | None, *, default_authority: str) -> AuthorityMode:
    if mode == "fast":
        return AuthorityMode.DELEGATE
    if mode in {"balanced", "controlled"}:
        return AuthorityMode.SUPERVISED
    return AuthorityMode(default_authority)


def _default_audience(default_audience: AudiencePersona) -> AudiencePersona:
    return AudiencePersona.coerce(default_audience)
