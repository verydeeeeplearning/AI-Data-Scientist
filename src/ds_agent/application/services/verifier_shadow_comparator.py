"""Shadow-mode comparator between legacy hook signals and verifier verdicts."""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from typing import Any

from ds_agent.domain.dtos.verifier_context import VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult, ReviewVerdict
from ds_agent.domain.entities.shadow_comparison import (
    LegacyShadowState,
    ShadowComparisonItem,
    ShadowComparisonRecord,
)
from ds_agent.domain.interfaces.verifier_ports import ShadowComparatorPort

_TRIGGERED_STATUSES = {"warn", "fail", "error"}
_SUPPORTED_SIGNALS: tuple[dict[str, Any], ...] = (
    {
        "comparison_key": "temporal_join_guard",
        "legacy_source": "temporal_join_guard_hook",
        "legacy_event": "harness.warning",
        "legacy_type": "temporal_join",
        "tools": {"feature_engineer", "execute_code", "sql_query"},
        "verifier_targets": ["data_leakage_detection", "join_validity_cardinality"],
        "verifier_filters": {"data_leakage_detection": "temporal_only"},
    },
    {
        "comparison_key": "leakage_detection",
        "legacy_source": "leakage_detection_hook",
        "legacy_event": "harness.warning",
        "legacy_type": "leakage",
        "tools": {"feature_engineer"},
        "verifier_targets": ["data_leakage_detection"],
    },
    {
        "comparison_key": "baseline_guard",
        "legacy_source": "baseline_guard_hook",
        "legacy_event": "harness.warning",
        "legacy_type": "baseline_missing",
        "tools": {"train_model"},
        "verifier_targets": ["baseline_comparison"],
    },
    {
        "comparison_key": "overfitting_guard",
        "legacy_source": "overfitting_detector_hook",
        "legacy_event": "harness.warning",
        "legacy_type": "overfitting",
        "tools": {"train_model", "evaluate_model"},
        "verifier_targets": ["overfitting_gap"],
    },
    {
        "comparison_key": "drift_detection",
        "legacy_source": "drift_detection_hook",
        "legacy_event": "drift.detected",
        "legacy_type": None,
        "tools": {"evaluate_model", "deploy_model"},
        "verifier_targets": ["distribution_drift"],
    },
)


class LegacyHookShadowComparator(ShadowComparatorPort):
    """Compare legacy hook warnings against mapped verifier checks."""

    def compare(
        self,
        ctx: VerifierContext,
        verdict: ReviewVerdict,
    ) -> ShadowComparisonRecord | None:
        normalized_log = [_normalize_run_log_entry(item) for item in ctx.run_log]
        tools_seen = {
            str(item.get("tool"))
            for item in normalized_log
            if str(item.get("event", "")) == "tool.call" and item.get("tool")
        }
        items: list[ShadowComparisonItem] = []
        for spec in _SUPPORTED_SIGNALS:
            items.append(
                self._build_item(
                    spec=spec,
                    run_log=normalized_log,
                    tools_seen=tools_seen,
                    verdict=verdict,
                )
            )
        if not any(item.applicable for item in items):
            return None
        return ShadowComparisonRecord(
            comparison_id=f"SC-{time.time_ns()}",
            verdict_id=verdict.verdict_id,
            task_id=verdict.task_id,
            run_id=verdict.run_id,
            session_id=ctx.task_contract.session_id,
            created_at=verdict.created_at,
            items=items,
        )

    def _build_item(
        self,
        *,
        spec: Mapping[str, Any],
        run_log: Sequence[Mapping[str, Any]],
        tools_seen: set[str],
        verdict: ReviewVerdict,
    ) -> ShadowComparisonItem:
        relevant_legacy = [
            item
            for item in run_log
            if str(item.get("event", "")) == str(spec["legacy_event"])
            and (
                spec["legacy_type"] is None
                or str(item.get("type", "")) == str(spec["legacy_type"])
            )
        ]
        verifier_hits = _find_verifier_hits(
            verdict,
            spec["verifier_targets"],
            spec.get("verifier_filters"),
        )
        applicable = bool(tools_seen.intersection(spec["tools"])) or bool(relevant_legacy)
        legacy_state: LegacyShadowState = "triggered" if relevant_legacy else "clear"
        verifier_state: LegacyShadowState = "triggered" if verifier_hits else "clear"
        return ShadowComparisonItem(
            comparison_key=str(spec["comparison_key"]),
            legacy_source=str(spec["legacy_source"]),
            verifier_targets=list(spec["verifier_targets"]),
            applicable=applicable,
            legacy_state=legacy_state if applicable else "not_applicable",
            verifier_state=verifier_state if applicable else "not_applicable",
            legacy_evidence=[dict(item) for item in relevant_legacy],
            verifier_evidence=verifier_hits,
            note=_build_note(legacy_state, verifier_state, applicable),
        )


def _find_verifier_hits(
    verdict: ReviewVerdict,
    verifier_targets: Sequence[str],
    verifier_filters: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    targets = set(verifier_targets)
    for layer in verdict.layers:
        for check in layer.checks:
            if check.check_id not in targets:
                continue
            if check.status not in _TRIGGERED_STATUSES:
                continue
            if not _matches_verifier_filter(
                check,
                verifier_filters.get(check.check_id) if verifier_filters else None,
            ):
                continue
            hits.append(
                {
                    "layer": layer.layer,
                    "check_id": check.check_id,
                    "status": check.status,
                    "message": check.message,
                }
            )
    return hits


def _matches_verifier_filter(check: CheckResult, filter_name: Any) -> bool:
    if filter_name is None:
        return True
    if str(filter_name) != "temporal_only":
        return True
    temporal_overlap = check.evidence.get("temporal_overlap_rows")
    if temporal_overlap is not None and float(temporal_overlap) > 0:
        return True
    message = check.message.lower()
    return "temporal" in message or "join" in message


def _normalize_run_log_entry(item: Any) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        return {"event": "unknown", "raw": item}
    if "event" in item:
        normalized = dict(item)
        payload = normalized.get("payload")
        if isinstance(payload, Mapping):
            merged = dict(payload)
            merged["event"] = str(normalized["event"])
            for key, value in normalized.items():
                if key not in {"payload"}:
                    merged.setdefault(key, value)
            return merged
        return dict(item)
    return dict(item)


def _build_note(legacy_state: str, verifier_state: str, applicable: bool) -> str | None:
    if not applicable:
        return None
    if legacy_state == verifier_state:
        return "legacy hook and verifier agree"
    if legacy_state == "triggered":
        return "legacy hook warned but verifier stayed clear"
    return "verifier flagged an issue that the legacy hook missed"
