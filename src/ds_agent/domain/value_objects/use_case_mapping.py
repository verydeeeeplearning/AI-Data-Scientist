"""Canonical onboarding use-case mapping shared across backend and Electron."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ds_agent.domain.value_objects.audience_persona import AudiencePersona

DEFAULT_USE_CASE_ID: Final[str] = "general"
ONBOARDING_USE_CASE_IDS: Final[frozenset[str]] = frozenset(
    {
        "data_analysis",
        "reporting",
        "prediction",
        "dashboard",
        "sql_exploration",
        "weekly_kpi_triage",
        "ab_test_analysis",
        "general",
    }
)


@dataclass(frozen=True, slots=True)
class UseCaseSpec:
    """Resolved onboarding defaults for one use-case id."""

    use_case_id: str
    contract_type: str
    default_mission: str | None
    default_authority: str
    default_audience: AudiencePersona
    default_deliverable_specs: tuple[dict[str, str], ...]


USE_CASE_SPECS: Final[dict[str, UseCaseSpec]] = {
    "data_analysis": UseCaseSpec(
        use_case_id="data_analysis",
        contract_type="eda",
        default_mission="data_analysis",
        default_authority="supervised",
        default_audience=AudiencePersona.SENIOR_STAFF,
        default_deliverable_specs=(
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ),
    ),
    "reporting": UseCaseSpec(
        use_case_id="reporting",
        contract_type="reporting",
        default_mission="reporting",
        default_authority="supervised",
        default_audience=AudiencePersona.EXECUTIVE,
        default_deliverable_specs=(
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
        ),
    ),
    "prediction": UseCaseSpec(
        use_case_id="prediction",
        contract_type="prediction",
        default_mission="prediction",
        default_authority="supervised",
        default_audience=AudiencePersona.PEER_DS,
        default_deliverable_specs=(
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            {"type": "ml_handoff_spec", "audience": "ml_engineer", "format": "markdown"},
            {"type": "ds_experiment_note", "audience": "ds_peer", "format": "markdown"},
        ),
    ),
    "dashboard": UseCaseSpec(
        use_case_id="dashboard",
        contract_type="dashboard",
        default_mission="dashboard",
        default_authority="supervised",
        default_audience=AudiencePersona.SENIOR_STAFF,
        default_deliverable_specs=(
            {"type": "dashboard", "audience": "pm", "format": "html"},
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
        ),
    ),
    "sql_exploration": UseCaseSpec(
        use_case_id="sql_exploration",
        contract_type="sql_exploration",
        default_mission="sql_exploration",
        default_authority="delegate",
        default_audience=AudiencePersona.PEER_DS,
        default_deliverable_specs=(
            {"type": "notebook", "audience": "ds_peer", "format": "ipynb"},
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ),
    ),
    "weekly_kpi_triage": UseCaseSpec(
        use_case_id="weekly_kpi_triage",
        contract_type="kpi_triage",
        default_mission="weekly-kpi-triage",
        default_authority="delegate",
        default_audience=AudiencePersona.SENIOR_STAFF,
        default_deliverable_specs=(
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
        ),
    ),
    "ab_test_analysis": UseCaseSpec(
        use_case_id="ab_test_analysis",
        contract_type="experiment_compare",
        default_mission="ab-test-analysis",
        default_authority="supervised",
        default_audience=AudiencePersona.EXECUTIVE,
        default_deliverable_specs=(
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
            {"type": "exec_brief", "audience": "executive", "format": "pptx"},
        ),
    ),
    "general": UseCaseSpec(
        use_case_id="general",
        contract_type="eda",
        default_mission="general",
        default_authority="supervised",
        default_audience=AudiencePersona.SENIOR_STAFF,
        default_deliverable_specs=(
            {"type": "ds_appendix", "audience": "ds_peer", "format": "markdown"},
        ),
    ),
}


def resolve_use_case(use_case_id: str) -> UseCaseSpec:
    """Resolve one onboarding use-case id with a safe fallback."""

    return USE_CASE_SPECS.get(use_case_id, USE_CASE_SPECS[DEFAULT_USE_CASE_ID])
