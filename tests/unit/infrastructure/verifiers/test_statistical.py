from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from ds_agent.domain.dtos.verifier_context import VerifierConfig, VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.infrastructure.verifiers.statistical import StatisticalVerifier


def _task_contract() -> TaskContract:
    now = datetime(2026, 4, 16, tzinfo=UTC)
    return TaskContract(
        task_id="TC-2026-001",
        session_id="session-1",
        type="churn_analysis",
        business_goal="Reduce churn",
        required_deliverables=[{"type": "exec_brief", "audience": "executive", "format": "pptx"}],
        created_at=now,
        updated_at=now,
    )


def _base_artifacts() -> dict[str, object]:
    train_df = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5, 6],
            "feature_a": [0.11, 0.23, 0.35, 0.41, 0.52, 0.63],
            "feature_b": [1.0, 0.8, 0.5, 0.4, 0.2, 0.1],
            "target": [0, 0, 0, 1, 1, 1],
        }
    )
    val_df = pd.DataFrame(
        {
            "id": [7, 8, 9],
            "feature_a": [0.14, 0.31, 0.59],
            "feature_b": [0.9, 0.7, 0.2],
            "target": [0, 0, 1],
        }
    )
    return {
        "train_df": train_df,
        "val_df": val_df,
        "target_column": "target",
        "subgroup_metrics": {"segment_a": 0.84, "segment_b": 0.80, "segment_c": 0.79},
        "overall_metric": 0.81,
        "actual_metric": 0.84,
        "baseline_metric": 0.75,
        "baseline_p_value": 0.01,
        "sample_size": 400,
        "required_sample_size": 200,
        "effect_size": 0.25,
        "actual_accuracy": 0.88,
        "majority_accuracy": 0.60,
        "model_family": "linear",
        "interpret_coefficients": True,
        "vif": {"feature_a": 2.1, "feature_b": 3.2},
        "train_metric": 0.88,
        "val_metric": 0.82,
        "p_values": [0.01, 0.03],
        "claims_adjusted": True,
        "min_practical_effect": 0.10,
    }


def _ctx(overrides: dict[str, object] | None = None) -> VerifierContext:
    artifacts = _base_artifacts()
    if overrides:
        artifacts.update(overrides)
    return VerifierContext(
        run_id="run-1",
        task_contract=_task_contract(),
        artifacts=artifacts,
        config=VerifierConfig(),
    )


