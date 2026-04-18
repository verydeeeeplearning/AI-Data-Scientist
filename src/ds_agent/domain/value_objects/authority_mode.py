"""Authority-mode value objects for the autonomy control plane."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class AuthorityTransitionRequirement:
    """Approval gates required to move from one authority mode to another."""

    owner_approvals: int = 0
    certification_required: bool = False
    manual_only: bool = False

    @property
    def is_free(self) -> bool:
        """Return whether the transition is immediately allowed."""

        return (
            self.owner_approvals == 0
            and not self.certification_required
            and not self.manual_only
        )


class AuthorityMode(StrEnum):
    """Runtime authority level delegated to the agent."""

    SHADOW = "shadow"
    SUPERVISED = "supervised"
    DELEGATE = "delegate"
    AUTOPILOT = "autopilot"
    INCIDENT = "incident"
    FREEZE = "freeze"

    @property
    def blocks_external_writes(self) -> bool:
        """Return whether this mode forbids external side effects by default."""

        return self in {AuthorityMode.SHADOW, AuthorityMode.FREEZE}

    @property
    def requires_certification(self) -> bool:
        """Return whether this mode requires a certified mission boundary."""

        return self is AuthorityMode.AUTOPILOT

    @classmethod
    def coerce(cls, value: AuthorityMode | str) -> AuthorityMode:
        """Normalize persisted or user-provided values."""

        if isinstance(value, cls):
            return value
        return cls(str(value).strip().lower())

    @classmethod
    def from_legacy_agent_mode(cls, value: str | None) -> AuthorityMode:
        """Map the legacy 3-mode agent setting onto the new authority axis."""

        normalized = _normalize_legacy_agent_mode(value)
        if normalized == "auto":
            return cls.DELEGATE
        return cls.SUPERVISED

    def transition_requirement(
        self,
        target: AuthorityMode | str,
    ) -> AuthorityTransitionRequirement:
        """Return the policy gate for a transition to ``target``."""

        resolved_target = self.coerce(target)
        if resolved_target is self:
            return AuthorityTransitionRequirement()

        if resolved_target is AuthorityMode.INCIDENT:
            return AuthorityTransitionRequirement(manual_only=True)

        if self is AuthorityMode.FREEZE:
            return AuthorityTransitionRequirement(owner_approvals=1)

        if resolved_target in {AuthorityMode.SHADOW, AuthorityMode.FREEZE}:
            return AuthorityTransitionRequirement()

        if resolved_target is AuthorityMode.AUTOPILOT:
            return AuthorityTransitionRequirement(certification_required=True)

        if (
            self in {AuthorityMode.SHADOW, AuthorityMode.SUPERVISED}
            and resolved_target is AuthorityMode.DELEGATE
        ):
            return AuthorityTransitionRequirement(owner_approvals=1)

        return AuthorityTransitionRequirement()


def _normalize_legacy_agent_mode(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "auto"

    normalized = str(value).strip().lower().replace("_", "-")
    if normalized == "step-by-step":
        return normalized
    if normalized in {"auto", "supervised"}:
        return normalized
    raise ValueError(f"Unsupported legacy agent mode: {value}")
