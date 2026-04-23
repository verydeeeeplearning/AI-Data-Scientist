"""Learning governance tools for knowledge quality management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ds_agent.tools.registry import tool

if TYPE_CHECKING:
    from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore

_learning_store: SqliteLearningStore | None = None


# ---------------------------------------------------------------------------
# Official flag-off policy: Read-only-visible (adopted 2026-04-22, Gap 5A-1)
#
#   flag OFF (DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1 unset / falsy):
#     - Read-only tools (list_learning_inbox, get_learning_item,
#       list_promotions, list_deprecations, get_gc_report,
#       get_learning_governance_status) remain accessible.
#     - Mutation tools (review_learning_item, rollback_promotion,
#       run_gc_loop, finalize_learning_candidate_promotion) return DISABLED.
#
#   flag ON (DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1=1/true/yes):
#     - All tools active.
#
# Implementation: _get_learning_store(require_mutation=True) returns None
# (→ DISABLED) when flag is OFF; _get_learning_store(require_mutation=False)
# always returns the store, enabling read-only access regardless of flag.
# ---------------------------------------------------------------------------


def _governance_mutation_enabled() -> bool:
    return os.environ.get("DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _get_learning_store(*, require_mutation: bool = False) -> SqliteLearningStore | None:
    global _learning_store
    if _learning_store is not None:
        if require_mutation and not _governance_mutation_enabled():
            return None
        return _learning_store
    if require_mutation and not _governance_mutation_enabled():
        return None
    from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
    from ds_agent.tools.path_utils import get_active_workspace

    workspace = get_active_workspace()
    _learning_store = SqliteLearningStore.for_workspace(
        str(workspace) if workspace else None,
    )
    return _learning_store


def _get_gc_workspace_path() -> str | None:
    from ds_agent.tools.path_utils import get_active_workspace

    workspace = get_active_workspace()
    return str(workspace) if workspace is not None else None


def _get_active_custom_skills_dir() -> Path | None:
    override = os.environ.get("DS_AGENT_ACTIVE_CUSTOM_SKILLS_DIR", "").strip()
    if not override:
        return None
    return Path(override).expanduser().resolve()


def _ok(**payload: object) -> str:
    return json.dumps({"ok": True, **payload}, ensure_ascii=False)


def _err(code: str, msg: str) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": msg}},
        ensure_ascii=False,
    )


def _serialize_learning_item_summary(
    item: Any,
    *,
    priority_score: float,
) -> dict[str, object]:
    return {
        "item_id": item.item_id,
        "type": item.item_type.value,
        "status": item.status.value,
        "title": item.title,
        "priority_score": priority_score,
        "evidence_count": len(item.evidence),
        "conflict_count": len(item.conflict_refs),
        "scope": item.scope,
        "tags": item.tags,
        "created_at": item.created_at.isoformat(),
        "metadata": dict(item.metadata or {}),
    }


def _serialize_learning_item_detail(
    item: Any,
    *,
    content_limit: int = 500,
) -> dict[str, object]:
    return {
        "item_id": item.item_id,
        "type": item.item_type.value,
        "status": item.status.value,
        "title": item.title,
        "content": item.content[:content_limit],
        "signature": item.signature,
        "scope": item.scope,
        "review_count": item.review_count,
        "evidence_count": len(item.evidence),
        "conflict_count": len(item.conflict_refs),
        "tags": item.tags,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "metadata": dict(item.metadata or {}),
    }


@tool(
    name="list_learning_inbox",
    description="List learning items in the governance inbox with priority scores.",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "default": "proposed"},
            "item_type": {"type": "string", "default": "all"},
            "limit": {"type": "integer", "default": 20},
        },
    },
    safety_level="safe",
)
def list_learning_inbox(
    status: str = "proposed",
    item_type: str = "all",
    limit: int = 20,
) -> str:
    """List learning items in the governance inbox with priority scores.

    Args:
        status: Filter by status (proposed/under_review/all).
        item_type: Filter by type (pattern/kb_entry/custom_skill/all).
        limit: Maximum items to return.
    """
    store = _get_learning_store()
    if store is None:
        return _err("DISABLED", "Self-improve governance is not enabled.")

    from datetime import UTC, datetime

    from ds_agent.application.learning.learning_inbox import LearningInboxUseCase
    from ds_agent.domain.learning.learning_item import (
        LearningItemStatus,
        LearningItemType,
    )

    class _Clock:
        def now(self) -> datetime:
            return datetime.now(UTC)

    status_filter = None
    if status != "all":
        try:
            status_filter = [LearningItemStatus(status)]
        except ValueError:
            return _err("INVALID_STATUS", f"Unknown status: {status}")

    type_filter = None
    if item_type != "all":
        try:
            type_filter = LearningItemType(item_type)
        except ValueError:
            return _err("INVALID_TYPE", f"Unknown type: {item_type}")

    uc = LearningInboxUseCase(store, _Clock())
    scored = uc.execute(
        status_filter=status_filter,
        item_type_filter=type_filter,
        limit=limit,
    )
    items = [
        _serialize_learning_item_summary(s.item, priority_score=s.priority_score) for s in scored
    ]
    return _ok(items=items, count=len(items))


@tool(
    name="review_learning_item",
    description="Review a learning item (approve/modify/reject).",
    parameters={
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
            "decision": {"type": "string"},
            "comment": {"type": "string", "default": ""},
            "reviewer": {"type": "string", "default": "llm"},
        },
        "required": ["item_id", "decision"],
    },
    safety_level="caution",
)
def review_learning_item(
    item_id: str,
    decision: str,
    comment: str = "",
    reviewer: str = "llm",
) -> str:
    """Review a learning item (approve/modify/reject).

    Args:
        item_id: Learning item ID.
        decision: Review decision (approve/modify/reject).
        comment: Optional review comment.
        reviewer: Who is reviewing.
    """
    store = _get_learning_store(require_mutation=True)
    if store is None:
        return _err("DISABLED", "Self-improve governance is not enabled.")

    from datetime import UTC, datetime

    from ds_agent.application.learning.review_learning_item import (
        ReviewLearningItemUseCase,
    )
    from ds_agent.domain.learning.review_event import ReviewChecklist, ReviewDecision

    class _Clock:
        def now(self) -> datetime:
            return datetime.now(UTC)

    try:
        dec = ReviewDecision(decision)
    except ValueError:
        return _err("INVALID_DECISION", f"Unknown decision: {decision}")

    checklist = (
        ReviewChecklist(
            evidence_sufficient=True,
            no_unresolved_conflicts=True,
            scope_appropriate=True,
            content_accurate=True,
        )
        if dec == ReviewDecision.APPROVE
        else None
    )

    uc = ReviewLearningItemUseCase(store, _Clock())
    try:
        updated, event = uc.execute(
            item_id=item_id,
            decision=dec,
            reviewer=reviewer,
            checklist=checklist,
            comment=comment,
        )
    except ValueError as exc:
        return _err("REVIEW_ERROR", str(exc))

    return _ok(
        item_id=updated.item_id,
        new_status=updated.status.value,
        event_id=event.event_id,
    )


@tool(
    name="get_learning_item",
    description="Get details of a single learning item.",
    parameters={
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
        },
        "required": ["item_id"],
    },
    safety_level="safe",
)
def get_learning_item(item_id: str) -> str:
    """Get details of a single learning item.

    Args:
        item_id: Learning item ID.
    """
    store = _get_learning_store()
    if store is None:
        return _err("DISABLED", "Self-improve governance is not enabled.")

    item = store.get_item(item_id)
    if item is None:
        return _err("NOT_FOUND", f"Learning item {item_id} not found.")

    return _ok(**_serialize_learning_item_detail(item))


@tool(
    name="list_promotions",
    description="List recent promotion records.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "default": 20},
        },
    },
    safety_level="safe",
)
def list_promotions(limit: int = 20) -> str:
    """List recent promotion records.

    Args:
        limit: Maximum records to return.
    """
    store = _get_learning_store()
    if store is None:
        return _err("DISABLED", "Self-improve governance is not enabled.")

    records = store.list_promotion_records(limit=limit)
    items = [
        {
            "record_id": r.record_id,
            "item_id": r.item_id,
            "type": r.item_type.value,
            "eval_score": r.eval_score,
            "promoted_at": r.promoted_at.isoformat(),
        }
        for r in records
    ]
    return _ok(records=items, count=len(items))


@tool(
    name="list_deprecations",
    description="List recent deprecation records.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "default": 20},
        },
    },
    safety_level="safe",
)
def list_deprecations(limit: int = 20) -> str:
    """List recent deprecation records.

    Args:
        limit: Maximum records to return.
    """
    store = _get_learning_store()
    if store is None:
        return _err("DISABLED", "Self-improve governance is not enabled.")

    records = store.list_deprecation_records(limit=limit)
    items = [
        {
            "record_id": r.record_id,
            "item_id": r.item_id,
            "reason": r.reason.value,
            "mode": r.mode.value,
            "failure_count": r.failure_count,
            "deprecated_at": r.deprecated_at.isoformat(),
        }
        for r in records
    ]
    return _ok(records=items, count=len(items))


@tool(
    name="rollback_promotion",
    description="Rollback a promoted learning item to deprecated state.",
    parameters={
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
            "reason": {"type": "string", "default": "manual rollback"},
        },
        "required": ["item_id"],
    },
    safety_level="caution",
)
def rollback_promotion(
    item_id: str,
    reason: str = "manual rollback",
) -> str:
    """Rollback a promoted learning item to deprecated state.

    Args:
        item_id: Learning item ID to rollback.
        reason: Reason for rollback.
    """
    store = _get_learning_store(require_mutation=True)
    if store is None:
        return _err("DISABLED", "Self-improve governance is not enabled.")

    from datetime import UTC, datetime

    from ds_agent.application.learning.rollback_promotion import (
        RollbackPromotionUseCase,
    )

    class _Clock:
        def now(self) -> datetime:
            return datetime.now(UTC)

    uc = RollbackPromotionUseCase(store, _Clock())
    try:
        updated, dep_record = uc.execute(item_id=item_id, reason=reason)
    except ValueError as exc:
        return _err("ROLLBACK_ERROR", str(exc))

    return _ok(
        item_id=updated.item_id,
        new_status=updated.status.value,
        deprecation_record_id=dep_record.record_id,
    )


@tool(
    name="run_gc_loop",
    description="Classify persisted governed failure signals and generate a GC report.",
    parameters={
        "type": "object",
        "properties": {
            "promotion_threshold": {"type": "integer", "default": 3},
            "limit": {"type": "integer", "default": 200},
        },
    },
    safety_level="safe",
)
def run_gc_loop(
    promotion_threshold: int = 3,
    limit: int = 200,
) -> str:
    """Classify persisted governed failure signals and generate a GC report."""

    store = _get_learning_store(require_mutation=True)
    if store is None:
        return _err("DISABLED", "Self-improve governance is not enabled.")

    workspace_path = _get_gc_workspace_path()
    if workspace_path is None:
        return _err("NO_WORKSPACE", "No active workspace is available for GC reports.")

    from datetime import UTC, datetime

    from ds_agent.application.learning.failure_taxonomy_gc import (
        FailureTaxonomyGCLoopUseCase,
    )
    from ds_agent.runtime.learning_failure_signal_sync import PersistedFailureSignalSync

    class _Clock:
        def now(self) -> datetime:
            return datetime.now(UTC)

    try:
        result = FailureTaxonomyGCLoopUseCase(
            store,
            _Clock(),
            workspace_path,
            signal_sync=PersistedFailureSignalSync(
                store=store,
                workspace_dir=workspace_path,
            ),
        ).execute(
            promotion_threshold=promotion_threshold,
            limit=limit,
            write_report=True,
        )
    except ValueError as exc:
        return _err("GC_LOOP_ERROR", str(exc))

    classes = [
        {
            "failure_class": summary.failure_class.value,
            "item_count": summary.item_count,
            "recurrence_count": summary.recurrence_count,
            "warning_types": list(summary.warning_types),
            "source_kinds": list(summary.source_kinds),
        }
        for summary in result.class_summaries
    ]
    return _ok(
        generated_at=result.generated_at.isoformat(),
        total_items=result.total_items,
        total_recurrences=result.total_recurrences,
        promotion_threshold=result.promotion_threshold,
        promotion_candidate_classes=[
            failure_class.value for failure_class in result.promotion_candidate_classes
        ],
        classes=classes,
        skill_candidates=[
            {
                "failure_class": candidate.failure_class.value,
                "candidate_id": candidate.candidate_id,
                "status": candidate.status,
                "pending_path": candidate.pending_path,
                "reused_existing": candidate.reused_existing,
            }
            for candidate in result.registered_skill_candidates
        ],
        report_path=result.report_path,
    )


@tool(
    name="finalize_learning_candidate_promotion",
    description=(
        "Finalize a pending learning candidate into promoted or blocked state "
        "using explicit evaluation scores."
    ),
    parameters={
        "type": "object",
        "properties": {
            "candidate_id": {"type": "string"},
            "candidate_score": {"type": "number"},
            "passed_tasks": {"type": "integer"},
            "total_tasks": {"type": "integer"},
            "baseline_score": {"type": "number"},
            "delta_threshold": {"type": "number", "default": 0.03},
        },
        "required": ["candidate_id", "candidate_score", "passed_tasks", "total_tasks"],
    },
    safety_level="caution",
)
def finalize_learning_candidate_promotion(
    candidate_id: str,
    candidate_score: float,
    passed_tasks: int,
    total_tasks: int,
    baseline_score: float | None = None,
    delta_threshold: float = 0.03,
) -> str:
    """Finalize one learning-governance candidate using explicit eval scores."""

    _ = _get_learning_store(require_mutation=True)
    if _ is None:
        return _err("DISABLED", "Self-improve governance is not enabled.")

    workspace_path = _get_gc_workspace_path()
    if workspace_path is None:
        return _err("NO_WORKSPACE", "No active workspace is available for candidate promotion.")

    from ds_agent.application.learning.finalize_learning_candidate_promotion import (
        FinalizeLearningCandidatePromotionUseCase,
    )

    try:
        decision, candidate = FinalizeLearningCandidatePromotionUseCase(
            workspace_path,
            active_custom_dir=_get_active_custom_skills_dir(),
        ).execute(
            candidate_id=candidate_id,
            candidate_score=candidate_score,
            passed_tasks=passed_tasks,
            total_tasks=total_tasks,
            baseline_score=baseline_score,
            delta_threshold=delta_threshold,
        )
    except ValueError as exc:
        return _err("PROMOTION_ERROR", str(exc))

    return _ok(
        candidate_id=decision.candidate_id,
        status=decision.status,
        promoted=decision.promoted,
        candidate_score=decision.candidate_score,
        baseline_score=decision.baseline_score,
        delta_score=decision.delta_score,
        delta_threshold=decision.delta_threshold,
        passed_tasks=decision.passed_tasks,
        total_tasks=decision.total_tasks,
        summary=decision.summary,
        promoted_path=candidate.promoted_path,
        pending_path=candidate.pending_path,
    )


@tool(
    name="get_gc_report",
    description="Return the latest failure-taxonomy GC report.",
    parameters={
        "type": "object",
        "properties": {},
    },
    safety_level="safe",
)
def get_gc_report() -> str:
    """Return the latest failure-taxonomy GC report."""

    workspace_path = _get_gc_workspace_path()
    if workspace_path is None:
        return _err("NO_WORKSPACE", "No active workspace is available for GC reports.")

    from ds_agent.application.learning.failure_taxonomy_gc import latest_gc_report_path

    report_path = latest_gc_report_path(workspace_path)
    if report_path is None:
        return _err("NOT_FOUND", "No GC report has been generated yet.")

    try:
        content = report_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _err("READ_ERROR", str(exc))

    return _ok(path=str(report_path), content=content)


@tool(
    name="get_learning_governance_status",
    description="Return a read-only operational snapshot for learning governance.",
    parameters={
        "type": "object",
        "properties": {
            "history_limit": {"type": "integer", "default": 5},
        },
    },
    safety_level="safe",
)
def get_learning_governance_status(history_limit: int = 5) -> str:
    """Return a read-only operational snapshot for learning governance."""

    workspace_path = _get_gc_workspace_path()
    if workspace_path is None:
        return _err("NO_WORKSPACE", "No active workspace is available for learning governance.")

    store = _get_learning_store()
    if store is None:
        return _err("STORE_UNAVAILABLE", "Learning governance store is unavailable.")

    from ds_agent.runtime.learning_governance_scheduler import (
        build_learning_governance_status_payload,
    )
    from ds_agent.runtime.policy_store import JsonPolicyStore

    payload = build_learning_governance_status_payload(
        policy_store=JsonPolicyStore(workspace_dir=workspace_path),
        store=store,
        workspace_dir=workspace_path,
        history_limit=history_limit,
    )
    payload["review_enabled"] = _governance_mutation_enabled()
    return _ok(**payload)
