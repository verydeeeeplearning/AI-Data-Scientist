"""Default authority x action-class matrix for autonomy decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from ds_agent.domain.value_objects.action_class import ActionClass, get_action_class
from ds_agent.domain.value_objects.authority_mode import AuthorityMode


class Verdict(StrEnum):
    """Execution verdict for one action under one authority mode."""

    AUTO = "auto"
    ASK = "ask"
    APPROVE = "approve"
    DUAL = "dual"
    SKIP = "skip"


_DEFAULT_MATRIX: dict[str, dict[AuthorityMode, Verdict]] = {
    "read_sql_gold": {
        AuthorityMode.SHADOW: Verdict.AUTO,
        AuthorityMode.SUPERVISED: Verdict.AUTO,
        AuthorityMode.DELEGATE: Verdict.AUTO,
        AuthorityMode.AUTOPILOT: Verdict.AUTO,
        AuthorityMode.INCIDENT: Verdict.AUTO,
        AuthorityMode.FREEZE: Verdict.AUTO,
    },
    "read_sql_bronze": {
        AuthorityMode.SHADOW: Verdict.AUTO,
        AuthorityMode.SUPERVISED: Verdict.ASK,
        AuthorityMode.DELEGATE: Verdict.ASK,
        AuthorityMode.AUTOPILOT: Verdict.AUTO,
        AuthorityMode.INCIDENT: Verdict.AUTO,
        AuthorityMode.FREEZE: Verdict.AUTO,
    },
    "read_sensitive_table": {
        AuthorityMode.SHADOW: Verdict.SKIP,
        AuthorityMode.SUPERVISED: Verdict.APPROVE,
        AuthorityMode.DELEGATE: Verdict.APPROVE,
        AuthorityMode.AUTOPILOT: Verdict.APPROVE,
        AuthorityMode.INCIDENT: Verdict.APPROVE,
        AuthorityMode.FREEZE: Verdict.APPROVE,
    },
    "read_pii_table": {
        AuthorityMode.SHADOW: Verdict.SKIP,
        AuthorityMode.SUPERVISED: Verdict.APPROVE,
        AuthorityMode.DELEGATE: Verdict.APPROVE,
        AuthorityMode.AUTOPILOT: Verdict.APPROVE,
        AuthorityMode.INCIDENT: Verdict.APPROVE,
        AuthorityMode.FREEZE: Verdict.SKIP,
    },
    "feature_engineering": {
        AuthorityMode.SHADOW: Verdict.AUTO,
        AuthorityMode.SUPERVISED: Verdict.AUTO,
        AuthorityMode.DELEGATE: Verdict.AUTO,
        AuthorityMode.AUTOPILOT: Verdict.AUTO,
        AuthorityMode.INCIDENT: Verdict.AUTO,
        AuthorityMode.FREEZE: Verdict.AUTO,
    },
    "model_training": {
        AuthorityMode.SHADOW: Verdict.AUTO,
        AuthorityMode.SUPERVISED: Verdict.ASK,
        AuthorityMode.DELEGATE: Verdict.AUTO,
        AuthorityMode.AUTOPILOT: Verdict.AUTO,
        AuthorityMode.INCIDENT: Verdict.AUTO,
        AuthorityMode.FREEZE: Verdict.SKIP,
    },
    "artifact_draft": {
        AuthorityMode.SHADOW: Verdict.AUTO,
        AuthorityMode.SUPERVISED: Verdict.AUTO,
        AuthorityMode.DELEGATE: Verdict.AUTO,
        AuthorityMode.AUTOPILOT: Verdict.AUTO,
        AuthorityMode.INCIDENT: Verdict.AUTO,
        AuthorityMode.FREEZE: Verdict.AUTO,
    },
    "jira_create": {
        AuthorityMode.SHADOW: Verdict.SKIP,
        AuthorityMode.SUPERVISED: Verdict.APPROVE,
        AuthorityMode.DELEGATE: Verdict.ASK,
        AuthorityMode.AUTOPILOT: Verdict.AUTO,
        AuthorityMode.INCIDENT: Verdict.AUTO,
        AuthorityMode.FREEZE: Verdict.SKIP,
    },
    "slack_post": {
        AuthorityMode.SHADOW: Verdict.SKIP,
        AuthorityMode.SUPERVISED: Verdict.APPROVE,
        AuthorityMode.DELEGATE: Verdict.APPROVE,
        AuthorityMode.AUTOPILOT: Verdict.ASK,
        AuthorityMode.INCIDENT: Verdict.AUTO,
        AuthorityMode.FREEZE: Verdict.SKIP,
    },
    "email_send": {
        AuthorityMode.SHADOW: Verdict.SKIP,
        AuthorityMode.SUPERVISED: Verdict.APPROVE,
        AuthorityMode.DELEGATE: Verdict.APPROVE,
        AuthorityMode.AUTOPILOT: Verdict.APPROVE,
        AuthorityMode.INCIDENT: Verdict.APPROVE,
        AuthorityMode.FREEZE: Verdict.SKIP,
    },
    "staging_deploy": {
        AuthorityMode.SHADOW: Verdict.SKIP,
        AuthorityMode.SUPERVISED: Verdict.APPROVE,
        AuthorityMode.DELEGATE: Verdict.APPROVE,
        AuthorityMode.AUTOPILOT: Verdict.ASK,
        AuthorityMode.INCIDENT: Verdict.AUTO,
        AuthorityMode.FREEZE: Verdict.SKIP,
    },
    "prod_deploy": {
        AuthorityMode.SHADOW: Verdict.SKIP,
        AuthorityMode.SUPERVISED: Verdict.DUAL,
        AuthorityMode.DELEGATE: Verdict.DUAL,
        AuthorityMode.AUTOPILOT: Verdict.APPROVE,
        AuthorityMode.INCIDENT: Verdict.APPROVE,
        AuthorityMode.FREEZE: Verdict.SKIP,
    },
    "delete_table": {
        AuthorityMode.SHADOW: Verdict.SKIP,
        AuthorityMode.SUPERVISED: Verdict.DUAL,
        AuthorityMode.DELEGATE: Verdict.DUAL,
        AuthorityMode.AUTOPILOT: Verdict.DUAL,
        AuthorityMode.INCIDENT: Verdict.DUAL,
        AuthorityMode.FREEZE: Verdict.SKIP,
    },
    "unknown": {
        AuthorityMode.SHADOW: Verdict.SKIP,
        AuthorityMode.SUPERVISED: Verdict.APPROVE,
        AuthorityMode.DELEGATE: Verdict.APPROVE,
        AuthorityMode.AUTOPILOT: Verdict.APPROVE,
        AuthorityMode.INCIDENT: Verdict.APPROVE,
        AuthorityMode.FREEZE: Verdict.SKIP,
    },
}


@dataclass(frozen=True, slots=True)
class ActionMatrix:
    """Lookup table for authority-mode policy verdicts."""

    matrix: dict[str, dict[AuthorityMode, Verdict]]

    @classmethod
    def default(cls) -> ActionMatrix:
        return cls(matrix={name: dict(values) for name, values in _DEFAULT_MATRIX.items()})

    def lookup(
        self,
        action_class: ActionClass | str,
        authority: AuthorityMode | str,
    ) -> Verdict:
        resolved_action = (
            action_class
            if isinstance(action_class, ActionClass)
            else get_action_class(action_class)
        )
        resolved_authority = AuthorityMode.coerce(authority)
        row = self.matrix.get(resolved_action.name, self.matrix["unknown"])
        return row[resolved_authority]

    def with_overrides(
        self,
        overrides: Mapping[str, Mapping[AuthorityMode | str, Verdict | str]],
    ) -> ActionMatrix:
        """Return a new matrix with override verdicts applied."""

        updated = {name: dict(values) for name, values in self.matrix.items()}
        for action_name, authority_map in overrides.items():
            if action_name not in updated:
                continue
            row = updated[action_name]
            for authority_name, verdict_name in authority_map.items():
                row[AuthorityMode.coerce(authority_name)] = Verdict(str(verdict_name))
        return ActionMatrix(matrix=updated)

    def with_risk_tier_overlay(
        self,
        risk_tier_matrix: Mapping[str, Mapping[AuthorityMode | str, str]],
    ) -> ActionMatrix:
        """Return a new matrix with persisted risk-tier cells applied.

        The persisted matrix stores tier labels, so we translate the tier
        labels into dispatch verdicts before overlaying them on top of the
        current matrix. Unknown actions are ignored so the overlay stays
        compatible with partial drafts.
        """

        updated = {name: dict(values) for name, values in self.matrix.items()}
        for action_name, authority_map in risk_tier_matrix.items():
            if action_name not in updated:
                continue
            row = updated[action_name]
            for authority_name, tier_label in authority_map.items():
                verdict = _coerce_risk_tier_verdict(str(tier_label))
                if verdict is None:
                    continue
                row[AuthorityMode.coerce(authority_name)] = verdict
        return ActionMatrix(matrix=updated)


def _coerce_risk_tier_verdict(value: str) -> Verdict | None:
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in {"t0", "routine", "auto"}:
        return Verdict.AUTO
    if normalized in {"t1", "guarded", "ask"}:
        return Verdict.ASK
    if normalized in {"t2", "sensitive", "approve"}:
        return Verdict.APPROVE
    if normalized in {"t3", "critical", "dual"}:
        return Verdict.DUAL
    try:
        return Verdict(normalized)
    except ValueError:
        return None
