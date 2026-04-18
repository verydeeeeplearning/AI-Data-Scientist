from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from ds_agent.domain.dtos.verifier_context import VerifierConfig, VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult
from ds_agent.domain.entities.task_contract import TaskContract
from ds_agent.domain.value_objects.drift import DriftMetric, DriftReport
from ds_agent.infrastructure.verifiers.data import DataVerifier, DistributionDriftCheck


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
    current_df = pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4],
            "segment": ["a", "a", "b", "b"],
            "score": [0.1, 0.2, 0.3, 0.4],
            "event_at": pd.to_datetime(
                [
                    "2026-04-16T09:00:00Z",
                    "2026-04-16T09:15:00Z",
                    "2026-04-16T09:30:00Z",
                    "2026-04-16T09:45:00Z",
                ]
            ),
        }
    )
    return {
        "current_df": current_df,
        "observed_df": current_df,
        "reference_df": current_df.copy(),
        "data_schema": {
            "customer_id": {"dtype": "int64", "required": True},
            "segment": {"dtype": "object", "required": True},
            "score": {"dtype": "float64", "required": True},
            "optional_note": {"dtype": "object", "required": False},
        },
        "temporal_column": "event_at",
        "reference_now": datetime(2026, 4, 16, 10, 0, tzinfo=UTC),
        "sla_max_staleness_seconds": 7200,
        "data_profile": {
            "columns": {
                "segment": {"null_ratio_mean": 0.0, "null_ratio_std": 0.0, "required": True},
                "score": {"null_ratio_mean": 0.0, "null_ratio_std": 0.0, "required": True},
            }
        },
        "run_log": [{"type": "join", "pre_row_count": 4, "post_row_count": 4}],
        "referential_checks": [{"name": "customer_fk", "orphan_rate": 0.0}],
    }


def _ctx(overrides: dict[str, object] | None = None) -> VerifierContext:
    artifacts = _base_artifacts()
    if overrides:
        artifacts.update(overrides)
        if "current_df" in overrides and "observed_df" not in overrides:
            artifacts["observed_df"] = overrides["current_df"]
    return VerifierContext(
        run_id="run-1",
        task_contract=_task_contract(),
        artifacts=artifacts,
        config=VerifierConfig(),
    )


def _find_check(verifier_result, check_id: str) -> CheckResult:
    return next(check for check in verifier_result.checks if check.check_id == check_id)


