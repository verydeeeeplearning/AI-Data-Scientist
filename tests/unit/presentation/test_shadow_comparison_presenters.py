from datetime import UTC, datetime

from ds_agent.domain.entities.shadow_comparison import (
    ShadowComparisonItem,
    ShadowComparisonRecord,
)
from ds_agent.presentation.shadow_comparison_presenters import (
    pick_effective_shadow_comparison,
    render_shadow_comparison_report,
    render_shadow_comparison_snapshot,
)


def _record(*, comparison_id: str, created_at: datetime) -> ShadowComparisonRecord:
    return ShadowComparisonRecord(
        comparison_id=comparison_id,
        verdict_id="RV-2026001",
        task_id="TC-2026-001",
        run_id="run-1",
        session_id="session-1",
        created_at=created_at,
        items=[
            ShadowComparisonItem(
                comparison_key="baseline_guard",
                legacy_source="baseline_guard_hook",
                verifier_targets=["baseline_comparison"],
                applicable=True,
                legacy_state="clear",
                verifier_state="triggered",
                note="verifier flagged an issue that the legacy hook missed",
            )
        ],
    )


def test_render_shadow_comparison_snapshot_reports_match_and_mismatch_counts() -> None:
    record = _record(
        comparison_id="SC-2026001",
        created_at=datetime(2026, 4, 16, 12, tzinfo=UTC),
    )

    assert render_shadow_comparison_snapshot(record) == "shadow=0% | mismatches=1/1"


def test_render_shadow_comparison_report_lists_mismatches() -> None:
    record = _record(
        comparison_id="SC-2026001",
        created_at=datetime(2026, 4, 16, 12, tzinfo=UTC),
    )

    rendered = render_shadow_comparison_report(record, compact=True)

    assert "Shadow comparison: SC-2026001" in rendered
    assert "Match: 0% | mismatches=1/1" in rendered
    assert "[verifier_only] baseline_guard" in rendered


def test_pick_effective_shadow_comparison_returns_latest_record() -> None:
    early = _record(
        comparison_id="SC-2026001",
        created_at=datetime(2026, 4, 16, 9, tzinfo=UTC),
    )
    later = _record(
        comparison_id="SC-2026002",
        created_at=datetime(2026, 4, 16, 11, tzinfo=UTC),
    )

    picked = pick_effective_shadow_comparison([early, later])

    assert picked is not None
    assert picked.comparison_id == "SC-2026002"
