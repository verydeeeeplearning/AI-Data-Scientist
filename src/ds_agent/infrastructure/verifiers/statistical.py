"""Statistical verifier layer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import mean, pstdev
from time import perf_counter

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from ds_agent.domain.dtos.verifier_context import VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult, CheckStatus, LayerResult
from ds_agent.domain.interfaces.verifier_ports import StatisticalCheck, StatisticalVerifierPort
from ds_agent.infrastructure.verifiers.common import (
    aggregate_layer,
    artifact,
    coerce_frame,
    elapsed_ms,
    metric_from_predictions,
    numeric_columns,
    safe_run_check,
)

_DOUBLE_WEIGHTED_CHECKS = {
    "data_leakage_detection": 2.0,
    "temporal_split_robustness": 2.0,
    "baseline_comparison": 2.0,
}


class DataLeakageCheck:
    """Detect duplicate splits, leaky correlations, and temporal overlap."""

    name = "data_leakage_detection"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        train = coerce_frame(artifact(ctx, "train_df"))
        val = coerce_frame(artifact(ctx, "val_df"))
        test = coerce_frame(artifact(ctx, "test_df"))
        if train is None:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="train_df artifact is missing",
                duration_ms=elapsed_ms(start),
            )

        temporal_column = artifact(ctx, "temporal_column")
        key_columns = list(artifact(ctx, "key_columns", default=[]))
        if not key_columns:
            key_columns = [
                column for column in ("id", "user_id", "customer_id") if column in train
            ]
        if (
            temporal_column
            and temporal_column in train.columns
            and temporal_column not in key_columns
        ):
            key_columns.append(str(temporal_column))

        duplicate_rate = 0.0
        overlap_rows = 0
        if key_columns and val is not None and set(key_columns).issubset(val.columns):
            overlap_rows += self._overlap_count(train, val, key_columns)
        if key_columns and test is not None and set(key_columns).issubset(test.columns):
            overlap_rows += self._overlap_count(train, test, key_columns)
        denominator = max(len(train), 1)
        duplicate_rate = overlap_rows / denominator

        leaky_features = self._find_leaky_features(ctx, train)

        temporal_overlap_rows = 0
        if (
            temporal_column
            and val is not None
            and temporal_column in train
            and temporal_column in val
        ):
            train_times = pd.to_datetime(train[temporal_column], errors="coerce").dropna()
            val_times = pd.to_datetime(val[temporal_column], errors="coerce").dropna()
            if not train_times.empty and not val_times.empty:
                train_max = train_times.max()
                temporal_overlap_rows += int((val_times <= train_max).sum())
        if (
            temporal_column
            and test is not None
            and temporal_column in train
            and temporal_column in test
        ):
            train_times = pd.to_datetime(train[temporal_column], errors="coerce").dropna()
            test_times = pd.to_datetime(test[temporal_column], errors="coerce").dropna()
            if not train_times.empty and not test_times.empty:
                train_max = train_times.max()
                temporal_overlap_rows += int((test_times <= train_max).sum())

        fit_scope = str(artifact(ctx, "feature_pipeline", default={}).get("fit_scope", "")).lower()
        full_fit = fit_scope == "full_dataset"

        evidence = {
            "duplicate_key_rate": round(duplicate_rate, 6),
            "leaky_features": leaky_features,
            "temporal_overlap_rows": temporal_overlap_rows,
            "pipeline_fit_scope": fit_scope or None,
        }
        fail_features = [feature for feature in leaky_features if not feature.endswith("~warn")]
        warn_features = [feature.removesuffix("~warn") for feature in leaky_features]
        if duplicate_rate > 0.005 or fail_features or temporal_overlap_rows > 0 or full_fit:
            message_parts = []
            if duplicate_rate > 0.005:
                message_parts.append(f"duplicate split overlap={duplicate_rate:.2%}")
            if fail_features:
                message_parts.append(f"leaky corr features={', '.join(fail_features[:3])}")
            if temporal_overlap_rows > 0:
                message_parts.append(f"temporal overlap rows={temporal_overlap_rows}")
            if full_fit:
                message_parts.append("feature pipeline fit on full dataset")
            return CheckResult(
                check_id=self.name,
                status="fail",
                score=0.0,
                evidence=evidence,
                message="; ".join(message_parts),
                remediation_hint="Resplit data and fit transformations on train only.",
                duration_ms=elapsed_ms(start),
            )
        if duplicate_rate >= 0.0001 or warn_features:
            return CheckResult(
                check_id=self.name,
                status="warn",
                score=0.55,
                evidence=evidence,
                message=(
                    f"possible split leakage overlap={duplicate_rate:.2%}, "
                    f"candidate features={', '.join(warn_features[:3]) or 'none'}"
                ),
                remediation_hint="Review split keys and inspect high-correlation features.",
                duration_ms=elapsed_ms(start),
            )
        return CheckResult(
            check_id=self.name,
            status="pass",
            score=1.0,
            evidence=evidence,
            message="no obvious leakage detected",
            duration_ms=elapsed_ms(start),
        )

    @staticmethod
    def _overlap_count(left: pd.DataFrame, right: pd.DataFrame, keys: Sequence[str]) -> int:
        left_index = pd.MultiIndex.from_frame(left[list(keys)].drop_duplicates())
        right_index = pd.MultiIndex.from_frame(right[list(keys)].drop_duplicates())
        return int(left_index.intersection(right_index).size)

    def _find_leaky_features(self, ctx: VerifierContext, train: pd.DataFrame) -> list[str]:
        target_column = artifact(ctx, "target_column")
        if not target_column or target_column not in train.columns:
            return []
        target = pd.to_numeric(train[target_column], errors="coerce")
        leaky_features: list[str] = []
        for feature in numeric_columns(train, exclude=[target_column]):
            values = pd.to_numeric(train[feature], errors="coerce")
            valid = pd.concat([target, values], axis=1).dropna()
            if len(valid) < 3:
                continue
            corr = abs(float(valid.corr(method="pearson").iloc[0, 1]))
            rank_corr = abs(float(valid.corr(method="spearman").iloc[0, 1]))
            max_corr = max(corr, rank_corr)
            if max_corr >= 0.99:
                leaky_features.append(feature)
            elif max_corr >= 0.90:
                leaky_features.append(f"{feature}~warn")
        return leaky_features


class TemporalSplitRobustnessCheck:
    """Evaluate variance across rolling temporal folds."""

    name = "temporal_split_robustness"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        temporal_column = artifact(ctx, "temporal_column")
        rolling_metrics = list(artifact(ctx, "rolling_metrics", default=[]))
        if not temporal_column and not rolling_metrics:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="temporal task artifacts are missing",
                duration_ms=elapsed_ms(start),
            )
        if len(rolling_metrics) < 3:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={"rolling_metrics": rolling_metrics},
                message="at least three rolling metrics are required",
                duration_ms=elapsed_ms(start),
            )

        metric_mean = mean(rolling_metrics)
        gap_ratio = (
            0.0
            if metric_mean == 0
            else (max(rolling_metrics) - min(rolling_metrics)) / metric_mean
        )
        evidence = {"rolling_metrics": rolling_metrics, "gap_ratio": round(gap_ratio, 6)}
        if gap_ratio > 0.30:
            status: CheckStatus = "fail"
            score = 0.0
            message = f"rolling metric gap too high ({gap_ratio:.1%})"
        elif gap_ratio > 0.15:
            status = "warn"
            score = 0.55
            message = f"rolling metric variance elevated ({gap_ratio:.1%})"
        else:
            status = "pass"
            score = 1.0
            message = "rolling temporal metrics are stable"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Revisit temporal split strategy or use more robust validation."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class SubgroupStabilityCheck:
    """Detect subgroup performance collapse."""

    name = "subgroup_stability"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        subgroup_metrics = self._extract_subgroup_metrics(ctx)
        if not subgroup_metrics:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="subgroup metrics are unavailable",
                duration_ms=elapsed_ms(start),
            )

        values = list(subgroup_metrics.values())
        overall = float(artifact(ctx, "overall_metric", default=mean(values)))
        cv = 0.0 if mean(values) == 0 else pstdev(values) / mean(values)
        worst_name = min(subgroup_metrics, key=lambda name: subgroup_metrics[name])
        worst_value = subgroup_metrics[worst_name]
        evidence = {
            "overall_metric": overall,
            "subgroup_metrics": subgroup_metrics,
            "worst_subgroup": worst_name,
            "coefficient_of_variation": round(cv, 6),
        }
        if worst_value < overall * 0.5 or cv > 0.5:
            status: CheckStatus = "fail"
            score = 0.0
            message = (
                f"subgroup instability detected ({worst_name}={worst_value:.3f}, cv={cv:.2f})"
            )
        elif cv > 0.3:
            status = "warn"
            score = 0.55
            message = f"subgroup variance elevated (cv={cv:.2f})"
        else:
            status = "pass"
            score = 1.0
            message = "subgroup metrics are stable"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Inspect the weakest subgroup before finalizing conclusions."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )

    def _extract_subgroup_metrics(self, ctx: VerifierContext) -> dict[str, float]:
        provided = artifact(ctx, "subgroup_metrics")
        if isinstance(provided, Mapping):
            return {str(key): float(value) for key, value in provided.items()}

        frame = coerce_frame(artifact(ctx, "evaluation_df"))
        subgroup_columns = list(artifact(ctx, "subgroup_columns", default=[]))
        truth_column = artifact(ctx, "y_true_column")
        prediction_column = artifact(ctx, "y_pred_column")
        if frame is None or not subgroup_columns or not truth_column or not prediction_column:
            return {}

        metrics: dict[str, float] = {}
        for column in subgroup_columns:
            if column not in frame.columns:
                continue
            for value, group in frame.groupby(column):
                metrics[f"{column}={value}"] = metric_from_predictions(
                    group,
                    truth_column=str(truth_column),
                    prediction_column=str(prediction_column),
                )
        return metrics


class BaselineComparisonCheck:
    """Verify lift against a naive baseline."""

    name = "baseline_comparison"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        actual_metric = artifact(ctx, "actual_metric")
        baseline_metric = artifact(ctx, "baseline_metric")
        p_value = artifact(ctx, "baseline_p_value")
        if actual_metric is None or baseline_metric is None:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="baseline comparison artifacts are missing",
                duration_ms=elapsed_ms(start),
            )

        lift = float(actual_metric) - float(baseline_metric)
        evidence = {
            "actual_metric": float(actual_metric),
            "baseline_metric": float(baseline_metric),
            "lift": round(lift, 6),
            "p_value": None if p_value is None else float(p_value),
        }
        if (p_value is not None and float(p_value) > 0.05) or lift < 0.01:
            status: CheckStatus = "fail"
            score = 0.0
            message = f"baseline lift insufficient ({lift:.3f})"
        elif lift < 0.05:
            status = "warn"
            score = 0.55
            message = f"baseline lift marginal ({lift:.3f})"
        else:
            status = "pass"
            score = 1.0
            message = f"baseline lift acceptable ({lift:.3f})"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Compare against a stronger baseline or rerun significance checks."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class PowerAnalysisCheck:
    """Check whether sample size supports the claimed effect."""

    name = "power_analysis"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        actual_n = artifact(ctx, "sample_size")
        effect_size = artifact(ctx, "effect_size")
        required_n = artifact(ctx, "required_sample_size")
        if actual_n is None:
            train = coerce_frame(artifact(ctx, "train_df"))
            actual_n = len(train) if train is not None else None
        if actual_n is None or effect_size is None:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="sample size or effect size is unavailable",
                duration_ms=elapsed_ms(start),
            )

        effect = abs(float(effect_size))
        if required_n is None:
            required_n = float("inf") if effect == 0 else 16.0 / (effect**2)
        actual = float(actual_n)
        required = float(required_n)
        evidence = {
            "actual_n": actual,
            "required_n": round(required, 2),
            "effect_size": effect,
        }
        if actual < required * 0.5:
            status: CheckStatus = "fail"
            score = 0.0
            message = "sample size is materially underpowered"
        elif actual < required:
            status = "warn"
            score = 0.55
            message = "sample size is below recommended power"
        else:
            status = "pass"
            score = 1.0
            message = "sample size looks adequate"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint=(
                "Collect more data or reduce claim strength."
                if status != "pass"
                else None
            ),
            duration_ms=elapsed_ms(start),
        )


class ClassImbalanceImpactCheck:
    """Measure whether majority-class performance nearly matches the model."""

    name = "class_imbalance_impact"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        actual_accuracy = artifact(ctx, "actual_accuracy")
        majority_accuracy = artifact(ctx, "majority_accuracy")
        if actual_accuracy is None or majority_accuracy is None:
            truth = artifact(ctx, "y_true")
            prediction = artifact(ctx, "y_pred")
            if truth is None or prediction is None:
                return CheckResult(
                    check_id=self.name,
                    status="skipped",
                    score=1.0,
                    evidence={},
                    message="class balance artifacts are unavailable",
                    duration_ms=elapsed_ms(start),
                )
            truth_series = pd.Series(truth)
            pred_series = pd.Series(prediction)
            actual_accuracy = float((truth_series == pred_series).mean())
            majority_accuracy = float(truth_series.value_counts(normalize=True).max())

        actual = float(actual_accuracy)
        majority = float(majority_accuracy)
        ratio = 1.0 if actual <= 0 else majority / actual
        evidence = {
            "actual_accuracy": actual,
            "majority_accuracy": majority,
            "majority_to_actual_ratio": round(ratio, 6),
        }
        if ratio >= 0.95:
            status: CheckStatus = "fail"
            score = 0.0
            message = "model barely beats majority-class baseline"
        elif ratio >= 0.85:
            status = "warn"
            score = 0.55
            message = "class imbalance likely inflates accuracy"
        else:
            status = "pass"
            score = 1.0
            message = "model meaningfully exceeds majority baseline"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Add balanced metrics or rebalance the training objective."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class MulticollinearityCheck:
    """Estimate VIF and flag unstable coefficient interpretation."""

    name = "multicollinearity"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        model_family = str(artifact(ctx, "model_family", default="")).lower()
        interpret_coefficients = bool(artifact(ctx, "interpret_coefficients", default=False))
        if model_family in {"tree", "boosting", "deep"} and not interpret_coefficients:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={"model_family": model_family},
                message="coefficient interpretation is not in scope",
                duration_ms=elapsed_ms(start),
            )

        provided_vif = artifact(ctx, "vif")
        vif_map: dict[str, float]
        if isinstance(provided_vif, Mapping):
            vif_map = {str(key): float(value) for key, value in provided_vif.items()}
        else:
            frame = coerce_frame(artifact(ctx, "train_df"))
            if frame is None:
                return CheckResult(
                    check_id=self.name,
                    status="skipped",
                    score=1.0,
                    evidence={},
                    message="training frame is unavailable for VIF calculation",
                    duration_ms=elapsed_ms(start),
                )
            feature_columns = artifact(ctx, "feature_columns")
            cols = list(feature_columns) if feature_columns else numeric_columns(frame)
            if len(cols) < 2:
                return CheckResult(
                    check_id=self.name,
                    status="skipped",
                    score=1.0,
                    evidence={},
                    message="at least two numeric features are required",
                    duration_ms=elapsed_ms(start),
                )
            vif_map = self._calculate_vif(frame[cols])

        high_vif = [name for name, value in vif_map.items() if value > 10]
        evidence = {"vif": {name: round(value, 4) for name, value in vif_map.items()}}
        if len(high_vif) >= 3:
            status: CheckStatus = "fail"
            score = 0.0
            message = f"high VIF on {len(high_vif)} features"
        elif high_vif:
            status = "warn"
            score = 0.55
            message = f"elevated VIF on {', '.join(high_vif[:3])}"
        else:
            status = "pass"
            score = 1.0
            message = "no severe multicollinearity detected"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Drop or combine collinear features before coefficient-level claims."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )

    @staticmethod
    def _calculate_vif(frame: pd.DataFrame) -> dict[str, float]:
        valid = frame.dropna().astype(float)
        corr = valid.corr().fillna(0.0).to_numpy()
        inverse = np.linalg.pinv(corr)
        return {column: float(inverse[idx, idx]) for idx, column in enumerate(valid.columns)}


class OverfittingGapCheck:
    """Flag excessive train-vs-validation gaps."""

    name = "overfitting_gap"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        train_metric = artifact(ctx, "train_metric")
        val_metric = artifact(ctx, "val_metric")
        if train_metric is None or val_metric is None:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="train/validation metrics are unavailable",
                duration_ms=elapsed_ms(start),
            )

        train_value = float(train_metric)
        val_value = float(val_metric)
        gap = float("inf") if val_value == 0 else abs(train_value - val_value) / abs(val_value)
        evidence = {
            "train_metric": train_value,
            "val_metric": val_value,
            "gap_ratio": round(gap, 6),
        }
        if gap > 0.20:
            status: CheckStatus = "fail"
            score = 0.0
            message = f"train/val gap too large ({gap:.1%})"
        elif gap > 0.10:
            status = "warn"
            score = 0.55
            message = f"train/val gap elevated ({gap:.1%})"
        else:
            status = "pass"
            score = 1.0
            message = "train/val gap is within tolerance"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Regularize more aggressively or simplify the model."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class MultipleTestingCorrectionCheck:
    """Check whether multiple p-value claims survive correction."""

    name = "multiple_testing_correction"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        p_values = artifact(ctx, "p_values")
        if not p_values or len(p_values) < 2:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="multiple-testing inputs are unavailable",
                duration_ms=elapsed_ms(start),
            )

        values = [float(value) for value in p_values]
        original_significant = sum(value < 0.05 for value in values)
        corrected_threshold = 0.05 / len(values)
        corrected_significant = sum(value < corrected_threshold for value in values)
        claims_adjusted = bool(artifact(ctx, "claims_adjusted", default=False))
        reduction_ratio = (
            1.0 if original_significant == 0 else corrected_significant / original_significant
        )
        evidence = {
            "p_values": values,
            "original_significant": original_significant,
            "corrected_significant": corrected_significant,
            "corrected_threshold": corrected_threshold,
        }
        if (
            original_significant > 0
            and reduction_ratio <= 0.5
            and not claims_adjusted
        ):
            status: CheckStatus = "fail"
            score = 0.0
            message = "significance claims do not survive correction"
        elif corrected_significant < original_significant:
            status = "warn"
            score = 0.55
            message = "some significance claims weaken after correction"
        else:
            status = "pass"
            score = 1.0
            message = "multiple-testing claims are acceptable"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Apply Bonferroni/BH correction in the final narrative."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class SampleRatioMismatchCheck:
    """Check whether experiment allocation exhibits sample-ratio mismatch."""

    name = "sample_ratio_mismatch"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        explicit = artifact(ctx, "sample_ratio_mismatch")
        if isinstance(explicit, bool):
            return CheckResult(
                check_id=self.name,
                status="fail" if explicit else "pass",
                score=0.0 if explicit else 1.0,
                evidence={"explicit_mismatch": explicit},
                message=(
                    "sample-ratio mismatch is explicitly recorded"
                    if explicit
                    else "sample-ratio mismatch is explicitly cleared"
                ),
                remediation_hint=(
                    "Investigate assignment, instrumentation, and traffic splits before shipping."
                    if explicit
                    else None
                ),
                duration_ms=elapsed_ms(start),
            )

        srm = artifact(ctx, "srm")
        if isinstance(srm, Mapping):
            p_value = _coerce_float(srm.get("p_value"))
            is_valid = srm.get("is_valid")
            observed_counts = srm.get("observed_counts")
            expected_counts = srm.get("expected_counts")
            if p_value is None and isinstance(is_valid, bool):
                p_value = 1.0 if is_valid else 0.0
            if p_value is not None:
                evidence = {
                    "p_value": p_value,
                    "is_valid": bool(is_valid) if isinstance(is_valid, bool) else p_value >= 0.05,
                    "observed_counts": observed_counts,
                    "expected_counts": expected_counts,
                }
                if p_value < 0.05:
                    status: CheckStatus = "fail"
                    score = 0.0
                    message = "sample-ratio mismatch indicates assignment imbalance"
                elif p_value < 0.10:
                    status = "warn"
                    score = 0.55
                    message = "sample allocation is borderline imbalanced"
                else:
                    status = "pass"
                    score = 1.0
                    message = "sample allocation is consistent with the expected split"
                return CheckResult(
                    check_id=self.name,
                    status=status,
                    score=score,
                    evidence=evidence,
                    message=message,
                    remediation_hint=(
                        "Investigate assignment, instrumentation, "
                        "and traffic splits before shipping."
                        if status != "pass"
                        else None
                    ),
                    duration_ms=elapsed_ms(start),
                )

        return CheckResult(
            check_id=self.name,
            status="skipped",
            score=1.0,
            evidence={},
            message="sample-ratio mismatch evidence is unavailable",
            duration_ms=elapsed_ms(start),
        )


class ConfidenceIntervalReviewCheck:
    """Review whether confidence intervals support the stated experiment conclusion."""

    name = "confidence_interval_review"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        explicit = artifact(ctx, "confidence_interval_review")
        if isinstance(explicit, bool):
            return CheckResult(
                check_id=self.name,
                status="pass" if explicit else "fail",
                score=1.0 if explicit else 0.0,
                evidence={"explicit_review": explicit},
                message=(
                    "confidence-interval review is explicitly recorded"
                    if explicit
                    else "confidence-interval review is explicitly missing"
                ),
                remediation_hint=(
                    None
                    if explicit
                    else "Inspect and report the confidence interval before moving to review."
                ),
                duration_ms=elapsed_ms(start),
            )

        ci_low = _coerce_float(artifact(ctx, "ci_low"))
        ci_high = _coerce_float(artifact(ctx, "ci_high"))
        if ci_low is None or ci_high is None:
            interval = artifact(ctx, "confidence_interval")
            if isinstance(interval, Mapping):
                ci_low = _coerce_float(interval.get("low"))
                ci_high = _coerce_float(interval.get("high"))
        if ci_low is None or ci_high is None:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={},
                message="confidence-interval evidence is unavailable",
                duration_ms=elapsed_ms(start),
            )

        if ci_low > ci_high:
            ci_low, ci_high = ci_high, ci_low
        effect_size = abs(_coerce_float(artifact(ctx, "effect_size")) or 0.0)
        width = ci_high - ci_low
        spans_zero = ci_low <= 0.0 <= ci_high
        evidence = {
            "ci_low": ci_low,
            "ci_high": ci_high,
            "interval_width": width,
            "effect_size": effect_size,
            "spans_zero": spans_zero,
        }
        if spans_zero:
            status: CheckStatus = "fail"
            score = 0.0
            message = "confidence interval still crosses zero"
        elif effect_size > 0.0 and width > effect_size * 2:
            status = "warn"
            score = 0.55
            message = "confidence interval is wide relative to the observed effect"
        else:
            status = "pass"
            score = 1.0
            message = "confidence interval supports the observed effect direction"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint=(
                "Report the interval width and temper the recommendation until precision improves."
                if status != "pass"
                else None
            ),
            duration_ms=elapsed_ms(start),
        )


class EffectSizePracticalSignificanceCheck:
    """Ensure statistical signal meets the practical-effect threshold."""

    name = "effect_size_practical_significance"
    version = "1"

    def run(self, ctx: VerifierContext) -> CheckResult:
        start = perf_counter()
        effect_size = artifact(ctx, "effect_size")
        min_effect = float(artifact(ctx, "min_practical_effect", default=0.0))
        if effect_size is None:
            return CheckResult(
                check_id=self.name,
                status="skipped",
                score=1.0,
                evidence={"min_practical_effect": min_effect},
                message="effect size is unavailable",
                duration_ms=elapsed_ms(start),
            )

        effect = abs(float(effect_size))
        evidence = {
            "effect_size": effect,
            "min_practical_effect": min_effect,
        }
        if effect < min_effect:
            status: CheckStatus = "fail"
            score = 0.0
            message = "effect size is below the practical threshold"
        elif effect < (min_effect * 1.5 if min_effect > 0 else effect + 1):
            status = "warn"
            score = 0.55
            message = "effect size is only marginally practical"
        else:
            status = "pass"
            score = 1.0
            message = "effect size meets practical significance"
        return CheckResult(
            check_id=self.name,
            status=status,
            score=score,
            evidence=evidence,
            message=message,
            remediation_hint="Reduce claim strength or raise the minimum business threshold."
            if status != "pass"
            else None,
            duration_ms=elapsed_ms(start),
        )


class StatisticalVerifier(StatisticalVerifierPort):
    """Run the statistical verifier layer deterministically."""

    def __init__(self, checks: Sequence[StatisticalCheck] | None = None) -> None:
        self._checks = list(
            checks
            or [
                DataLeakageCheck(),
                TemporalSplitRobustnessCheck(),
                SubgroupStabilityCheck(),
                BaselineComparisonCheck(),
                PowerAnalysisCheck(),
                ClassImbalanceImpactCheck(),
                MulticollinearityCheck(),
                OverfittingGapCheck(),
                SampleRatioMismatchCheck(),
                MultipleTestingCorrectionCheck(),
                ConfidenceIntervalReviewCheck(),
                EffectSizePracticalSignificanceCheck(),
            ]
        )

    async def run(self, ctx: VerifierContext) -> LayerResult:
        results = [safe_run_check(ctx, check) for check in self._checks]
        return aggregate_layer(
            layer="statistical",
            checks=results,
            weights=_DOUBLE_WEIGHTED_CHECKS,
        )


def _coerce_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