class _FakeDriftAnalyzer:
    def __init__(self, psi: float) -> None:
        self._psi = psi

    def analyze(self, reference_data: object, current_data: object, features=None) -> DriftReport:
        level = "danger" if self._psi > 0.25 else "warning" if self._psi > 0.10 else "ok"
        overall_status = (
            "danger" if level == "danger" else "warning" if level == "warning" else "ok"
        )
        recommended_action = (
            "rollback_or_retrain"
            if overall_status == "danger"
            else "monitor_and_investigate"
            if overall_status == "warning"
            else "no_action"
        )
        return DriftReport(
            metrics=[
                DriftMetric(
                    feature_name="score",
                    metric_type="PSI",
                    value=self._psi,
                    threshold=0.1,
                    level=level,
                )
            ],
            overall_status=overall_status,
            top_drifting_features=["score"] if self._psi > 0 else [],
            recommended_action=recommended_action,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        (
            {
                "current_df": pd.DataFrame(
                    {
                        "customer_id": [1, 2, 3, 4],
                        "segment": ["a", "a", "b", "b"],
                        "score": [0.1, 0.2, 0.3, 0.4],
                        "optional_note": ["x", "y", "z", "w"],
                        "event_at": pd.to_datetime(
                            [
                                "2026-04-16T09:00:00Z",
                                "2026-04-16T09:15:00Z",
                                "2026-04-16T09:30:00Z",
                                "2026-04-16T09:45:00Z",
                            ]
                        ),
                    }
                )
            },
            "pass",
        ),
        ({}, "warn"),
        (
            {
                "current_df": pd.DataFrame(
                    {
                        "customer_id": [1, 2, 3],
                        "score": [0.1, 0.2, 0.3],
                        "event_at": pd.to_datetime(
                            [
                                "2026-04-16T09:00:00Z",
                                "2026-04-16T09:15:00Z",
                                "2026-04-16T09:30:00Z",
                            ]
                        ),
                    }
                )
            },
            "fail",
        ),
    ],
)
async def test_schema_contract_status_matrix(
    overrides: dict[str, object],
    expected_status: str,
) -> None:
    if "current_df" in overrides:
        overrides = {
            **overrides,
            "observed_df": overrides["current_df"],
        }
    result = await DataVerifier().run(_ctx(overrides))
    check = _find_check(result, "schema_contract_validation")

    assert check.status == expected_status
    if expected_status == "pass":
        assert check.evidence["missing_required"] == []
        assert check.evidence["missing_optional"] == []
    elif expected_status == "warn":
        assert "optional_note" in check.evidence["missing_optional"]
    else:
        assert "segment" in check.evidence["missing_required"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reference_now", "expected_status"),
    [
        (datetime(2026, 4, 16, 10, 0, tzinfo=UTC), "pass"),
        (datetime(2026, 4, 16, 11, 30, tzinfo=UTC), "warn"),
        (datetime(2026, 4, 16, 12, 0, tzinfo=UTC), "fail"),
    ],
)
async def test_freshness_check_status_matrix(
    reference_now: datetime,
    expected_status: str,
) -> None:
    result = await DataVerifier().run(_ctx({"reference_now": reference_now}))
    check = _find_check(result, "freshness_sla_compliance")

    assert check.status == expected_status
    if expected_status == "pass":
        assert check.evidence["staleness_seconds"] <= 7200 * 0.8
    elif expected_status == "warn":
        assert 7200 * 0.8 < check.evidence["staleness_seconds"] <= 7200
    else:
        assert check.evidence["staleness_seconds"] > 7200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({}, "pass"),
        (
            {
                "current_df": pd.DataFrame(
                    {
                        "customer_id": [1, 2, 3, 4],
                        "segment": ["a", "a", "b", "b"],
                        "score": [0.1, 0.2, 0.3, 0.4],
                        "optional_note": [None, None, "ok", "ok"],
                        "event_at": pd.to_datetime(
                            [
                                "2026-04-16T09:00:00Z",
                                "2026-04-16T09:15:00Z",
                                "2026-04-16T09:30:00Z",
                                "2026-04-16T09:45:00Z",
                            ]
                        ),
                    }
                ),
                "data_profile": {
                    "columns": {
                        "segment": {
                            "null_ratio_mean": 0.0,
                            "null_ratio_std": 0.0,
                            "required": True,
                        },
                        "score": {
                            "null_ratio_mean": 0.0,
                            "null_ratio_std": 0.0,
                            "required": True,
                        },
                        "optional_note": {
                            "null_ratio_mean": 0.0,
                            "null_ratio_std": 0.0,
                            "required": False,
                        },
                    }
                },
            },
            "warn",
        ),
        (
            {
                "current_df": pd.DataFrame(
                    {
                        "customer_id": [1, 2, 3, 4],
                        "segment": ["a", None, None, "b"],
                        "score": [0.1, 0.2, 0.3, 0.4],
                        "event_at": pd.to_datetime(
                            [
                                "2026-04-16T09:00:00Z",
                                "2026-04-16T09:15:00Z",
                                "2026-04-16T09:30:00Z",
                                "2026-04-16T09:45:00Z",
                            ]
                        ),
                    }
                )
            },
            "fail",
        ),
    ],
)
async def test_null_spike_status_matrix(
    overrides: dict[str, object],
    expected_status: str,
) -> None:
    result = await DataVerifier().run(_ctx(overrides))
    check = _find_check(result, "null_spike_anomaly")

    assert check.status == expected_status
    if expected_status == "pass":
        assert all(delta["current"] == 0.0 for delta in check.evidence["columns"].values())
    elif expected_status == "warn":
        assert check.evidence["columns"]["optional_note"]["current"] > 0.0
    else:
        assert check.evidence["columns"]["segment"]["current"] > 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("run_log", "expected_status"),
    [
        ([{"type": "join", "pre_row_count": 100, "post_row_count": 100}], "pass"),
        ([{"type": "join", "pre_row_count": 100, "post_row_count": 108}], "warn"),
        ([{"type": "join", "pre_row_count": 100, "post_row_count": 250}], "fail"),
    ],
)
async def test_join_validity_status_matrix(
    run_log: list[dict[str, int | str]],
    expected_status: str,
) -> None:
    result = await DataVerifier().run(_ctx({"run_log": run_log}))
    check = _find_check(result, "join_validity_cardinality")

    assert check.status == expected_status
    if expected_status == "pass":
        assert check.evidence["max_row_ratio"] < 1.05
    elif expected_status == "warn":
        assert 1.05 <= check.evidence["max_row_ratio"] < 2.0
    else:
        assert check.evidence["max_row_ratio"] >= 2.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("psi", "expected_status"),
    [
        (0.05, "pass"),
        (0.15, "warn"),
        (0.35, "fail"),
    ],
)
async def test_distribution_drift_status_matrix(
    psi: float,
    expected_status: str,
) -> None:
    verifier = DataVerifier(checks=[DistributionDriftCheck(_FakeDriftAnalyzer(psi))])

    result = await verifier.run(_ctx())
    check = _find_check(result, "distribution_drift")

    assert check.status == expected_status
    assert check.evidence["max_psi"] == psi


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("orphan_rate", "expected_status"),
    [
        (0.0, "pass"),
        (0.005, "warn"),
        (0.02, "fail"),
    ],
)
async def test_referential_integrity_status_matrix(
    orphan_rate: float,
    expected_status: str,
) -> None:
    result = await DataVerifier().run(
        _ctx({"referential_checks": [{"name": "customer_fk", "orphan_rate": orphan_rate}]})
    )
    check = _find_check(result, "referential_integrity")

    assert check.status == expected_status
    assert check.evidence["max_orphan_rate"] == orphan_rate
