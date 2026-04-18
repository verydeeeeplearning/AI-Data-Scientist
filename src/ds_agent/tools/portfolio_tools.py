"""Portfolio management tools for async task lifecycle."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ds_agent.tools.registry import tool

if TYPE_CHECKING:
    from ds_agent.infrastructure.persistence.portfolio_store import SqlitePortfolioStore

_portfolio_store: SqlitePortfolioStore | None = None


def _get_portfolio_store() -> SqlitePortfolioStore | None:
    global _portfolio_store
    if _portfolio_store is not None:
        return _portfolio_store
    if os.environ.get("DS_AGENT_PORTFOLIO_ENABLED", "").lower() not in {"1", "true", "yes"}:
        return None
    from ds_agent.infrastructure.persistence.portfolio_store import SqlitePortfolioStore
    from ds_agent.tools.path_utils import get_active_workspace

    workspace = get_active_workspace()
    _portfolio_store = SqlitePortfolioStore.for_workspace(
        str(workspace) if workspace else None,
    )
    return _portfolio_store


def _ok(**payload: object) -> str:
    return json.dumps({"ok": True, **payload}, ensure_ascii=False)


def _err(code: str, msg: str) -> str:
    return json.dumps({"ok": False, "error": {"code": code, "message": msg}}, ensure_ascii=False)


@tool(
    name="list_my_portfolio",
    description="List portfolio entries, optionally filtered by quadrant.",
    parameters={
        "type": "object",
        "properties": {
            "quadrant": {"type": "string", "default": "all"},
            "limit": {"type": "integer", "default": 20},
        },
    },
    safety_level="safe",
)
def list_my_portfolio(
    quadrant: str = "all",
    limit: int = 20,
) -> str:
    """List portfolio entries, optionally filtered by quadrant.

    Args:
        quadrant: Filter by quadrant (active/waiting/monitoring/playbook_candidate/all).
        limit: Maximum entries to return.
    """
    store = _get_portfolio_store()
    if store is None:
        return _err("DISABLED", "Portfolio manager is not enabled. Set DS_AGENT_PORTFOLIO_ENABLED=1.")

    q = quadrant if quadrant != "all" else None
    entries = store.list_entries(quadrant=q, limit=limit)
    items = [
        {
            "entry_id": e.entry_id,
            "task_contract_id": e.task_contract_id,
            "quadrant": e.quadrant,
            "priority": e.business_priority.value,
            "sla_deadline": e.sla_deadline.isoformat() if e.sla_deadline else None,
            "tags": e.tags,
        }
        for e in entries
    ]
    return _ok(entries=items, count=len(items))


@tool(
    name="pause_task",
    description="Pause an active portfolio task by moving it to the waiting quadrant.",
    parameters={
        "type": "object",
        "properties": {
            "entry_id": {"type": "string"},
            "wait_kind": {"type": "string", "default": "timer"},
            "wait_spec": {"type": "string", "default": "{}"},
            "reason": {"type": "string", "default": "paused by LLM"},
        },
        "required": ["entry_id"],
    },
    safety_level="caution",
)
def pause_task(
    entry_id: str,
    wait_kind: str = "timer",
    wait_spec: str = "{}",
    reason: str = "paused by LLM",
) -> str:
    """Pause an active portfolio task by moving it to the waiting quadrant.

    Args:
        entry_id: Portfolio entry ID to pause.
        wait_kind: Wait condition kind (timer/approval/data_freshness/external_resource).
        wait_spec: JSON string of wait condition spec (e.g. {"resume_at": "2026-04-17T09:00:00Z"}).
        reason: Reason for pausing.
    """
    store = _get_portfolio_store()
    if store is None:
        return _err("DISABLED", "Portfolio manager is not enabled.")

    entry = store.get_entry(entry_id)
    if entry is None:
        return _err("NOT_FOUND", f"Portfolio entry {entry_id} not found.")

    from ds_agent.domain.portfolio.portfolio_entry import PortfolioQuadrant, PortfolioTransition
    from ds_agent.domain.portfolio.wait_condition import WaitCondition, WaitConditionKind

    now = datetime.now(UTC)
    condition_id = f"WC-{now.strftime('%Y%m%d%H%M%S')}"
    try:
        spec = json.loads(wait_spec)
    except json.JSONDecodeError:
        return _err("INVALID_SPEC", "wait_spec must be valid JSON.")

    try:
        kind = WaitConditionKind(wait_kind)
    except ValueError:
        return _err("INVALID_KIND", f"Unknown wait_kind: {wait_kind}")

    try:
        updated = entry.transition_to(
            PortfolioQuadrant.WAITING,
            reason=reason,
            actor="llm",
            now=now,
            wait_condition_id=condition_id,
        )
    except ValueError as exc:
        return _err("TRANSITION_ERROR", str(exc))

    wc = WaitCondition.create(
        condition_id=condition_id,
        kind=kind,
        spec=spec,
        now=now,
    )
    store.save_wait_condition(wc)
    store.save_entry(updated)
    store.record_transition(
        entry_id,
        PortfolioTransition(
            from_quadrant=entry.quadrant,
            to_quadrant=PortfolioQuadrant.WAITING,
            reason=reason,
            actor="llm",
            at=now,
        ),
    )
    return _ok(entry_id=entry_id, new_quadrant="waiting", condition_id=condition_id)


@tool(
    name="resume_task",
    description="Resume a waiting portfolio task by moving it to the active quadrant.",
    parameters={
        "type": "object",
        "properties": {
            "entry_id": {"type": "string"},
            "run_id": {"type": "string"},
            "reason": {"type": "string", "default": "condition satisfied"},
        },
        "required": ["entry_id", "run_id"],
    },
    safety_level="caution",
)
def resume_task(
    entry_id: str,
    run_id: str,
    reason: str = "condition satisfied",
) -> str:
    """Resume a waiting portfolio task by moving it to the active quadrant.

    The slot manager enforces max_active_slots as a hard constraint.

    Args:
        entry_id: Portfolio entry ID to resume.
        run_id: New run ID for the active execution.
        reason: Reason for resuming.
    """
    store = _get_portfolio_store()
    if store is None:
        return _err("DISABLED", "Portfolio manager is not enabled.")

    entry = store.get_entry(entry_id)
    if entry is None:
        return _err("NOT_FOUND", f"Portfolio entry {entry_id} not found.")

    from ds_agent.application.portfolio.slot_manager import SlotManager
    from ds_agent.domain.portfolio.portfolio_entry import PortfolioQuadrant, PortfolioTransition

    slot_mgr = SlotManager(store)
    refusal = slot_mgr.acquire_or_refuse()
    if refusal is not None:
        return _err("SLOT_FULL", refusal)

    now = datetime.now(UTC)
    try:
        updated = entry.transition_to(
            PortfolioQuadrant.ACTIVE,
            reason=reason,
            actor="llm",
            now=now,
            run_id=run_id,
        )
    except ValueError as exc:
        return _err("TRANSITION_ERROR", str(exc))

    store.save_entry(updated)
    store.record_transition(
        entry_id,
        PortfolioTransition(
            from_quadrant=entry.quadrant,
            to_quadrant=PortfolioQuadrant.ACTIVE,
            reason=reason,
            actor="llm",
            at=now,
        ),
    )
    return _ok(entry_id=entry_id, new_quadrant="active", run_id=run_id)


@tool(
    name="set_sla",
    description="Set or update the SLA priority and deadline for a portfolio entry.",
    parameters={
        "type": "object",
        "properties": {
            "entry_id": {"type": "string"},
            "priority": {"type": "string"},
            "deadline": {"type": "string", "default": ""},
        },
        "required": ["entry_id", "priority"],
    },
    safety_level="caution",
)
def set_sla(
    entry_id: str,
    priority: str,
    deadline: str = "",
) -> str:
    """Set or update the SLA priority and deadline for a portfolio entry.

    Args:
        entry_id: Portfolio entry ID.
        priority: Business priority (P0/P1/P2/P3).
        deadline: Optional ISO-8601 SLA deadline.
    """
    store = _get_portfolio_store()
    if store is None:
        return _err("DISABLED", "Portfolio manager is not enabled.")

    entry = store.get_entry(entry_id)
    if entry is None:
        return _err("NOT_FOUND", f"Portfolio entry {entry_id} not found.")

    from ds_agent.domain.portfolio.portfolio_entry import BusinessPriority

    try:
        bp = BusinessPriority(priority)
    except ValueError:
        return _err("INVALID_PRIORITY", f"Unknown priority: {priority}")

    sla_deadline = datetime.fromisoformat(deadline) if deadline else None
    updated = entry.model_copy(
        update={
            "business_priority": bp,
            "sla_deadline": sla_deadline,
            "updated_at": datetime.now(UTC),
        },
    )
    store.save_entry(updated)
    return _ok(
        entry_id=entry_id,
        priority=bp.value,
        sla_deadline=sla_deadline.isoformat() if sla_deadline else None,
    )


@tool(
    name="request_monitoring",
    description="Move an active task to the monitoring quadrant for metric tracking.",
    parameters={
        "type": "object",
        "properties": {
            "entry_id": {"type": "string"},
            "metric_name": {"type": "string"},
            "reason": {"type": "string", "default": "post-execution monitoring"},
        },
        "required": ["entry_id", "metric_name"],
    },
    safety_level="caution",
)
def request_monitoring(
    entry_id: str,
    metric_name: str,
    reason: str = "post-execution monitoring",
) -> str:
    """Move an active task to the monitoring quadrant for metric tracking.

    Args:
        entry_id: Portfolio entry ID.
        metric_name: Name of the metric to monitor.
        reason: Reason for monitoring.
    """
    store = _get_portfolio_store()
    if store is None:
        return _err("DISABLED", "Portfolio manager is not enabled.")

    entry = store.get_entry(entry_id)
    if entry is None:
        return _err("NOT_FOUND", f"Portfolio entry {entry_id} not found.")

    from ds_agent.domain.portfolio.portfolio_entry import PortfolioQuadrant, PortfolioTransition

    now = datetime.now(UTC)
    monitoring_id = f"MON-{now.strftime('%Y%m%d%H%M%S')}"

    try:
        updated = entry.transition_to(
            PortfolioQuadrant.MONITORING,
            reason=reason,
            actor="llm",
            now=now,
            monitoring_metric_ref=monitoring_id,
        )
    except ValueError as exc:
        return _err("TRANSITION_ERROR", str(exc))

    # MonitoringState persistence would go through a dedicated store method.
    # For now, store the entry transition.
    store.save_entry(updated)
    store.record_transition(
        entry_id,
        PortfolioTransition(
            from_quadrant=entry.quadrant,
            to_quadrant=PortfolioQuadrant.MONITORING,
            reason=reason,
            actor="llm",
            at=now,
        ),
    )
    return _ok(entry_id=entry_id, new_quadrant="monitoring", monitoring_id=monitoring_id)
