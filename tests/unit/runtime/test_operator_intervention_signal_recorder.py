"""Tests for operator_intervention ingestion via LearningTaskContractFailureSignalRecorder."""

from __future__ import annotations

import shutil
from pathlib import Path

from ds_agent.domain.learning.failure_taxonomy import (
    FailureClass,
    FailureTaxonomyItem,
    classify_warning_type,
)
from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
from ds_agent.runtime.task_contract_failure_signal_recorder import (
    LearningTaskContractFailureSignalRecorder,
)


def _make_workspace(name: str) -> Path:
    workspace = (Path.cwd() / name).resolve()
    shutil.rmtree(workspace, ignore_errors=True)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


# ── basic ingestion ───────────────────────────────────────────────────────────


def test_operator_intervention_forced_transition_persists_learning_item() -> None:
    workspace = _make_workspace("op_intervention_forced_transition_workspace")
    store: SqliteLearningStore | None = None
    try:
        store = SqliteLearningStore(workspace / "learning.db")
        recorder = LearningTaskContractFailureSignalRecorder(store)

        recorder.record_operator_intervention(
            task_id="TC-2026-999",
            session_id="sess-1",
            run_id="run-3",
            intervention_kind="forced_transition",
            reason="Operator overrode review gate for urgent business deadline",
            metadata={"transition_to": "review", "patch_fields": []},
        )

        items = store.list_items(limit=10)
        assert len(items) == 1
        item = items[0]
        assert item.title == "Harness warning: operator_intervention_forced_transition"
        assert item.metadata["warningType"] == "operator_intervention_forced_transition"
        assert item.metadata["failureSourceKind"] == "operator_intervention"
        assert item.metadata["failureSignalType"] == "forced_transition"
        assert item.metadata["failureSourceRef"] == "TC-2026-999"
        assert item.metadata["surface"] == "operator_intervention"
        assert len(item.metadata["sourceRefs"]) == 1
        assert item.metadata["sourceRefs"][0].startswith(
            "operator_intervention:TC-2026-999:forced_transition:"
        )
    finally:
        if store is not None:
            store._conn.close()
        shutil.rmtree(workspace, ignore_errors=True)


def test_operator_intervention_patch_override_persists_learning_item() -> None:
    workspace = _make_workspace("op_intervention_patch_override_workspace")
    store: SqliteLearningStore | None = None
    try:
        store = SqliteLearningStore(workspace / "learning.db")
        recorder = LearningTaskContractFailureSignalRecorder(store)

        recorder.record_operator_intervention(
            task_id="TC-2026-888",
            session_id="sess-2",
            run_id=None,
            intervention_kind="patch_override",
            reason="Correcting assumption after stakeholder meeting",
            metadata={"patch_fields": ["business_goal", "allowed_data_sources"]},
        )

        items = store.list_items(limit=10)
        assert len(items) == 1
        item = items[0]
        assert item.metadata["warningType"] == "operator_intervention_patch_override"
        assert item.metadata["failureSourceKind"] == "operator_intervention"
        assert item.metadata["failureSignalType"] == "patch_override"
    finally:
        if store is not None:
            store._conn.close()
        shutil.rmtree(workspace, ignore_errors=True)


def test_operator_intervention_unknown_kind_falls_back_gracefully() -> None:
    workspace = _make_workspace("op_intervention_unknown_kind_workspace")
    store: SqliteLearningStore | None = None
    try:
        store = SqliteLearningStore(workspace / "learning.db")
        recorder = LearningTaskContractFailureSignalRecorder(store)

        recorder.record_operator_intervention(
            task_id="TC-2026-777",
            session_id=None,
            run_id=None,
            intervention_kind="some_new_kind",
            reason="Ad-hoc admin action",
        )

        items = store.list_items(limit=10)
        assert len(items) == 1
        assert items[0].metadata["warningType"] == "operator_intervention_unknown"
        assert items[0].metadata["failureSignalType"] == "some_new_kind"
    finally:
        if store is not None:
            store._conn.close()
        shutil.rmtree(workspace, ignore_errors=True)


# ── recurrence / signature deduplication ─────────────────────────────────────


