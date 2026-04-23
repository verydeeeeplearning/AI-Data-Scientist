from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.entities.shadow_comparison import (
    ShadowComparisonItem,
    ShadowComparisonRecord,
)
from ds_agent.infrastructure.persistence.shadow_comparison_repo import (
    SqliteShadowComparisonRepository,
)


def _record() -> ShadowComparisonRecord:
    return ShadowComparisonRecord(
        comparison_id="SC-2026001",
        verdict_id="RV-2026001",
        task_id="TC-2026-001",
        run_id="run-1",
        session_id="session-1",
        created_at=datetime(2026, 4, 16, tzinfo=UTC),
        items=[
            ShadowComparisonItem(
                comparison_key="baseline_guard",
                legacy_source="baseline_guard_hook",
                verifier_targets=["baseline_comparison"],
                applicable=True,
                legacy_state="clear",
                verifier_state="triggered",
            )
        ],
    )


def test_shadow_comparison_repo_round_trip(tmp_path) -> None:
    repo = SqliteShadowComparisonRepository.for_workspace(str(tmp_path))
    record = _record()

    repo.save(record)

    loaded = repo.get(record.comparison_id)
    assert loaded is not None
    assert loaded.comparison_id == record.comparison_id
    assert repo.list_for_task(record.task_id)[0].comparison_id == record.comparison_id
    assert repo.list_for_verdict(record.verdict_id)[0].comparison_id == record.comparison_id
    assert repo.list_recent(limit=1)[0].comparison_id == record.comparison_id
