from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ds_agent.application.learning.harness_warning_ingestor import HarnessWarningIngestor
from ds_agent.application.services.scheduler_service import SchedulerService
from ds_agent.infrastructure.cron_runner import CronRunner
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
from ds_agent.runtime.learning_governance_scheduler import (
    LearningGovernanceScheduler,
    build_learning_governance_status_payload,
)
from ds_agent.runtime.policy_store import JsonPolicyStore
from ds_agent.self_improve.promotion_candidates import JsonPromotionCandidateStore


def _seed_gc_warning(store: SqliteLearningStore) -> None:
    ingestor = HarnessWarningIngestor(store)
    payload = {
        "type": "baseline_missing",
        "severity": "high",
        "message": "No comparison baseline was recorded before training.",
    }
    ingestor.ingest(payload, session_id="learning:sess-1", run_id="run-gc-1", surface="daemon")
    ingestor.ingest(payload, session_id="learning:sess-2", run_id="run-gc-2", surface="daemon")
    ingestor.ingest(payload, session_id="learning:sess-3", run_id="run-gc-3", surface="daemon")


def test_registers_learning_governance_gc_order(tmp_path: Path) -> None:
    scheduler = SchedulerService(
        store=JsonPolicyStore(base_dir=tmp_path),
        cron_runner=CronRunner(),
    )
    adapter = LearningGovernanceScheduler(
        scheduler_service=scheduler,
        store=SqliteLearningStore.for_workspace(str(tmp_path)),
        workspace_dir=tmp_path,
        cron="0 9 * * MON",
        promotion_threshold=4,
        limit=150,
    )

    order = adapter.register()

    assert order.order_id == LearningGovernanceScheduler.ORDER_ID
    assert order.trigger.cron == "0 9 * * MON"
    assert order.scope["job"] == "weekly_gc"
    assert order.scope["promotionThreshold"] == 4
    assert order.scope["limit"] == 150


def test_run_due_executes_gc_loop_and_records_history(tmp_path: Path) -> None:
    learning_store = SqliteLearningStore.for_workspace(str(tmp_path))
    _seed_gc_warning(learning_store)
    policy_store = JsonPolicyStore(base_dir=tmp_path)
    scheduler = SchedulerService(
        store=policy_store,
        cron_runner=CronRunner(),
    )
    adapter = LearningGovernanceScheduler(
        scheduler_service=scheduler,
        store=learning_store,
        workspace_dir=tmp_path,
        cron="* * * * *",
        promotion_threshold=3,
        limit=50,
    )
    order = adapter.register()
    order.next_run_at = 0.0
    policy_store.upsert_standing_order(order)

    result = adapter.run_due(now=datetime(2026, 4, 21, 9, 0, tzinfo=UTC))

    assert result is not None
    assert result.total_items == 1
    assert result.total_recurrences == 3
    assert result.report_path is not None
    assert Path(result.report_path).exists()
    assert [item.value for item in result.promotion_candidate_classes] == ["missing_baseline"]
    assert [item.candidate_id for item in result.registered_skill_candidates] == [
        "failure-taxonomy-missing_baseline"
    ]

    item = learning_store.list_items(limit=5)[0]
    assert item.metadata["failureTaxonomyClass"] == "missing_baseline"
    assert item.metadata["failureTaxonomyPromotionCandidate"] is True
    assert item.metadata["failureTaxonomyCandidateId"] == "failure-taxonomy-missing_baseline"

    candidate_store = JsonPromotionCandidateStore.for_workspace(str(tmp_path))
    candidate = candidate_store.get("failure-taxonomy-missing_baseline")
    assert candidate is not None
    assert candidate.status == "pending_promotion"
    assert Path(candidate.pending_path).exists()

    history = scheduler.list_history(LearningGovernanceScheduler.ORDER_ID, limit=5)
    statuses = [entry["status"] for entry in history]
    assert "completed" in statuses
    assert "dispatched" in statuses


def test_build_learning_governance_status_payload_summarizes_backlog_and_history(
    tmp_path: Path,
) -> None:
    learning_store = SqliteLearningStore.for_workspace(str(tmp_path))
    _seed_gc_warning(learning_store)
    policy_store = JsonPolicyStore(base_dir=tmp_path)
    scheduler = SchedulerService(
        store=policy_store,
        cron_runner=CronRunner(),
    )
    adapter = LearningGovernanceScheduler(
        scheduler_service=scheduler,
        store=learning_store,
        workspace_dir=tmp_path,
        cron="* * * * *",
        promotion_threshold=3,
        limit=50,
    )
    order = adapter.register()
    order.next_run_at = 0.0
    policy_store.upsert_standing_order(order)

    adapter.run_due(now=datetime(2026, 4, 21, 9, 0, tzinfo=UTC))

    payload = build_learning_governance_status_payload(
        policy_store=policy_store,
        store=learning_store,
        workspace_dir=tmp_path,
        history_limit=5,
    )

    assert payload["standingOrder"]["orderId"] == LearningGovernanceScheduler.ORDER_ID
    assert payload["backlog"]["activeWarningItems"] == 1
    assert payload["backlog"]["activeWarningRecurrences"] == 3
    assert payload["backlog"]["promotionCandidateItems"] == 1
    assert payload["backlog"]["promotionCandidateClasses"] == ["missing_baseline"]
    assert payload["latestCompletedRun"]["status"] == "completed"
    assert payload["latestCompletedRun"]["totalItems"] == 1
    assert payload["latestCompletedRun"]["totalRecurrences"] == 3
    assert payload["latestReport"]["name"].startswith("GC_REPORT_")
