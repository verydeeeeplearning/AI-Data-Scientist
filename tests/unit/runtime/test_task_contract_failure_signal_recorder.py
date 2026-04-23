from __future__ import annotations

import shutil
from pathlib import Path

from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
from ds_agent.runtime.task_contract_failure_signal_recorder import (
    LearningTaskContractFailureSignalRecorder,
)


def test_task_contract_failure_signal_recorder_persists_review_gate_failure() -> None:
    workspace = (Path.cwd() / "phase5_task_contract_failure_signal_workspace").resolve()
    store: SqliteLearningStore | None = None

    try:
        shutil.rmtree(workspace, ignore_errors=True)
        workspace.mkdir(parents=True, exist_ok=True)
        store = SqliteLearningStore(workspace / "learning.db")
        recorder = LearningTaskContractFailureSignalRecorder(store)

        recorder.record_transition_failure(
            task_id="TC-2026-001",
            session_id="session-1",
            run_id="run-2",
            transition_to="review",
            error_code="INVALID_TRANSITION",
            message="Latest auto verifier verdict must match the active run before moving to review",
            metadata={
                "kind": "verifier_review_gate",
                "transition_target": "review",
                "failure": "stale_review_verdict",
                "expected_run_id": "run-2",
                "latest_verdict_id": "RV-1",
                "latest_verdict_run_id": "run-1",
            },
        )

        items = store.list_items(limit=10)
        assert len(items) == 1
        assert items[0].title == "Harness warning: review_gate_stale_verdict"
        assert items[0].metadata["warningType"] == "review_gate_stale_verdict"
        assert items[0].metadata["failureSourceKind"] == "task_contract_gate"
        assert items[0].metadata["failureSignalType"] == "stale_review_verdict"
        assert items[0].metadata["failureSourceRef"] == "TC-2026-001"
        assert items[0].metadata["surface"] == "task_contract_gate"
        assert items[0].metadata["sourceRefs"] == [
            "task_contract_gate:TC-2026-001:review:stale_review_verdict:RV-1:run-2:run-1"
        ]
    finally:
        if store is not None:
            store._conn.close()
        shutil.rmtree(workspace, ignore_errors=True)
