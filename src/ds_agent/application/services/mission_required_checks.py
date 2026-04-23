"""Resolve mission-pack required checks against the verifier inventory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ds_agent.domain.entities.mission_pack import MissionPack
from ds_agent.domain.entities.review_verdict import LayerResult

VERIFIER_CHECK_IDS: tuple[str, ...] = (
    "access_scope",
    "baseline_comparison",
    "business_question_confirmed",
    "causal_language_appropriateness",
    "claim_evidence_alignment",
    "class_imbalance_impact",
    "confidence_interval_review",
    "cost_budget_compliance",
    "data_leakage_detection",
    "distribution_drift",
    "effect_size_practical_significance",
    "freshness_sla_compliance",
    "join_validity_cardinality",
    "metric_definition_confirmed",
    "metric_citation_accuracy",
    "multiple_testing_correction",
    "multicollinearity",
    "null_spike_anomaly",
    "overfitting_gap",
    "overstatement_hedge_detection",
    "pii_exposure",
    "power_analysis",
    "query_grain_confirmed",
    "recommendation_feasibility",
    "referential_integrity",
    "retention_policy",
    "risky_action_detection",
    "sample_ratio_mismatch",
    "schema_contract_validation",
    "subgroup_stability",
    "temporal_split_robustness",
    "write_side_effect_preview",
)
REQUIRED_CHECK_ALIASES: dict[str, tuple[str, ...]] = {
    "baseline_compare": ("baseline_comparison",),
    "dashboard_grain_confirmed": ("query_grain_confirmed",),
    "executive_narrative_review": (
        "business_question_confirmed",
        "claim_evidence_alignment",
        "overstatement_hedge_detection",
        "recommendation_feasibility",
    ),
    "causal_assumption_check": ("causal_language_appropriateness",),
    "join_key_validation": ("join_validity_cardinality",),
    "label_leakage": ("data_leakage_detection",),
    "multiple_testing_review": ("multiple_testing_correction",),
    "schema_drift": ("schema_contract_validation",),
    "sensitive_column_review": ("pii_exposure",),
    "temporal_leakage": ("temporal_split_robustness",),
}
_CHECK_STATUS_PRIORITY: dict[str, int] = {
    "error": 4,
    "fail": 3,
    "warn": 2,
    "pass": 1,
    "skipped": 0,
}
_FAILURE_STATUSES = {"error", "fail", "missing"}


class MissionPackLoaderPort(Protocol):
    """Minimal mission-pack loader protocol used by verifier preflight."""

    def try_load(self, name: str) -> MissionPack | None: ...


@dataclass(frozen=True)
class MissionRequiredChecksResolution:
    """Resolved view of one mission pack's required-check contract."""

    mission_name: str
    mission_loaded: bool
    required_checks: tuple[str, ...]
    mapped_required_checks: dict[str, tuple[str, ...]]
    unmapped_required_checks: tuple[str, ...]

    @property
    def resolved_check_ids(self) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for required_check in self.required_checks:
            for check_id in self.mapped_required_checks.get(required_check, ()):
                if check_id in seen:
                    continue
                ordered.append(check_id)
                seen.add(check_id)
        return tuple(ordered)


class MissionRequiredCheckResolver:
    """Translate mission-pack aliases into canonical verifier check ids."""

    def __init__(self, mission_loader: MissionPackLoaderPort | None = None) -> None:
        self._mission_loader = mission_loader

    def resolve_for_mission(
        self,
        mission_name: str | None,
    ) -> MissionRequiredChecksResolution | None:
        if not mission_name:
            return None
        if self._mission_loader is None:
            return MissionRequiredChecksResolution(
                mission_name=mission_name,
                mission_loaded=False,
                required_checks=(),
                mapped_required_checks={},
                unmapped_required_checks=(),
            )
        pack = self._mission_loader.try_load(mission_name)
        if pack is None:
            return MissionRequiredChecksResolution(
                mission_name=mission_name,
                mission_loaded=False,
                required_checks=(),
                mapped_required_checks={},
                unmapped_required_checks=(),
            )
        return self.resolve_pack(pack)

    def resolve_pack(self, pack: MissionPack) -> MissionRequiredChecksResolution:
        mapped: dict[str, tuple[str, ...]] = {}
        unmapped: list[str] = []
        for required_check in pack.required_checks:
            check_ids = _resolve_required_check(required_check)
            if check_ids:
                mapped[required_check] = check_ids
                continue
            unmapped.append(required_check)
        return MissionRequiredChecksResolution(
            mission_name=pack.name,
            mission_loaded=True,
            required_checks=pack.required_checks,
            mapped_required_checks=mapped,
            unmapped_required_checks=tuple(unmapped),
        )


def build_mission_required_check_metadata(
    resolution: MissionRequiredChecksResolution,
    layers: list[LayerResult],
) -> dict[str, object]:
    """Serialize one preflight resolution into verifier verdict metadata."""

    metadata: dict[str, object] = {
        "mission_name": resolution.mission_name,
        "mission_pack_loaded": resolution.mission_loaded,
    }
    if not resolution.mission_loaded:
        return metadata

    check_results = evaluate_required_check_results(resolution, layers)
    metadata["mission_required_checks"] = list(resolution.required_checks)
    metadata["mission_required_check_ids"] = list(resolution.resolved_check_ids)
    metadata["mission_required_check_map"] = {
        required_check: list(check_ids)
        for required_check, check_ids in resolution.mapped_required_checks.items()
    }
    metadata["mission_unmapped_required_checks"] = list(resolution.unmapped_required_checks)
    metadata["mission_required_check_results"] = check_results
    metadata["mission_required_check_failures"] = [
        required_check
        for required_check, status in check_results.items()
        if status in _FAILURE_STATUSES
    ]
    return metadata


def evaluate_required_check_results(
    resolution: MissionRequiredChecksResolution,
    layers: list[LayerResult],
) -> dict[str, str]:
    """Reduce one verifier verdict into per-required-check statuses."""

    observed_statuses: dict[str, str] = {}
    for layer in layers:
        for check in layer.checks:
            observed_statuses[check.check_id] = check.status

    required_results: dict[str, str] = {}
    for required_check in resolution.required_checks:
        mapped_check_ids = resolution.mapped_required_checks.get(required_check)
        if not mapped_check_ids:
            required_results[required_check] = "unmapped"
            continue
        statuses = [
            observed_statuses[check_id]
            for check_id in mapped_check_ids
            if check_id in observed_statuses
        ]
        if not statuses:
            required_results[required_check] = "missing"
            continue
        required_results[required_check] = max(statuses, key=_CHECK_STATUS_PRIORITY.__getitem__)
    return required_results


def _resolve_required_check(required_check: str) -> tuple[str, ...]:
    normalized = required_check.strip().lower()
    if normalized in VERIFIER_CHECK_IDS:
        return (normalized,)
    return REQUIRED_CHECK_ALIASES.get(normalized, ())
