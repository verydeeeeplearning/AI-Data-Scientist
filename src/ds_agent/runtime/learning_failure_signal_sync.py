"""Sync persisted verifier/shadow outcomes into governed failure-signal warnings."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ds_agent.application.learning.harness_warning_ingestor import HarnessWarningIngestor
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.entities.shadow_comparison import (
    ShadowComparisonItem,
    ShadowComparisonRecord,
)
from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.infrastructure.persistence.shadow_comparison_repo import (
    SqliteShadowComparisonRepository,
)
from ds_agent.infrastructure.persistence.verdict_repo import SqliteVerdictRepository

_NON_PASS_CHECK_STATUSES = frozenset({"warn", "fail", "error"})
_PASSING_MISSION_RESULTS = frozenset({"pass", "passed", "ok", "success"})
_SHADOW_WARNING_TYPE_MAP = {
    "temporal_join_guard": "temporal_join",
    "leakage_detection": "leakage",
    "baseline_guard": "baseline_missing",
    "overfitting_guard": "overfitting",
    "drift_detection": "distribution_drift",
}


class PersistedFailureSignalSync:
    """Replay persisted verifier artifacts into the learning-governance inbox."""

    def __init__(
        self,
        *,
        store: LearningStore,
        workspace_dir: str | Path,
        verdict_repo: SqliteVerdictRepository | None = None,
        shadow_repo: SqliteShadowComparisonRepository | None = None,
    ) -> None:
        workspace = str(Path(workspace_dir))
        self._ingestor = HarnessWarningIngestor(store)
        self._verdict_repo = verdict_repo or SqliteVerdictRepository.for_workspace(workspace)
        self._shadow_repo = shadow_repo or SqliteShadowComparisonRepository.for_workspace(workspace)

    def sync(self, *, limit: int) -> None:
        for verdict in self._verdict_repo.list_recent(limit=limit):
            session_id = _session_id_from_mapping(verdict.metadata)
            for payload in _build_review_verdict_payloads(verdict):
                self._ingestor.ingest(
                    payload,
                    session_id=session_id,
                    run_id=verdict.run_id,
                    surface="review_verdict",
                )

        for record in self._shadow_repo.list_recent(limit=limit):
            for payload in _build_shadow_payloads(record):
                self._ingestor.ingest(
                    payload,
                    session_id=record.session_id,
                    run_id=record.run_id,
                    surface="shadow_mismatch",
                )


def _build_review_verdict_payloads(verdict: ReviewVerdict) -> list[dict[str, Any]]:
    signals: dict[str, dict[str, Any]] = {}

    def add_signal(
        signal_key: object,
        *,
        layer: str | None,
        detail_message: str,
        severity: str,
        fallback_warning_type: str | None = None,
    ) -> None:
        normalized_key = _normalize_signal(signal_key)
        if normalized_key is None:
            return
        warning_type = _review_warning_type(
            normalized_key,
            layer=layer,
            fallback=fallback_warning_type,
        )
        source_ref = f"review_verdict:{verdict.verdict_id}:{normalized_key}"
        signals[source_ref] = {
            "id": source_ref,
            "type": warning_type,
            "severity": _normalize_severity(severity),
            "message": (
                f"Verifier review signaled {normalized_key}"
                if layer is None
                else f"Verifier review signaled {normalized_key} in {layer}"
            ),
            "suggestion": "Inspect the persisted verifier verdict and resolve the recurring issue.",
            "sourceRef": source_ref,
            "failureSourceKind": "review_verdict",
            "failureSignalType": normalized_key,
            "failureSourceRef": verdict.verdict_id,
            "failureSourceCreatedAt": verdict.created_at.isoformat(),
            "detailMessage": detail_message,
        }

    for issue in verdict.blocking_issues:
        add_signal(
            issue.check_id or issue.issue_id or issue.layer or verdict.category,
            layer=issue.layer,
            detail_message=issue.message,
            severity=issue.severity,
            fallback_warning_type=_layer_fallback_warning_type(issue.layer),
        )

    for layer in verdict.layers:
        for check in layer.checks:
            if check.status not in _NON_PASS_CHECK_STATUSES:
                continue
            add_signal(
                check.check_id,
                layer=layer.layer,
                detail_message=check.message,
                severity=_severity_for_check_status(check.status),
                fallback_warning_type=_layer_fallback_warning_type(layer.layer),
            )

    failures = verdict.metadata.get("mission_required_check_failures")
    if isinstance(failures, Iterable) and not isinstance(failures, (str, bytes)):
        for failure in failures:
            add_signal(
                failure,
                layer="policy",
                detail_message=f"Mission required check failed: {failure}",
                severity="high",
                fallback_warning_type="policy_review_issue",
            )

    results = verdict.metadata.get("mission_required_check_results")
    if isinstance(results, Mapping):
        for check_id, status in results.items():
            normalized_status = _normalize_signal(status)
            if normalized_status in _PASSING_MISSION_RESULTS:
                continue
            add_signal(
                check_id,
                layer="policy",
                detail_message=f"Mission required check returned status '{status}'",
                severity="high",
                fallback_warning_type="policy_review_issue",
            )

    if verdict.confidence is not None and verdict.confidence.grade in {"low", "insufficient"}:
        add_signal(
            "confidence_low",
            layer="statistical",
            detail_message=(
                verdict.confidence.rationale or "Verifier confidence remained below target."
            ),
            severity="medium",
            fallback_warning_type="statistical_review_issue",
        )

    return list(signals.values())


def _build_shadow_payloads(record: ShadowComparisonRecord) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for item in record.items:
        if not item.applicable or item.mismatch_kind in {"agreement", "not_applicable"}:
            continue
        warning_type = _shadow_warning_type(item)
        source_ref = (
            f"shadow_mismatch:{record.comparison_id}:{item.comparison_key}:{item.mismatch_kind}"
        )
        payloads.append(
            {
                "id": source_ref,
                "type": warning_type,
                "severity": _severity_for_shadow_item(item),
                "message": _shadow_message(item),
                "suggestion": "Review legacy hook and verifier parity for this recurring mismatch.",
                "sourceRef": source_ref,
                "failureSourceKind": "shadow_mismatch",
                "failureSignalType": item.comparison_key,
                "failureSourceRef": record.comparison_id,
                "failureSourceCreatedAt": record.created_at.isoformat(),
                "mismatchKind": item.mismatch_kind,
                "detailMessage": item.note or _shadow_message(item),
            }
        )
    return payloads


def _review_warning_type(
    signal_key: str,
    *,
    layer: str | None,
    fallback: str | None,
) -> str:
    normalized = signal_key.strip().lower()
    if any(token in normalized for token in ("leakage", "temporal_join", "join_validity")):
        return "temporal_join" if "temporal" in normalized else "leakage"
    if any(token in normalized for token in ("baseline", "control", "benchmark")):
        return "baseline_missing"
    if "overfit" in normalized:
        return "overfitting"
    if any(token in normalized for token in ("drift", "schema", "quality", "sanity")):
        return "distribution_drift" if "drift" in normalized else "sanity_check"
    if any(token in normalized for token in ("pii", "privacy")):
        return "pii_detected"
    if any(token in normalized for token in ("claim", "traceability")):
        return "claim_traceability"
    if any(token in normalized for token in ("policy", "compliance", "approval")):
        return "policy_review_issue"
    if any(token in normalized for token in ("narrative", "writeback")):
        return "narrative_review_issue"
    return fallback or _layer_fallback_warning_type(layer)


def _layer_fallback_warning_type(layer: str | None) -> str:
    if layer == "policy":
        return "policy_review_issue"
    if layer == "narrative":
        return "narrative_review_issue"
    if layer == "data":
        return "data_review_issue"
    return "statistical_review_issue"


def _shadow_warning_type(item: ShadowComparisonItem) -> str:
    return _SHADOW_WARNING_TYPE_MAP.get(item.comparison_key, "sanity_check")


def _shadow_message(item: ShadowComparisonItem) -> str:
    if item.mismatch_kind == "legacy_only":
        return f"Shadow mismatch: legacy {item.comparison_key} triggered but verifier stayed clear"
    return f"Shadow mismatch: verifier flagged {item.comparison_key} but legacy hook stayed clear"


def _severity_for_shadow_item(item: ShadowComparisonItem) -> str:
    if item.comparison_key in {
        "temporal_join_guard",
        "leakage_detection",
        "baseline_guard",
        "overfitting_guard",
    }:
        return "high"
    return "medium"


def _severity_for_check_status(status: str) -> str:
    if status in {"fail", "error"}:
        return "high"
    return "medium"


def _normalize_signal(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or None


def _normalize_severity(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"low", "medium", "high"}:
        return normalized
    if normalized == "critical":
        return "high"
    return "medium"


def _session_id_from_mapping(metadata: Mapping[str, object]) -> str | None:
    for key in ("sessionId", "session_id"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
