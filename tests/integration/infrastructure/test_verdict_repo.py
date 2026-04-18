from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.infrastructure.persistence.verdict_repo import SqliteVerdictRepository


def test_sqlite_verdict_repository_round_trip(tmp_path) -> None:
    repo = SqliteVerdictRepository(tmp_path / "review_verdicts.db")
    first = ReviewVerdict(
        verdict_id="RV-1",
        task_id="TC-2026-001",
        category="orchestrator",
        reviewer="verifier",
        created_at=datetime(2026, 4, 16, 9, 0, tzinfo=UTC),
        summary="first verdict",
    )
    second = ReviewVerdict(
        verdict_id="RV-2",
        task_id="TC-2026-001",
        category="orchestrator",
        reviewer="verifier",
        created_at=datetime(2026, 4, 16, 10, 0, tzinfo=UTC),
        summary="second verdict",
    )

    repo.save(first)
    repo.save(second)

    loaded = repo.get("RV-1")
    task_verdicts = repo.list_for_task("TC-2026-001")

    assert loaded is not None
    assert loaded.summary == "first verdict"
    assert [verdict.verdict_id for verdict in task_verdicts] == ["RV-2", "RV-1"]