def test_operator_intervention_same_reason_collapses_into_single_recurrence() -> None:
    """Two identical interventions (same task + kind + reason) -> recurrenceCount = 1.

    The signature is stable across identical inputs so the second ingest merges
    into the existing item instead of creating a second one.
    """
    workspace = _make_workspace("op_intervention_recurrence_workspace")
    store: SqliteLearningStore | None = None
    try:
        store = SqliteLearningStore(workspace / "learning.db")
        recorder = LearningTaskContractFailureSignalRecorder(store)

        for _ in range(2):
            recorder.record_operator_intervention(
                task_id="TC-2026-555",
                session_id="sess-a",
                run_id="run-1",
                intervention_kind="forced_transition",
                reason="Same recurring override reason",
            )

        items = store.list_items(limit=10)
        assert len(items) == 1
        # Identical source-refs: recurrenceCount stays 1 (idempotent merge)
        assert items[0].metadata["recurrenceCount"] == 1
    finally:
        if store is not None:
            store._conn.close()
        shutil.rmtree(workspace, ignore_errors=True)


def test_operator_intervention_different_reasons_create_separate_items() -> None:
    """Two interventions with different reasons produce two learning items."""
    workspace = _make_workspace("op_intervention_distinct_reasons_workspace")
    store: SqliteLearningStore | None = None
    try:
        store = SqliteLearningStore(workspace / "learning.db")
        recorder = LearningTaskContractFailureSignalRecorder(store)

        recorder.record_operator_intervention(
            task_id="TC-2026-444",
            session_id="sess-b",
            run_id=None,
            intervention_kind="forced_transition",
            reason="First distinct reason for override",
        )
        recorder.record_operator_intervention(
            task_id="TC-2026-444",
            session_id="sess-b",
            run_id=None,
            intervention_kind="forced_transition",
            reason="Second distinct reason for override",
        )

        items = store.list_items(limit=10)
        assert len(items) == 2
    finally:
        if store is not None:
            store._conn.close()
        shutil.rmtree(workspace, ignore_errors=True)


# ── GC classifier ─────────────────────────────────────────────────────────────


def test_classify_operator_intervention_warning_types_map_to_policy() -> None:
    """All operator_intervention warning types classify as POLICY."""
    warning_types = [
        "operator_intervention_forced_transition",
        "operator_intervention_patch_override",
        "operator_intervention_assumption_edit",
        "operator_intervention_unknown",
    ]
    for wt in warning_types:
        assert classify_warning_type(wt) == FailureClass.POLICY, (
            f"{wt} should map to POLICY, got {classify_warning_type(wt)}"
        )


def test_classify_unknown_operator_intervention_prefix_maps_to_policy() -> None:
    """Any warning type starting with operator_intervention_ maps to POLICY via fallback."""
    assert classify_warning_type("operator_intervention_future_kind") == FailureClass.POLICY


def test_failure_taxonomy_item_from_operator_intervention_learning_item() -> None:
    """FailureTaxonomyItem.from_learning_item projects operator_intervention correctly."""
    workspace = _make_workspace("op_intervention_taxonomy_workspace")
    store: SqliteLearningStore | None = None
    try:
        store = SqliteLearningStore(workspace / "learning.db")
        recorder = LearningTaskContractFailureSignalRecorder(store)

        recorder.record_operator_intervention(
            task_id="TC-2026-333",
            session_id="sess-c",
            run_id="run-99",
            intervention_kind="forced_transition",
            reason="Taxonomy projection test",
        )

        items = store.list_items(limit=10)
        assert len(items) == 1
        taxonomy_item = FailureTaxonomyItem.from_learning_item(items[0])
        assert taxonomy_item.failure_class == FailureClass.POLICY
        assert taxonomy_item.source_kind == "operator_intervention"
        assert taxonomy_item.warning_type == "operator_intervention_forced_transition"
        assert taxonomy_item.source_ref == "TC-2026-333"
        assert "operator_intervention" in taxonomy_item.surfaces
    finally:
        if store is not None:
            store._conn.close()
        shutil.rmtree(workspace, ignore_errors=True)
