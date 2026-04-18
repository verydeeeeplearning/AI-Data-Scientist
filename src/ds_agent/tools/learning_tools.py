"""Learning governance tools for knowledge quality management."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from ds_agent.tools.registry import tool

if TYPE_CHECKING:
    from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore

_learning_store: SqliteLearningStore | None = None


def _get_learning_store() -> SqliteLearningStore | None:
    global _learning_store
    if _learning_store is not None:
        return _learning_store
    if os.environ.get("DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1", "").lower() not in {
        "1", "true", "yes",
    }:
        return None
    from ds_agent.infrastructure.persistence.learning_store import SqliteLearningStore
    from ds_agent.tools.path_utils import get_active_workspace

    workspace = get_active_workspace()
    _learning_store = SqliteLearningStore.for_workspace(
        str(workspace) if workspace else None,
    )
    return _learning_store


def _ok(**payload: object) -> str:
    return json.dumps({"ok": True, **payload}, ensure_ascii=False)


def _err(code: str, msg: str) -> str:
    return json.dumps(
        {"ok": False, "error": {"code": code, "message": msg}},
        ensure_ascii=False,
    )


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
        {
            "item_id": s.item.item_id,
            "type": s.item.item_type.value,
            "status": s.item.status.value,
            "title": s.item.title,
            "priority_score": s.priority_score,
            "evidence_count": len(s.item.evidence),
            "conflict_count": len(s.item.conflict_refs),
            "scope": s.item.scope,
            "tags": s.item.tags,
        }
        for s in scored
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
    store = _get_learning_store()
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

    checklist = ReviewChecklist(
        evidence_sufficient=True,
        no_unresolved_conflicts=True,
        scope_appropriate=True,
        content_accurate=True,
    ) if dec == ReviewDecision.APPROVE else None

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

    return _ok(
        item_id=item.item_id,
        type=item.item_type.value,
        status=item.status.value,
        title=item.title,
        content=item.content[:500],
        signature=item.signature,
        scope=item.scope,
        review_count=item.review_count,
        evidence_count=len(item.evidence),
        conflict_count=len(item.conflict_refs),
        tags=item.tags,
        created_at=item.created_at.isoformat(),
    )


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
    store = _get_learning_store()
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
