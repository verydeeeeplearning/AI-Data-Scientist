from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ds_agent.domain.entities.review_verdict import (
    CheckResult,
    ConfidenceBand,
    LayerResult,
    ReviewVerdict,
)


@pytest.mark.parametrize(
    ("score", "expected_grade"),
    [
        (0.80, "high"),
        (0.50, "medium"),
        (0.20, "low"),
        (0.19, "insufficient"),
    ],
)
def test_confidence_band_derives_grade_from_score(score: float, expected_grade: str) -> None:
    band = ConfidenceBand(score=score, rationale="scored")

    assert band.grade == expected_grade


def test_confidence_band_rejects_explicit_grade_mismatch() -> None:
    with pytest.raises(ValueError, match="confidence grade"):
        ConfidenceBand(score=0.91, grade="medium", rationale="mismatch")


def test_review_verdict_keeps_legacy_shape_compatible() -> None:
    verdict = ReviewVerdict(
        verdict_id="RV-1",
        task_id="TC-2026-001",
        category="statistical",
        result="warn",
        reviewer="agent",
        summary="Potential leakage candidate",
        evidence_refs=["artifact://profile/train"],
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
    )

    assert verdict.category == "statistical"
    assert verdict.result == "warn"
    assert verdict.overall == "warn"
    assert verdict.layers == []
    assert verdict.summary == "Potential leakage candidate"


def test_review_verdict_derives_overall_from_layers() -> None:
    verdict = ReviewVerdict(
        verdict_id="RV-2",
        task_id="TC-2026-001",
        reviewer="verifier",
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
        layers=[
            LayerResult(
                layer="statistical",
                checks=[
                    CheckResult(
                        check_id="leakage",
                        status="pass",
                        score=1.0,
                        evidence={},
                        message="clean split",
                        duration_ms=10,
                    )
                ],
            ),
            LayerResult(
                layer="policy",
                checks=[
                    CheckResult(
                        check_id="pii_exposure",
                        status="fail",
                        score=0.0,
                        evidence={"detected": ["email"]},
                        message="PII found in deliverable",
                        duration_ms=12,
                    )
                ],
            ),
        ],
        confidence=ConfidenceBand(score=0.42, rationale="policy violation dominates"),
    )

    assert verdict.category == "orchestrator"
    assert verdict.overall == "fail"
    assert verdict.result == "fail"
    assert verdict.summary == "policy violation dominates"
