"""Action-class metadata for autonomy policy decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Sensitivity(StrEnum):
    """Sensitivity level of the data touched by an action."""

    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    PII = "pii"


class WriteEffect(StrEnum):
    """Side-effect profile of an action."""

    NONE = "none"
    LOCAL = "local"
    EXTERNAL = "external"
    IRREVERSIBLE = "irreversible"


class CostImpact(StrEnum):
    """Relative cost impact of an action."""

    FREE = "free"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Reversibility(StrEnum):
    """How reversible an action is after execution."""

    REVERSIBLE = "reversible"
    SOFT_REVERSIBLE = "soft_reversible"
    IRREVERSIBLE = "irreversible"


@dataclass(frozen=True, slots=True)
class ActionClass:
    """Normalized policy classification for a candidate action."""

    name: str
    data_sensitivity: Sensitivity
    write_side_effect: WriteEffect
    cost_impact: CostImpact
    reversibility: Reversibility
    audit_required: bool = False

    @property
    def is_read_only(self) -> bool:
        return self.write_side_effect == WriteEffect.NONE


ACTION_CLASS_CATALOG: dict[str, ActionClass] = {
    "read_sql_gold": ActionClass(
        name="read_sql_gold",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.NONE,
        cost_impact=CostImpact.LOW,
        reversibility=Reversibility.REVERSIBLE,
    ),
    "read_sql_bronze": ActionClass(
        name="read_sql_bronze",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.NONE,
        cost_impact=CostImpact.MEDIUM,
        reversibility=Reversibility.REVERSIBLE,
    ),
    "read_sensitive_table": ActionClass(
        name="read_sensitive_table",
        data_sensitivity=Sensitivity.RESTRICTED,
        write_side_effect=WriteEffect.NONE,
        cost_impact=CostImpact.LOW,
        reversibility=Reversibility.REVERSIBLE,
        audit_required=True,
    ),
    "read_pii_table": ActionClass(
        name="read_pii_table",
        data_sensitivity=Sensitivity.PII,
        write_side_effect=WriteEffect.NONE,
        cost_impact=CostImpact.LOW,
        reversibility=Reversibility.REVERSIBLE,
        audit_required=True,
    ),
    "feature_engineering": ActionClass(
        name="feature_engineering",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.LOCAL,
        cost_impact=CostImpact.LOW,
        reversibility=Reversibility.REVERSIBLE,
    ),
    "model_training": ActionClass(
        name="model_training",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.LOCAL,
        cost_impact=CostImpact.MEDIUM,
        reversibility=Reversibility.SOFT_REVERSIBLE,
    ),
    "artifact_draft": ActionClass(
        name="artifact_draft",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.LOCAL,
        cost_impact=CostImpact.FREE,
        reversibility=Reversibility.REVERSIBLE,
    ),
    "jira_create": ActionClass(
        name="jira_create",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.EXTERNAL,
        cost_impact=CostImpact.FREE,
        reversibility=Reversibility.SOFT_REVERSIBLE,
        audit_required=True,
    ),
    "slack_post": ActionClass(
        name="slack_post",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.EXTERNAL,
        cost_impact=CostImpact.FREE,
        reversibility=Reversibility.SOFT_REVERSIBLE,
        audit_required=True,
    ),
    "email_send": ActionClass(
        name="email_send",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.EXTERNAL,
        cost_impact=CostImpact.FREE,
        reversibility=Reversibility.IRREVERSIBLE,
        audit_required=True,
    ),
    "staging_deploy": ActionClass(
        name="staging_deploy",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.EXTERNAL,
        cost_impact=CostImpact.LOW,
        reversibility=Reversibility.SOFT_REVERSIBLE,
        audit_required=True,
    ),
    "prod_deploy": ActionClass(
        name="prod_deploy",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.EXTERNAL,
        cost_impact=CostImpact.HIGH,
        reversibility=Reversibility.IRREVERSIBLE,
        audit_required=True,
    ),
    "delete_table": ActionClass(
        name="delete_table",
        data_sensitivity=Sensitivity.RESTRICTED,
        write_side_effect=WriteEffect.IRREVERSIBLE,
        cost_impact=CostImpact.FREE,
        reversibility=Reversibility.IRREVERSIBLE,
        audit_required=True,
    ),
    "unknown": ActionClass(
        name="unknown",
        data_sensitivity=Sensitivity.INTERNAL,
        write_side_effect=WriteEffect.EXTERNAL,
        cost_impact=CostImpact.MEDIUM,
        reversibility=Reversibility.SOFT_REVERSIBLE,
        audit_required=True,
    ),
}


def get_action_class(name: str) -> ActionClass:
    """Return the catalog entry for ``name`` or the conservative unknown class."""

    return ACTION_CLASS_CATALOG.get(name, ACTION_CLASS_CATALOG["unknown"])
