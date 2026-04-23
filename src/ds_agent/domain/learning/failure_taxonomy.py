"""Failure taxonomy projection for governed failure-signal learning items."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.domain.learning.learning_item import LearningItem

RemediationSurface = Literal["docs_rule", "hook", "verifier_check", "contract_test"]
_VALID_REMEDIATION_SURFACES: frozenset[str] = frozenset(
    {"docs_rule", "hook", "verifier_check", "contract_test"}
)


class FailureClass(StrEnum):
    """Canonical failure classes used by the GC loop."""

    LEAKAGE = "leakage"
    OVERFITTING = "overfitting"
    MISSING_BASELINE = "missing_baseline"
    DATA_QUALITY = "data_quality"
    POLICY = "policy"
    NARRATIVE = "narrative"
    UNCATEGORIZED = "uncategorized"


_WARNING_TYPE_TO_FAILURE_CLASS: dict[str, FailureClass] = {
    "baseline_missing": FailureClass.MISSING_BASELINE,
    "baseline_comparison": FailureClass.MISSING_BASELINE,
    "baseline_guard": FailureClass.MISSING_BASELINE,
    "claim_traceability": FailureClass.NARRATIVE,
    "data_leakage_detection": FailureClass.LEAKAGE,
    "distribution_drift": FailureClass.DATA_QUALITY,
    "join_validity_cardinality": FailureClass.LEAKAGE,
    "leakage": FailureClass.LEAKAGE,
    "narrative_review_issue": FailureClass.NARRATIVE,
    "overfitting": FailureClass.OVERFITTING,
    "overfitting_gap": FailureClass.OVERFITTING,
    "pii_detected": FailureClass.POLICY,
    "pii_redacted": FailureClass.POLICY,
    "policy_review_issue": FailureClass.POLICY,
    "review_gate_missing_verdict": FailureClass.POLICY,
    "review_gate_non_auto_verdict": FailureClass.POLICY,
    "review_gate_missing_run_id": FailureClass.POLICY,
    "review_gate_stale_verdict": FailureClass.POLICY,
    "operator_intervention_forced_transition": FailureClass.POLICY,
    "operator_intervention_patch_override": FailureClass.POLICY,
    "operator_intervention_assumption_edit": FailureClass.POLICY,
    "operator_intervention_unknown": FailureClass.POLICY,
    "sanity_check": FailureClass.DATA_QUALITY,
    "semantic_read_guard": FailureClass.POLICY,
    "semantic_trust": FailureClass.POLICY,
    "semantic_writeback": FailureClass.NARRATIVE,
    "statistical_review_issue": FailureClass.DATA_QUALITY,
    "data_review_issue": FailureClass.DATA_QUALITY,
    "temporal_join": FailureClass.LEAKAGE,
}


class FailureTaxonomyItem(BaseModel):
    """Typed view over one persisted failure-signal learning item."""

    model_config = ConfigDict(frozen=True)

    item_id: str = Field(min_length=1)
    failure_class: FailureClass
    warning_type: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    source_ref: str | None = None
    severity: str = Field(min_length=1)
    message: str = Field(min_length=1)
    recurrence_count: int = Field(default=1, ge=1)
    learning_status: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    session_ids: tuple[str, ...] = Field(default_factory=tuple)
    run_ids: tuple[str, ...] = Field(default_factory=tuple)
    surfaces: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Gap 5D-4: remediation surface tracking
    owner: str | None = None
    remediation_surfaces: list[RemediationSurface] = Field(default_factory=list)
    target_artifact: str | None = None

    @classmethod
    def from_learning_item(cls, item: LearningItem) -> FailureTaxonomyItem:
        """Project one learning item into the failure-taxonomy view."""

        warning_type = _normalized_warning_type(item.metadata)
        message = _warning_message(item)
        return cls(
            item_id=item.item_id,
            failure_class=classify_warning_type(warning_type),
            warning_type=warning_type,
            source_kind=_normalized_source_kind(item.metadata),
            source_ref=_normalize_optional_text(item.metadata.get("failureSourceRef")),
            severity=_warning_severity(item.metadata),
            message=message,
            recurrence_count=_warning_recurrence_count(item.metadata),
            learning_status=item.status.value,
            created_at=item.created_at,
            updated_at=item.updated_at,
            session_ids=_tuple_from_metadata_strings(
                item.metadata,
                list_key="sessionIds",
                fallback_key="sessionId",
                fallback_value=item.source.session_id,
            ),
            run_ids=_tuple_from_metadata_strings(
                item.metadata,
                list_key="runIds",
                fallback_key="runId",
            ),
            surfaces=_tuple_from_metadata_strings(
                item.metadata,
                list_key="surfaces",
                fallback_key="surface",
            ),
            metadata=dict(item.metadata),
            owner=_normalize_optional_text(item.metadata.get("remediationOwner")),
            remediation_surfaces=_remediation_surfaces_from_metadata(item.metadata),
            target_artifact=_normalize_optional_text(item.metadata.get("remediationTargetArtifact")),
        )


def _remediation_surfaces_from_metadata(metadata: dict[str, Any]) -> list[RemediationSurface]:
    """Extract and validate remediation surfaces from item metadata."""
    raw = metadata.get("remediationSurfaces")
    if not isinstance(raw, list):
        raw_single = metadata.get("remediationSurface")
        if isinstance(raw_single, str) and raw_single.strip():
            raw = [raw_single.strip()]
        else:
            return []
    result: list[RemediationSurface] = []
    for entry in raw:
        if isinstance(entry, str) and entry.strip() in _VALID_REMEDIATION_SURFACES:
            result.append(entry.strip())  # type: ignore[arg-type]
    return result


def classify_warning_type(warning_type: str | None) -> FailureClass:
    """Map a governed failure signal type to a canonical failure class."""

    normalized = str(warning_type or "").strip().lower()
    if not normalized:
        return FailureClass.UNCATEGORIZED
    mapped = _WARNING_TYPE_TO_FAILURE_CLASS.get(normalized)
    if mapped is not None:
        return mapped
    if any(token in normalized for token in ("leakage", "temporal_join", "join_validity")):
        return FailureClass.LEAKAGE
    if any(token in normalized for token in ("baseline", "control", "benchmark")):
        return FailureClass.MISSING_BASELINE
    if "overfit" in normalized:
        return FailureClass.OVERFITTING
    if any(token in normalized for token in ("pii", "policy", "privacy", "compliance")):
        return FailureClass.POLICY
    if normalized.startswith("operator_intervention"):
        return FailureClass.POLICY
    if any(token in normalized for token in ("claim", "traceability", "narrative", "writeback")):
        return FailureClass.NARRATIVE
    if any(token in normalized for token in ("drift", "schema", "sanity", "quality")):
        return FailureClass.DATA_QUALITY
    return FailureClass.UNCATEGORIZED


def _normalized_warning_type(metadata: dict[str, Any]) -> str:
    raw = metadata.get("warningType")
    normalized = str(raw or "").strip().lower()
    return normalized or "unknown"


def _normalized_source_kind(metadata: dict[str, Any]) -> str:
    raw = metadata.get("failureSourceKind")
    normalized = str(raw or "").strip().lower()
    return normalized or "harness.warning"


def _warning_message(item: LearningItem) -> str:
    raw_payload = item.metadata.get("rawPayload")
    if isinstance(raw_payload, dict):
        raw_message = raw_payload.get("message")
        if isinstance(raw_message, str) and raw_message.strip():
            return raw_message.strip()
    return item.content.split("\n\nSuggestion:", 1)[0].strip()


def _warning_severity(metadata: dict[str, Any]) -> str:
    raw = metadata.get("severity")
    normalized = str(raw or "").strip().lower()
    return normalized or "medium"


def _warning_recurrence_count(metadata: dict[str, Any]) -> int:
    raw = metadata.get("recurrenceCount")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 1
    return max(1, value)


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _tuple_from_metadata_strings(
    metadata: dict[str, Any],
    *,
    list_key: str,
    fallback_key: str,
    fallback_value: str | None = None,
) -> tuple[str, ...]:
    values: list[str] = []
    raw_list = metadata.get(list_key)
    if isinstance(raw_list, list):
        values.extend(_normalized_strings(raw_list))
    if not values:
        raw_single = metadata.get(fallback_key)
        if isinstance(raw_single, str) and raw_single.strip():
            values.append(raw_single.strip())
    if not values and isinstance(fallback_value, str) and fallback_value.strip():
        values.append(fallback_value.strip())
    return tuple(_dedupe_preserve_order(values))


def _normalized_strings(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if candidate:
            normalized.append(candidate)
    return normalized


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        marker = value.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(value)
    return ordered
