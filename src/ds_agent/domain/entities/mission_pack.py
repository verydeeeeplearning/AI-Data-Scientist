"""Mission pack entities for the autonomy control plane."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ds_agent.domain.entities.certification import CertificationSpec
from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode

_VALID_OVERRIDE_VERDICTS = frozenset({"auto", "ask", "approve", "dual", "skip"})
_MISSION_DOMAIN_KEYS = (
    "data_domain",
    "domain",
    "source_domain",
    "business_domain",
    "target_schema",
    "schema",
    "schema_name",
)


def _validate_string_items(values: tuple[str, ...], *, field_name: str, allow_empty: bool) -> None:
    if not allow_empty and not values:
        raise ValueError(f"{field_name} must contain at least one item.")
    for item in values:
        if not item.strip():
            raise ValueError(f"{field_name} entries must be non-empty strings.")


class MissionBoundary(BaseModel):
    """Boundary rules declared by one mission pack."""

    model_config = ConfigDict(frozen=True)

    allowed_data_domains: tuple[str, ...] = Field(default_factory=tuple)
    required_semantic_metrics: tuple[str, ...] = Field(default_factory=tuple)
    allowed_action_classes: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_boundary(self) -> MissionBoundary:
        _validate_string_items(
            self.allowed_data_domains,
            field_name="allowed_data_domains",
            allow_empty=False,
        )
        _validate_string_items(
            self.required_semantic_metrics,
            field_name="required_semantic_metrics",
            allow_empty=True,
        )
        _validate_string_items(
            self.allowed_action_classes,
            field_name="allowed_action_classes",
            allow_empty=True,
        )
        return self


class MissionPack(BaseModel):
    """Typed representation of one YAML-backed mission definition."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    version: int = Field(ge=1)
    summary: str = Field(min_length=1)
    authority_default: AuthorityMode | None = None
    audience_default: AudiencePersona | None = None
    skills_required: tuple[str, ...] = Field(default_factory=tuple)
    boundary: MissionBoundary
    required_checks: tuple[str, ...] = Field(default_factory=tuple)
    required_artifacts: tuple[str, ...] = Field(default_factory=tuple)
    required_delivery_channels: tuple[str, ...] = Field(default_factory=tuple)
    auto_escalate_when: tuple[str, ...] = Field(default_factory=tuple)
    success_criteria: tuple[str, ...] = Field(default_factory=tuple)
    action_policy_overrides: dict[str, dict[str, str]] = Field(default_factory=dict)
    certification: CertificationSpec | None = None

    @model_validator(mode="after")
    def _validate_invariants(self) -> MissionPack:
        _validate_string_items(
            self.skills_required,
            field_name="skills_required",
            allow_empty=True,
        )
        _validate_string_items(
            self.required_checks,
            field_name="required_checks",
            allow_empty=False,
        )
        _validate_string_items(
            self.required_artifacts,
            field_name="required_artifacts",
            allow_empty=False,
        )
        _validate_string_items(
            self.required_delivery_channels,
            field_name="required_delivery_channels",
            allow_empty=True,
        )
        _validate_string_items(
            self.auto_escalate_when,
            field_name="auto_escalate_when",
            allow_empty=True,
        )
        _validate_string_items(
            self.success_criteria,
            field_name="success_criteria",
            allow_empty=False,
        )
        for action_name, overrides in self.action_policy_overrides.items():
            if not action_name.strip():
                raise ValueError("action_policy_overrides keys must be non-empty strings.")
            for authority, verdict in overrides.items():
                if not authority.strip():
                    raise ValueError(
                        "action_policy_overrides authority keys must be non-empty strings."
                    )
                if verdict not in _VALID_OVERRIDE_VERDICTS:
                    raise ValueError(f"Unsupported mission override verdict: {verdict!r}.")
        return self

    def policy_override(
        self,
        action_class: str,
        authority: AuthorityMode | str,
    ) -> str | None:
        """Return a mission-local verdict override for one action and authority."""

        overrides = self.action_policy_overrides.get(action_class, {})
        return overrides.get(AuthorityMode.coerce(authority).value)

    def is_within_boundary(
        self,
        action_class: str,
        arguments: Mapping[str, object] | None = None,
    ) -> bool:
        """Return whether the candidate stays inside the declared mission boundary."""

        if (
            self.boundary.allowed_action_classes
            and action_class not in self.boundary.allowed_action_classes
        ):
            return False

        domain = _extract_data_domain(arguments)
        if domain is None:
            return True
        return domain in self.boundary.allowed_data_domains


def _extract_data_domain(arguments: Mapping[str, object] | None) -> str | None:
    if arguments is None:
        return None

    for key in _MISSION_DOMAIN_KEYS:
        raw = arguments.get(key)
        if raw is None:
            continue
        value = str(raw).strip().lower()
        if value:
            return value
    return None
