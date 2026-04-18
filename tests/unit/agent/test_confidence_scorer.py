from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.agent.confidence_scorer import ConfidenceScorer
from ds_agent.domain.entities.review_verdict import CheckResult, Issue, LayerResult, ReviewVerdict


def _layer(layer: str, score: float, *, partial_failure: bool = False) -> LayerResult:
    return LayerResult(
        layer=layer,
        score=score,
        partial_failure=partial_failure,
        checks=[
            CheckResult(
                check_id=f"{layer}_check",
                status="pass" if score >= 0.7 else "warn",
                score=score,
                evidence={},
                message=f"{layer} score={score}",
                duration_ms=5,
            )
        ],
    )


def test_score_applies_layer_weights_and_blocker_penalty() -> None:
    verdict = ReviewVerdict(
        verdict_id="RV-10",
        task_id="TC-2026-001",
        reviewer="verifier",
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
        layers=[
            _layer("statistical", 0.9),
            _layer("data", 0.8),
            _layer("policy", 0.7),
            _layer("narrative", 0.6),
        ],
        blocking_issues=[Issue(message="PII exposure", layer="policy", check_id="policy_check")],
    )

    band = ConfidenceScorer().score(verdict)

    assert band.score == pytest.approx(0.58875)
    assert band.grade == "medium"


def test_score_falls_back_for_legacy_verdict_without_layers() -> None:
    verdict = ReviewVerdict(
        verdict_id="RV-11",
        task_id="TC-2026-001",
        category="statistical",
        result="pass",
        reviewer="agent",
        summary="Looks good",
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
    )

    band = ConfidenceScorer().score(verdict)

    assert band.score == pytest.approx(0.85)
    assert band.grade == "high"


def test_explain_lists_blockers_and_lowest_scoring_checks() -> None:
    verdict = ReviewVerdict(
        verdict_id="RV-12",
        task_id="TC-2026-001",
        reviewer="verifier",
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
        layers=[
            LayerResult(
                layer="statistical",
                checks=[
                    CheckResult(
                        check_id="leakage",
                        status="fail",
                        score=0.05,
                        evidence={},
                        message="target leakage suspected",
                        duration_ms=10,
                    ),
                    CheckResult(
                        check_id="overfit_gap",
                        status="warn",
                        score=0.20,
                        evidence={},
                        message="train/val gap is elevated",
                        duration_ms=10,
                    ),
                ],
            ),
            LayerResult(
                layer="data",
                checks=[
                    CheckResult(
                        check_id="drift",
                        status="warn",
                        score=0.30,
                        evidence={},
                        message="psi above threshold",
                        duration_ms=10,
                    ),
                    CheckResult(
                        check_id="freshness",
                        status="pass",
                        score=0.95,
                        evidence={},
                        message="fresh enough",
                        duration_ms=10,
                    ),
                ],
            ),
        ],
        blocking_issues=[Issue(message="policy review required", layer="policy")],
    )

    rationale = ConfidenceScorer().explain(verdict)

    assert rationale.startswith("blocked by: policy review required")
    assert "leakage: target leakage suspected" in rationale
    assert "overfit_gap: train/val gap is elevated" in rationale
    assert "drift: psi above threshold" in rationale
