from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.application.services.verifier_shadow_comparator import LegacyHookShadowComparator
from ds_agent.domain.dtos.verifier_context import VerifierConfig, VerifierContext
from ds_agent.domain.entities.review_verdict import CheckResult, LayerResult, ReviewVerdict
from ds_agent.domain.entities.task_contract import TaskContract


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


def _ctx(run_log: list[dict[str, object]]) -> VerifierContext:
    return VerifierContext(
        run_id="run-1",
        task_contract=_task_contract(),
        run_log=run_log,
        config=VerifierConfig(shadow_mode=True),
    )


def _verdict(*layers: LayerResult) -> ReviewVerdict:
    return ReviewVerdict(
        verdict_id="RV-2026001",
        task_id="TC-2026-001",
        category="orchestrator",
        reviewer="verifier_orchestrator",
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
        layers=list(layers),
    )


def _check(check_id: str, status: str, message: str) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        status=status,  # type: ignore[arg-type]
        score=0.55 if status == "warn" else 0.0 if status in {"fail", "error"} else 1.0,
        evidence={},
        message=message,
        duration_ms=1,
    )


def test_shadow_comparator_compares_triggered_and_clear_paths() -> None:
    comparator = LegacyHookShadowComparator()
    ctx = _ctx(
        [
            {"event": "tool.call", "tool": "feature_engineer"},
            {"event": "tool.call", "tool": "train_model"},
            {"event": "tool.call", "tool": "evaluate_model"},
            {"event": "harness.warning", "type": "leakage", "severity": "high"},
            {"event": "harness.warning", "type": "overfitting", "severity": "high"},
        ]
    )
    verdict = _verdict(
        LayerResult(
            layer="statistical",
            checks=[
                _check("data_leakage_detection", "fail", "target leakage detected"),
                _check("baseline_comparison", "pass", "baseline cleared"),
                _check("overfitting_gap", "warn", "train/test gap too high"),
            ],
        ),
        LayerResult(
            layer="data",
            checks=[_check("distribution_drift", "pass", "stable distributions")],
        ),
    )

    record = comparator.compare(ctx, verdict)

    assert record is not None
    assert record.applicable_count == 5
    assert record.mismatch_count == 0
    assert record.match_rate == 1.0


def test_shadow_comparator_flags_verifier_only_mismatch() -> None:
    comparator = LegacyHookShadowComparator()
    ctx = _ctx([{"event": "tool.call", "tool": "evaluate_model"}])
    verdict = _verdict(
        LayerResult(
            layer="data",
            checks=[_check("distribution_drift", "warn", "psi above threshold")],
        )
    )

    record = comparator.compare(ctx, verdict)

    assert record is not None
    drift_item = next(item for item in record.items if item.comparison_key == "drift_detection")
    assert drift_item.matches is False
    assert drift_item.mismatch_kind == "verifier_only"
    assert record.mismatch_count == 1


def test_shadow_comparator_returns_none_without_applicable_signals() -> None:
    comparator = LegacyHookShadowComparator()

    record = comparator.compare(_ctx([]), _verdict())

    assert record is None


def test_shadow_comparator_matches_temporal_join_to_temporal_verifier_evidence() -> None:
    comparator = LegacyHookShadowComparator()
    ctx = _ctx(
        [
            {"event": "tool.call", "tool": "feature_engineer"},
            {"event": "harness.warning", "type": "temporal_join", "severity": "high"},
        ]
    )
    verdict = _verdict(
        LayerResult(
            layer="statistical",
            checks=[
                CheckResult(
                    check_id="data_leakage_detection",
                    status="fail",
                    score=0.0,
                    evidence={"temporal_overlap_rows": 3},
                    message="temporal overlap rows=3",
                    duration_ms=1,
                )
            ],
        )
    )

    record = comparator.compare(ctx, verdict)

    assert record is not None
    temporal_item = next(
        item for item in record.items if item.comparison_key == "temporal_join_guard"
    )
    assert temporal_item.matches is True
    assert temporal_item.mismatch_kind == "agreement"
