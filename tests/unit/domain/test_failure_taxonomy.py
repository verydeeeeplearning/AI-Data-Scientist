from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.learning.failure_taxonomy import (
    FailureClass,
    FailureTaxonomyItem,
    classify_warning_type,
)
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)


def test_classify_warning_type_maps_known_warning_types() -> None:
    assert classify_warning_type("leakage") is FailureClass.LEAKAGE
    assert classify_warning_type("temporal_join") is FailureClass.LEAKAGE
    assert classify_warning_type("baseline_comparison") is FailureClass.MISSING_BASELINE
    assert classify_warning_type("overfitting_gap") is FailureClass.OVERFITTING
    assert classify_warning_type("distribution_drift") is FailureClass.DATA_QUALITY
    assert classify_warning_type("baseline_missing") is FailureClass.MISSING_BASELINE
    assert classify_warning_type("claim_traceability") is FailureClass.NARRATIVE


def test_classify_warning_type_defaults_to_uncategorized() -> None:
    assert classify_warning_type("unknown_warning") is FailureClass.UNCATEGORIZED
    assert classify_warning_type(None) is FailureClass.UNCATEGORIZED


def test_failure_taxonomy_item_projects_learning_item_metadata() -> None:
    item = LearningItem(
        item_id="LI-001",
        item_type=LearningItemType.PATTERN,
        status=LearningItemStatus.PROPOSED,
        title="Harness warning: leakage",
        content="Potential target leakage detected.",
        signature="sig:1",
        source=SourceInfo(session_id="session-a"),
        tags=["harness.warning", "leakage"],
        created_at=datetime(2026, 4, 21, tzinfo=UTC),
        updated_at=datetime(2026, 4, 21, 1, 0, tzinfo=UTC),
        metadata={
            "warningType": "leakage",
            "severity": "high",
            "failureSourceKind": "review_verdict",
            "failureSourceRef": "RV-001",
            "message": "Potential target leakage detected.",
            "recurrenceCount": 3,
            "sessionIds": ["session-a", "session-b"],
            "runIds": ["run-a"],
            "surfaces": ["ws", "daemon"],
        },
    )

    projected = FailureTaxonomyItem.from_learning_item(item)

    assert projected.item_id == "LI-001"
    assert projected.failure_class is FailureClass.LEAKAGE
    assert projected.warning_type == "leakage"
    assert projected.source_kind == "review_verdict"
    assert projected.source_ref == "RV-001"
    assert projected.severity == "high"
    assert projected.recurrence_count == 3
    assert projected.session_ids == ("session-a", "session-b")
    assert projected.run_ids == ("run-a",)
    assert projected.surfaces == ("ws", "daemon")
