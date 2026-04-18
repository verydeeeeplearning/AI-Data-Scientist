"""Audience-persona value objects for output adaptation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class AudiencePersonaSpec:
    """Prompt-facing guidance for one audience persona."""

    tone: str
    depth: str
    default_artifacts: tuple[str, ...]
    challenge_level: str
    uncertainty_style: str


class AudiencePersona(StrEnum):
    """Audience profile used to steer the agent's reporting style."""

    JUNIOR_MENTOR = "junior_mentor"
    PEER_DS = "peer_ds"
    SENIOR_STAFF = "senior_staff"
    EXECUTIVE = "executive"
    AUDITOR = "auditor"

    @classmethod
    def coerce(cls, value: AudiencePersona | str) -> AudiencePersona:
        """Normalize persisted or user-provided values."""

        if isinstance(value, cls):
            return value
        return cls(str(value).strip().lower())

    @classmethod
    def from_legacy_agent_mode(cls, value: str | None) -> AudiencePersona:
        """Map the legacy 3-mode agent setting onto the new audience axis."""

        normalized = _normalize_legacy_agent_mode(value)
        if normalized == "step-by-step":
            return cls.JUNIOR_MENTOR
        return cls.PEER_DS

    def spec(self) -> AudiencePersonaSpec:
        """Return the reporting guidance for this persona."""

        return _AUDIENCE_SPECS[self]


_AUDIENCE_SPECS: dict[AudiencePersona, AudiencePersonaSpec] = {
    AudiencePersona.JUNIOR_MENTOR: AudiencePersonaSpec(
        tone="educational and explicit",
        depth="very detailed",
        default_artifacts=("checklist", "annotated_notes", "commented_code"),
        challenge_level="low",
        uncertainty_style="explicit_caveats",
    ),
    AudiencePersona.PEER_DS: AudiencePersonaSpec(
        tone="collegial and concise",
        depth="medium",
        default_artifacts=("reproducible_notebook", "sql", "analysis_appendix"),
        challenge_level="medium",
        uncertainty_style="confidence_intervals",
    ),
    AudiencePersona.SENIOR_STAFF: AudiencePersonaSpec(
        tone="direct and decision-focused",
        depth="focused",
        default_artifacts=("decision_memo", "diff", "risk_summary"),
        challenge_level="high",
        uncertainty_style="confidence_with_caveat",
    ),
    AudiencePersona.EXECUTIVE: AudiencePersonaSpec(
        tone="business-first and brief",
        depth="minimal",
        default_artifacts=("exec_brief", "action_card"),
        challenge_level="decision_focused",
        uncertainty_style="risk_tokens",
    ),
    AudiencePersona.AUDITOR: AudiencePersonaSpec(
        tone="provenance-first and factual",
        depth="very detailed",
        default_artifacts=("audit_trail", "lineage_report", "approval_history"),
        challenge_level="none",
        uncertainty_style="quantified_with_policy_refs",
    ),
}


def _normalize_legacy_agent_mode(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "auto"

    normalized = str(value).strip().lower().replace("_", "-")
    if normalized == "step-by-step":
        return normalized
    if normalized in {"auto", "supervised"}:
        return normalized
    raise ValueError(f"Unsupported legacy agent mode: {value}")
