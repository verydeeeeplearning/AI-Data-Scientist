from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.domain.entities.review_verdict import (
    CheckResult,
    ConfidenceBand,
    Issue,
    LayerResult,
    ReviewVerdict,
)
from ds_agent.domain.entities.shadow_comparison import (
    ShadowComparisonItem,
    ShadowComparisonRecord,
)
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
from ds_agent.infrastructure.persistence.shadow_comparison_repo import (
    SqliteShadowComparisonRepository,
)
from ds_agent.infrastructure.persistence.verdict_repo import SqliteVerdictRepository
from ds_agent.runtime.learning_failure_signal_sync import PersistedFailureSignalSync
from ds_agent.runtime.learning_governance_scheduler import (
    build_learning_governance_status_payload,
)
from ds_agent.runtime.policy_store import JsonPolicyStore


def test_persisted_failure_signal_sync_is_idempotent_for_replayed_sources() -> None:
    workspace = (Path.cwd() / "phase5_signal_sync_test_workspace").resolve()
    store: SqliteLearningStore | None = None

    try:
        shutil.rmtree(workspace, ignore_errors=True)
        workspace.mkdir(parents=True, exist_ok=True)
        store = SqliteLearningStore.for_workspace(str(workspace))
        verdict_repo = SqliteVerdictRepository.for_workspace(str(workspace))
        shadow_repo = SqliteShadowComparisonRepository.for_workspace(str(workspace))

        verdict_repo.save(_review_verdict())
        shadow_repo.save(_shadow_record())

        sync = PersistedFailureSignalSync(
            store=store,
            workspace_dir=workspace,
            verdict_repo=verdict_repo,
            shadow_repo=shadow_repo,
        )
        sync.sync(limit=50)
        sync.sync(limit=50)

        items = store.list_items(limit=10)
        assert len(items) == 2

        metadata_by_type = {item.metadata["warningType"]: item.metadata for item in items}
        assert metadata_by_type["baseline_missing"]["failureSourceKind"] == "review_verdict"
        assert metadata_by_type["baseline_missing"]["failureSignalType"] == "baseline_comparison"
        assert metadata_by_type["baseline_missing"]["recurrenceCount"] == 1
        assert metadata_by_type["baseline_missing"]["sourceRefs"] == [
            "review_verdict:RV-2026001:baseline_comparison"
        ]

        assert metadata_by_type["temporal_join"]["failureSourceKind"] == "shadow_mismatch"
        assert metadata_by_type["temporal_join"]["failureSignalType"] == "temporal_join_guard"
        assert metadata_by_type["temporal_join"]["recurrenceCount"] == 1
        assert metadata_by_type["temporal_join"]["sourceRefs"] == [
            "shadow_mismatch:SC-2026001:temporal_join_guard:legacy_only"
        ]
    finally:
        if store is not None:
            store._conn.close()
        shutil.rmtree(workspace, ignore_errors=True)


def test_learning_governance_status_syncs_persisted_review_verdict_sources() -> None:
    workspace = (Path.cwd() / "phase5_signal_status_test_workspace").resolve()
    store: SqliteLearningStore | None = None

    try:
        shutil.rmtree(workspace, ignore_errors=True)
        workspace.mkdir(parents=True, exist_ok=True)
        store = SqliteLearningStore.for_workspace(str(workspace))
        verdict_repo = SqliteVerdictRepository.for_workspace(str(workspace))
        verdict_repo.save(_review_verdict(verdict_id="RV-2026002"))

        payload = build_learning_governance_status_payload(
            policy_store=JsonPolicyStore(base_dir=workspace),
            store=store,
            workspace_dir=workspace,
            history_limit=5,
        )

        assert payload["backlog"]["activeWarningItems"] == 1
        assert payload["backlog"]["activeWarningRecurrences"] == 1
        assert payload["backlog"]["warningTypes"] == ["baseline_missing"]
        assert payload["backlog"]["failureSignalTypes"] == ["baseline_comparison"]
        assert payload["backlog"]["sourceKinds"] == ["review_verdict"]
    finally:
        if store is not None:
            store._conn.close()
        shutil.rmtree(workspace, ignore_errors=True)


def _review_verdict(*, verdict_id: str = "RV-2026001") -> ReviewVerdict:
    return ReviewVerdict(
        verdict_id=verdict_id,
        task_id="TC-2026-001",
        reviewer="verifier",
        created_at=datetime(2026, 4, 22, 9, 0, tzinfo=UTC),
        run_id="run-2026-1",
        layers=[
            LayerResult(
                layer="statistical",
                checks=[
                    CheckResult(
                        check_id="baseline_comparison",
                        status="fail",
                        score=0.0,
                        message="Model was trained without a valid baseline comparison.",
                    )
                ],
            )
        ],
        blocking_issues=[
            Issue(
                issue_id="statistical:baseline_comparison",
                layer="statistical",
                check_id="baseline_comparison",
                severity="high",
                message="Baseline comparison failed the verifier gate.",
                blocking=True,
            )
        ],
        confidence=ConfidenceBand(score=0.82, rationale="Baseline miss was deterministic."),
        metadata={"sessionId": "session-review-1"},
    )


def _shadow_record() -> ShadowComparisonRecord:
    return ShadowComparisonRecord(
        comparison_id="SC-2026001",
        verdict_id="RV-2026001",
        task_id="TC-2026-001",
        run_id="run-2026-1",
        session_id="session-review-1",
        created_at=datetime(2026, 4, 22, 9, 0, tzinfo=UTC),
        items=[
            ShadowComparisonItem(
                comparison_key="temporal_join_guard",
                legacy_source="temporal_join_guard_hook",
                verifier_targets=["data_leakage_detection"],
                applicable=True,
                legacy_state="triggered",
                verifier_state="clear",
            )
        ],
    )
