from __future__ import annotations

from ds_agent.domain.learning.learning_item import LearningItemType
from ds_agent.gateway.daemon import AutonomousCallbacks
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore


def test_autonomous_callbacks_ingest_harness_warning(tmp_path) -> None:
    callbacks = AutonomousCallbacks("daemon", workspace_dir=str(tmp_path))

    callbacks.emit_event(
        "task.started",
        {
            "sessionId": "daemon:session-1",
            "runId": "run-daemon-1",
            "surface": "daemon",
        },
    )
    callbacks.emit_event(
        "harness.warning",
        {
            "type": "pii_detected",
            "message": "Potential PII found in exported payload.",
        },
    )

    store = SqliteLearningStore.for_workspace(str(tmp_path))
    items = store.list_items(item_type=LearningItemType.PATTERN)
    assert len(items) == 1
    assert items[0].metadata["sessionId"] == "daemon:session-1"
    assert items[0].metadata["runId"] == "run-daemon-1"
    assert items[0].metadata["warningType"] == "pii_detected"
