from datetime import UTC, datetime

from ds_agent.domain.entities.review_verdict import (
    ConfidenceBand,
    Issue,
    LayerResult,
    ReviewVerdict,
)
from ds_agent.presentation.verdict_presenters import (
    pick_effective_review_verdict,
    render_verdict_report,
    render_verdict_snapshot,
)


def _verdict(
    *,
    verdict_id: str,
    created_at: datetime,
    category: str = "orchestrator",
    judge_mode: str | None = None,
) -> ReviewVerdict:
    metadata = {"judge_mode": judge_mode} if judge_mode is not None else {}
    return ReviewVerdict(
        verdict_id=verdict_id,
        task_id="TC-2026-001",
        category=category,
        result="warn",
        reviewer="verifier",
        summary="Owner sign-off is still required.",
        created_at=created_at,
        confidence=ConfidenceBand(score=0.65),
        layers=[LayerResult(layer="policy", overall="warn", score=0.5)],
        blocking_issues=[Issue(message="Needs owner sign-off", layer="policy", blocking=True)],
        metadata=metadata,
    )


def test_render_verdict_snapshot_includes_judge_mode_when_available() -> None:
    verdict = _verdict(
        verdict_id="RV-2026002",
        created_at=datetime(2026, 4, 16, 12, tzinfo=UTC),
        judge_mode="llm",
    )

    assert render_verdict_snapshot(verdict) == "warn | confidence=medium | blockers=1 | judge=llm"


def test_render_verdict_report_lists_layers_and_blockers() -> None:
    verdict = _verdict(
        verdict_id="RV-2026002",
        created_at=datetime(2026, 4, 16, 12, tzinfo=UTC),
        judge_mode="heuristic_fallback",
    )

    rendered = render_verdict_report(verdict, compact=True)

    assert "Review verdict: RV-2026002" in rendered
    assert (
        "Result: warn | confidence=medium (0.65) | blockers=1 | judge=heuristic_fallback"
        in rendered
    )
    assert "Layers: policy=warn" in rendered
    assert "  - [medium] policy: Needs owner sign-off" in rendered


def test_pick_effective_review_verdict_prefers_latest_orchestrator() -> None:
    early = _verdict(verdict_id="RV-2026001", created_at=datetime(2026, 4, 16, 9, tzinfo=UTC))
    later_narrative = _verdict(
        verdict_id="RV-2026003",
        created_at=datetime(2026, 4, 16, 13, tzinfo=UTC),
        category="narrative",
    )
    later_orchestrator = _verdict(
        verdict_id="RV-2026002",
        created_at=datetime(2026, 4, 16, 11, tzinfo=UTC),
    )

    picked = pick_effective_review_verdict([early, later_narrative, later_orchestrator])

    assert picked is not None
    assert picked.verdict_id == "RV-2026002"