def _find_check(verifier_result, check_id: str) -> CheckResult:
    return next(check for check in verifier_result.checks if check.check_id == check_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({}, "pass"),
        (
            {
                "train_df": pd.DataFrame(
                    {
                        "id": [1, 2, 3, 4, 5, 6],
                        "feature_a": [0.1, 0.2, 0.3, 0.7, 0.8, 0.9],
                        "feature_b": [1.0, 0.8, 0.5, 0.4, 0.2, 0.1],
                        "target": [0, 0, 0, 1, 1, 1],
                    }
                )
            },
            "warn",
        ),
        (
            {
                "val_df": pd.DataFrame(
                    {
                        "id": [3, 8, 9],
                        "feature_a": [0.35, 0.31, 0.59],
                        "feature_b": [0.5, 0.7, 0.2],
                        "target": [0, 0, 1],
                    }
                )
            },
            "fail",
        ),
    ],
)
async def test_leakage_check_status_matrix(
    overrides: dict[str, object],
    expected_status: str,
) -> None:
    result = await StatisticalVerifier().run(_ctx(overrides))
    leakage = _find_check(result, "data_leakage_detection")

    assert leakage.status == expected_status
    if expected_status == "pass":
        assert leakage.evidence["duplicate_key_rate"] == 0.0
        assert leakage.evidence["leaky_features"] == []
    elif expected_status == "warn":
        assert leakage.evidence["duplicate_key_rate"] == 0.0
        assert leakage.evidence["leaky_features"] == ["feature_a~warn"]
    else:
        assert leakage.evidence["duplicate_key_rate"] > 0.005


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rolling_metrics", "expected_status"),
    [
        ([0.81, 0.80, 0.79], "pass"),
        ([0.90, 0.74, 0.80], "warn"),
        ([1.00, 0.60, 0.70], "fail"),
    ],
)
async def test_temporal_split_check_status_matrix(
    rolling_metrics: list[float],
    expected_status: str,
) -> None:
    result = await StatisticalVerifier().run(
        _ctx(
            {
                "temporal_column": "event_at",
                "train_df": pd.DataFrame(
                    {
                        "id": [1, 2, 3],
                        "event_at": ["2026-01-01", "2026-01-02", "2026-01-03"],
                        "feature_a": [0.1, 0.2, 0.3],
                        "feature_b": [1.0, 0.8, 0.6],
                        "target": [0, 0, 1],
                    }
                ),
                "val_df": pd.DataFrame(
                    {
                        "id": [4, 5],
                        "event_at": ["2026-01-04", "2026-01-05"],
                        "feature_a": [0.4, 0.5],
                        "feature_b": [0.5, 0.4],
                        "target": [1, 1],
                    }
                ),
                "rolling_metrics": rolling_metrics,
            }
        )
    )
    temporal = _find_check(result, "temporal_split_robustness")

    assert temporal.status == expected_status
    if expected_status == "pass":
        assert temporal.evidence["gap_ratio"] <= 0.15
    elif expected_status == "warn":
        assert 0.15 < temporal.evidence["gap_ratio"] <= 0.30
    else:
        assert temporal.evidence["gap_ratio"] > 0.30


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actual_metric", "baseline_metric", "baseline_p_value", "expected_status"),
    [
        (0.84, 0.75, 0.01, "pass"),
        (0.78, 0.75, 0.01, "warn"),
        (0.76, 0.75, 0.20, "fail"),
    ],
)
async def test_baseline_comparison_status_matrix(
    actual_metric: float,
    baseline_metric: float,
    baseline_p_value: float,
    expected_status: str,
) -> None:
    result = await StatisticalVerifier().run(
        _ctx(
            {
                "actual_metric": actual_metric,
                "baseline_metric": baseline_metric,
                "baseline_p_value": baseline_p_value,
            }
        )
    )
    baseline = _find_check(result, "baseline_comparison")

    assert baseline.status == expected_status
    if expected_status == "pass":
        assert baseline.evidence["lift"] >= 0.05
    elif expected_status == "warn":
        assert 0.01 <= baseline.evidence["lift"] < 0.05
    else:
        assert baseline.evidence["p_value"] > 0.05 or baseline.evidence["lift"] < 0.01


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("train_metric", "val_metric", "expected_status"),
    [
        (0.84, 0.80, "pass"),
        (0.90, 0.80, "warn"),
        (0.99, 0.80, "fail"),
    ],
)
async def test_overfitting_gap_status_matrix(
    train_metric: float,
    val_metric: float,
    expected_status: str,
) -> None:
    result = await StatisticalVerifier().run(
        _ctx({"train_metric": train_metric, "val_metric": val_metric})
    )
    check = _find_check(result, "overfitting_gap")

    assert check.status == expected_status
    if expected_status == "pass":
        assert check.evidence["gap_ratio"] <= 0.10
    elif expected_status == "warn":
        assert 0.10 < check.evidence["gap_ratio"] <= 0.20
    else:
        assert check.evidence["gap_ratio"] > 0.20


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subgroup_metrics", "expected_status"),
    [
        ({"segment_a": 0.84, "segment_b": 0.80, "segment_c": 0.79}, "pass"),
        ({"segment_a": 0.95, "segment_b": 0.95, "segment_c": 0.41}, "warn"),
        ({"segment_a": 0.82, "segment_b": 0.78, "segment_c": 0.20}, "fail"),
    ],
)
async def test_subgroup_stability_status_matrix(
    subgroup_metrics: dict[str, float],
    expected_status: str,
) -> None:
    result = await StatisticalVerifier().run(_ctx({"subgroup_metrics": subgroup_metrics}))
    subgroup = _find_check(result, "subgroup_stability")

    assert subgroup.status == expected_status
    assert subgroup.evidence["worst_subgroup"] == min(
        subgroup_metrics,
        key=lambda name: subgroup_metrics[name],
    )
    if expected_status == "pass":
        assert subgroup.evidence["coefficient_of_variation"] <= 0.3
    elif expected_status == "warn":
        assert 0.3 < subgroup.evidence["coefficient_of_variation"] <= 0.5
    else:
        assert subgroup_metrics[subgroup.evidence["worst_subgroup"]] < 0.81 * 0.5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sample_size", "required_sample_size", "expected_status"),
    [
        (400, 200, "pass"),
        (150, 200, "warn"),
        (80, 200, "fail"),
    ],
)
async def test_power_analysis_status_matrix(
    sample_size: int,
    required_sample_size: int,
    expected_status: str,
) -> None:
    result = await StatisticalVerifier().run(
        _ctx(
            {
                "sample_size": sample_size,
                "required_sample_size": required_sample_size,
            }
        )
    )
    check = _find_check(result, "power_analysis")

    assert check.status == expected_status
    if expected_status == "pass":
        assert check.evidence["actual_n"] >= check.evidence["required_n"]
    elif expected_status == "warn":
        assert check.evidence["required_n"] * 0.5 <= check.evidence["actual_n"] < check.evidence[
            "required_n"
        ]
    else:
        assert check.evidence["actual_n"] < check.evidence["required_n"] * 0.5


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actual_accuracy", "majority_accuracy", "expected_status"),
    [
        (0.88, 0.60, "pass"),
        (0.80, 0.70, "warn"),
        (0.80, 0.77, "fail"),
    ],
)
async def test_class_imbalance_impact_status_matrix(
    actual_accuracy: float,
    majority_accuracy: float,
    expected_status: str,
) -> None:
    result = await StatisticalVerifier().run(
        _ctx(
            {
                "actual_accuracy": actual_accuracy,
                "majority_accuracy": majority_accuracy,
            }
        )
    )
    check = _find_check(result, "class_imbalance_impact")

    assert check.status == expected_status
    if expected_status == "pass":
        assert check.evidence["majority_to_actual_ratio"] < 0.85
    elif expected_status == "warn":
        assert 0.85 <= check.evidence["majority_to_actual_ratio"] < 0.95
    else:
        assert check.evidence["majority_to_actual_ratio"] >= 0.95


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("vif", "expected_status"),
    [
        ({"feature_a": 2.1, "feature_b": 3.2}, "pass"),
        ({"feature_a": 12.0, "feature_b": 3.2}, "warn"),
        ({"feature_a": 12.0, "feature_b": 13.0, "feature_c": 14.0}, "fail"),
    ],
)
async def test_multicollinearity_status_matrix(
    vif: dict[str, float],
    expected_status: str,
) -> None:
    result = await StatisticalVerifier().run(_ctx({"vif": vif}))
    check = _find_check(result, "multicollinearity")

    assert check.status == expected_status
    if expected_status == "pass":
        assert all(value <= 10 for value in check.evidence["vif"].values())
    elif expected_status == "warn":
        assert sum(value > 10 for value in check.evidence["vif"].values()) == 1
    else:
        assert sum(value > 10 for value in check.evidence["vif"].values()) >= 3


