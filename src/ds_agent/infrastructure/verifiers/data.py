"""Data verifier layer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from ds_agent.application.services.drift_analyzer import DriftAnalyzer
from ds_agent.domain.dtos.verifier_context import VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult, CheckStatus, LayerResult
from ds_agent.domain.interfaces.verifier_ports import DataCheck, DataVerifierPort
from ds_agent.infrastructure.verifiers.common import (
    aggregate_layer,
    artifact,
    coerce_frame,
    elapsed_ms,
    safe_run_check,
)


class SchemaContractValidationCheck:
    """Validate observed data against the declared schema contract."""

    name = "schema_contract_validation"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        frame = coerce_frame(artifact(ctx, "current_df", "observed_df", "train_df"))
        schema = artifact(ctx, "data_schema")
        if frame is None or not isinstance(schema, Mapping):
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="schema contract inputs are unavailable",
                duration_ms=elapsed_ms(start),
            )

        missing_required: list[str] = []
        missing_optional: list[str] = []
        type_mismatches: dict[str, dict[str, str]] = {}
        for column, spec in schema.items():
            column_name = str(column)
            details = spec if isinstance(spec, Mapping) else {"dtype": spec}
            required = bool(details.get("required", True))
            if column_name not in frame.columns:
                if required:
                    missing_required.append(column_name)
                else:
                    missing_optional.append(column_name)
                continue
            expected_dtype = details.get("dtype")
            if expected_dtype and not self._matches_dtype(frame[column_name], str(expected_dtype)):
                type_mismatches[column_name] = {
                    "expected": str(expected_dtype),
                    "observed": str(frame[column_name].dtype),
                }

        evidence = {
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "type_mismatches": type_mismatches,
        }
        if missing_required or type_mismatches:
            status: CheckStatus = "fail"
            score = 0.0
            message = "required schema contract mismatches detected"
        elif missing_optional:
            status = "warn"
            score = 0.55
            message = "optional schema fields are missing"
        else:
            status = "pass"
            score = 1.0
            message = "schema contract matches observed data"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Refresh the schema contract or fix the upstream extract."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )

    @staticmethod
    def _matches_dtype(series: pd.Series, expected: str) -> bool:
        observed = str(series.dtype).lower()
        expected_lower = expected.lower()
        if expected_lower in observed:
            return True
        if expected_lower in {"int", "int64", "integer"}:
            return bool(pd.api.types.is_integer_dtype(series))
        if expected_lower in {"float", "float64", "double"}:
            return bool(pd.api.types.is_float_dtype(series))
        if expected_lower in {"str", "string", "object"}:
            return bool(pd.api.types.is_string_dtype(series)) or observed == "object"
        if expected_lower in {"bool", "boolean"}:
            return bool(pd.api.types.is_bool_dtype(series))
        if expected_lower.startswith("datetime"):
            return bool(pd.api.types.is_datetime64_any_dtype(series))
        return False


class FreshnessAndSlaCheck:
    """Ensure the latest data timestamp satisfies SLA constraints."""

    name = "freshness_sla_compliance"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        frame = coerce_frame(artifact(ctx, "current_df", "observed_df", "train_df"))
        temporal_column = artifact(ctx, "temporal_column")
        sla_seconds = artifact(ctx, "sla_max_staleness_seconds")
        reference_now = artifact(ctx, "reference_now")
        if frame is None or not temporal_column or sla_seconds is None or reference_now is None:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="freshness SLA inputs are unavailable",
                duration_ms=elapsed_ms(start),
            )

        if temporal_column not in frame.columns:
            return CheckResult(
                check_id=self.name,
                status="fail",
                score=0.0,
                evidence={"temporal_column": temporal_column},
                message="temporal column missing from observed data",
                duration_ms=elapsed_ms(start),
            )
        timestamps = pd.to_datetime(frame[temporal_column], errors="coerce").dropna()
        if timestamps.empty:
            return CheckResult(
                check_id=self.name,
                status="fail",
                score=0.0,
                evidence={"temporal_column": temporal_column},
                message="temporal column contains no valid timestamps",
                duration_ms=elapsed_ms(start),
            )

        latest = timestamps.max()
        now = pd.Timestamp(reference_now)
        staleness_seconds = float((now - latest).total_seconds())
        sla_limit = float(sla_seconds)
        evidence = {
            "latest_timestamp": latest.isoformat(),
            "reference_now": now.isoformat(),
            "staleness_seconds": staleness_seconds,
            "sla_max_staleness_seconds": sla_limit,
        }
        if staleness_seconds > sla_limit:
            status: CheckStatus = "fail"
            score = 0.0
            message = "data freshness exceeds SLA"
        elif staleness_seconds > sla_limit * 0.8:
            status = "warn"
            score = 0.55
            message = "data freshness is approaching SLA limit"
        else:
            status = "pass"
            score = 1.0
            message = "data freshness is within SLA"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Refresh the upstream extract or reduce freshness claims."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class NullSpikeAnomalyCheck:
    """Compare current null ratios against a baseline profile."""

    name = "null_spike_anomaly"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        frame = coerce_frame(artifact(ctx, "current_df", "observed_df", "train_df"))
        profile = artifact(ctx, "data_profile")
        if frame is None or not isinstance(profile, Mapping):
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="null anomaly inputs are unavailable",
                duration_ms=elapsed_ms(start),
            )

        columns_profile = profile.get("columns", profile)
        fail_columns: list[str] = []
        warn_columns: list[str] = []
        deltas: dict[str, dict[str, float]] = {}
        for column, spec in columns_profile.items():
            column_name = str(column)
            if column_name not in frame.columns or not isinstance(spec, Mapping):
                continue
            baseline = float(spec.get("null_ratio_mean", spec.get("null_ratio", 0.0)))
            std = float(spec.get("null_ratio_std", 0.0))
            threshold = baseline + (2 * std)
            current = float(frame[column_name].isna().mean())
            deltas[column_name] = {
                "baseline": baseline,
                "threshold": threshold,
                "current": current,
            }
            if current <= threshold:
                continue
            required = bool(spec.get("required", True))
            if required:
                fail_columns.append(column_name)
            else:
                warn_columns.append(column_name)

        evidence = {"columns": deltas}
        if fail_columns:
            status: CheckStatus = "fail"
            score = 0.0
            message = f"null spike on required columns: {', '.join(fail_columns[:3])}"
        elif warn_columns:
            status = "warn"
            score = 0.55
            message = f"null spike on optional columns: {', '.join(warn_columns[:3])}"
        else:
            status = "pass"
            score = 1.0
            message = "null ratios are within baseline tolerance"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Investigate upstream missingness before trusting downstream metrics."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class JoinValidityCardinalityCheck:
    """Review join events for unexplained row-count inflation."""

    name = "join_validity_cardinality"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        run_log = artifact(ctx, "run_log", default=[])
        join_events = [
            event
            for event in run_log
            if isinstance(event, Mapping) and str(event.get("type", "")).lower() == "join"
        ]
        if not join_events:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="join events are unavailable",
                duration_ms=elapsed_ms(start),
            )

        max_ratio = 1.0
        for event in join_events:
            pre = float(event.get("pre_row_count", 0) or 0)
            post = float(event.get("post_row_count", 0) or 0)
            if pre <= 0:
                continue
            ratio = post / pre
            max_ratio = max(max_ratio, ratio)

        evidence = {
            "join_events": [dict(event) for event in join_events],
            "max_row_ratio": max_ratio,
        }
        if max_ratio >= 2.0:
            status: CheckStatus = "fail"
            score = 0.0
            message = f"join row count inflated {max_ratio:.2f}x"
        elif max_ratio >= 1.05:
            status = "warn"
            score = 0.55
            message = f"join row count changed materially ({max_ratio:.2f}x)"
        else:
            status = "pass"
            score = 1.0
            message = "join row counts match expected cardinality"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Audit join keys and confirm expected cardinality."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class DistributionDriftCheck:
    """Reuse DriftAnalyzer to assess PSI-based drift."""

    name = "distribution_drift"
    version = "1"

    def __init__(self, analyzer: DriftAnalyzer | None = None) -> None:
        self._analyzer = analyzer or DriftAnalyzer()

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        reference = artifact(ctx, "reference_df", "train_df")
        current = artifact(ctx, "current_df", "observed_df")
        if reference is None or current is None:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="reference/current frames are unavailable",
                duration_ms=elapsed_ms(start),
            )

        report = self._analyzer.analyze(
            reference,
            current,
            features=artifact(ctx, "drift_features"),
        )
        psi_metrics = [metric for metric in report.metrics if metric.metric_type == "PSI"]
        max_psi = max((metric.value for metric in psi_metrics), default=0.0)
        evidence = {
            "overall_status": report.overall_status,
            "top_drifting_features": report.top_drifting_features,
            "max_psi": max_psi,
        }
        if max_psi > 0.25:
            status: CheckStatus = "fail"
            score = 0.0
            message = f"distribution drift exceeds fail threshold (PSI={max_psi:.3f})"
        elif max_psi > 0.10:
            status = "warn"
            score = 0.55
            message = f"distribution drift detected (PSI={max_psi:.3f})"
        else:
            status = "pass"
            score = 1.0
            message = "distribution drift is within tolerance"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Rebaseline the model or investigate the shifted features."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class ReferentialIntegrityCheck:
    """Verify orphan rates for declared foreign-key checks."""

    name = "referential_integrity"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        checks = artifact(ctx, "referential_checks")
        if not isinstance(checks, Sequence) or isinstance(checks, (str, bytes)):
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="referential checks are unavailable",
                duration_ms=elapsed_ms(start),
            )

        orphan_rates: list[dict[str, Any]] = []
        max_orphan_rate = 0.0
        for check in checks:
            if not isinstance(check, Mapping):
                continue
            orphan_rate = check.get("orphan_rate")
            if orphan_rate is None:
                orphan_rate = self._compute_orphan_rate(check)
            rate = float(orphan_rate)
            max_orphan_rate = max(max_orphan_rate, rate)
            orphan_rates.append(
                {
                    "name": str(check.get("name", check.get("foreign_key", "fk"))),
                    "orphan_rate": rate,
                }
            )

        evidence = {"checks": orphan_rates, "max_orphan_rate": max_orphan_rate}
        if max_orphan_rate > 0.01:
            status: CheckStatus = "fail"
            score = 0.0
            message = "orphan rate exceeds referential integrity threshold"
        elif max_orphan_rate >= 0.001:
            status = "warn"
            score = 0.55
            message = "minor orphan population detected"
        else:
            status = "pass"
            score = 1.0
            message = "referential integrity looks clean"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint=(
                "Repair foreign-key gaps before downstream joins."
                if status != "pass"
                else None
            ),
            duration_ms=elapsed_ms(start),
        )

    @staticmethod
    def _compute_orphan_rate(check: Mapping[str, Any]) -> float:
        child = coerce_frame(check.get("child_df"))
        parent = coerce_frame(check.get("parent_df"))
        foreign_key = check.get("foreign_key")
        parent_key = check.get("parent_key")
        if child is None or parent is None or not foreign_key or not parent_key:
            return 0.0
        valid_child = child[child[str(foreign_key)].notna()]
        if valid_child.empty:
            return 0.0
        parent_values = set(parent[str(parent_key)].dropna().tolist())
        orphan_count = int((~valid_child[str(foreign_key)].isin(parent_values)).sum())
        return orphan_count / len(valid_child)


class DataVerifier(DataVerifierPort):
    """Run the data verifier layer deterministically."""

    def __init__(self, checks: Sequence[DataCheck] | None = None) -> None:
        self._checks = list(
            checks
            or [
                SchemaContractValidationCheck(),
                FreshnessAndSlaCheck(),
                NullSpikeAnomalyCheck(),
                JoinValidityCardinalityCheck(),
                DistributionDriftCheck(),
                ReferentialIntegrityCheck(),
            ]
        )

    async def run(self, ctx: VerifierContext) -> LayerResult:
        results = [safe_run_check(ctx, check) for check in self._checks]
        return aggregate_layer(layer="data", checks=results)
