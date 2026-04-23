from __future__ import annotations

from ds_agent.application.learning.harness_warning_ingestor import (
    HarnessWarningIngestor,
    normalize_harness_warning,
)
from ds_agent.domain.learning.learning_item import LearningItemType
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore


def test_normalize_harness_warning_defaults_missing_fields() -> None:
    warning = normalize_harness_warning(
        {"type": "leakage", "message": "Potential target leakage detected."},
        session_id="session-1",
        run_id="run-1",
        surface="ws",
    )

    assert warning is not None
    assert warning.warning_type == "leakage"
    assert warning.severity == "medium"
    assert warning.warning_id.startswith("hw-")
    assert warning.tags == [
        "harness.warning",
        "leakage",
        "severity:medium",
        "surface:ws",
    ]


def test_ingestor_persists_and_deduplicates_harness_warning(tmp_path) -> None:
    store = SqliteLearningStore(tmp_path / "learning.db")
    ingestor = HarnessWarningIngestor(store)

    first = ingestor.ingest(
        {
            "type": "baseline_missing",
            "severity": "high",
            "message": "Model trained without a baseline.",
            "suggestion": "Run DummyClassifier before comparing models.",
        },
        session_id="session-1",
        run_id="run-1",
        surface="ws",
    )
    second = ingestor.ingest(
        {
            "type": "baseline_missing",
            "severity": "high",
            "message": "Model trained without a baseline.",
            "suggestion": "Run DummyClassifier before comparing models.",
        },
        session_id="session-2",
        run_id="run-2",
        surface="ws",
    )

    assert first is not None
    assert second is not None
    assert second.item_id == first.item_id
    items = store.list_items(item_type=LearningItemType.PATTERN)
    assert len(items) == 1
    assert items[0].title == "Harness warning: baseline_missing"
    assert items[0].metadata["warningType"] == "baseline_missing"
    assert items[0].metadata["recurrenceCount"] == 2
    assert items[0].metadata["sessionIds"] == ["session-1", "session-2"]
    assert items[0].metadata["runIds"] == ["run-1", "run-2"]
    assert items[0].metadata["surfaces"] == ["ws"]