@pytest.mark.asyncio
async def test_multicollinearity_skips_tree_model_without_coefficient_claims() -> None:
    ctx = _ctx({"model_family": "tree", "interpret_coefficients": False, "vif": None})

    result = await StatisticalVerifier().run(ctx)
    check = _find_check(result, "multicollinearity")

    assert check.status == "skipped"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("p_values", "claims_adjusted", "expected_status"),
    [
        ([0.001, 0.002], False, "pass"),
        ([0.001, 0.03], True, "warn"),
        ([0.001, 0.01, 0.02, 0.03], False, "fail"),
    ],
)
async def test_multiple_testing_status_matrix(
    p_values: list[float],
    claims_adjusted: bool,
    expected_status: str,
) -> None:
    result = await StatisticalVerifier().run(
        _ctx({"p_values": p_values, "claims_adjusted": claims_adjusted})
    )
    check = _find_check(result, "multiple_testing_correction")

    assert check.status == expected_status
    if expected_status == "pass":
        assert check.evidence["corrected_significant"] == check.evidence["original_significant"]
    elif expected_status == "warn":
        assert check.evidence["corrected_significant"] < check.evidence["original_significant"]
    else:
        assert check.evidence["corrected_significant"] <= (
            check.evidence["original_significant"] / 2
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("effect_size", "min_practical_effect", "expected_status"),
    [
        (0.25, 0.10, "pass"),
        (0.12, 0.10, "warn"),
        (0.05, 0.10, "fail"),
    ],
)
async def test_effect_size_practical_significance_status_matrix(
    effect_size: float,
    min_practical_effect: float,
    expected_status: str,
) -> None:
    result = await StatisticalVerifier().run(
        _ctx(
            {
                "effect_size": effect_size,
                "min_practical_effect": min_practical_effect,
            }
        )
    )
    check = _find_check(result, "effect_size_practical_significance")

    assert check.status == expected_status
    if expected_status == "pass":
        assert check.evidence["effect_size"] >= min_practical_effect * 1.5
    elif expected_status == "warn":
        assert min_practical_effect <= check.evidence["effect_size"] < min_practical_effect * 1.5
    else:
        assert check.evidence["effect_size"] < min_practical_effect


@pytest.mark.asyncio
async def test_statistical_layer_uses_double_weight_for_leakage_and_baseline() -> None:
    class WarnLeakageCheck:
        name = "data_leakage_detection"
        version = "1"

        def run(self, ctx: VerifierContext) -> CheckResult:
            return CheckResult(
                check_id=self.name,
                status="warn",
                score=0.5,
                evidence={},
                message="warn leakage",
                duration_ms=1,
            )

    class PassBaselineCheck:
        name = "baseline_comparison"
        version = "1"

        def run(self, ctx: VerifierContext) -> CheckResult:
            return CheckResult(
                check_id=self.name,
                status="pass",
                score=1.0,
                evidence={},
                message="baseline ok",
                duration_ms=1,
            )

    class PassOtherCheck:
        name = "power_analysis"
        version = "1"

        def run(self, ctx: VerifierContext) -> CheckResult:
            return CheckResult(
                check_id=self.name,
                status="pass",
                score=1.0,
                evidence={},
                message="power ok",
                duration_ms=1,
            )

    verifier = StatisticalVerifier(
        checks=[WarnLeakageCheck(), PassBaselineCheck(), PassOtherCheck()]
    )

    result = await verifier.run(_ctx())

    assert result.score == pytest.approx((0.5 * 2.0 + 1.0 * 2.0 + 1.0) / 5.0)
    assert result.overall == "warn"
