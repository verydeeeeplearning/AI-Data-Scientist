"""Structured standing-order management tool."""

from __future__ import annotations

import json
from typing import Any

from ds_agent.application.services.scheduler_service import get_scheduler_service
from ds_agent.domain.entities.standing_order import (
    CronTrigger,
    EscalationRule,
    EventTrigger,
    StandingOrder,
)
from ds_agent.tools.registry import tool


@tool(
    name="standing_order",
    description=(
        "Create, list, update, delete, inspect, and prepare structured standing "
        "orders for recurring autonomous work such as weekly KPI scans."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "update", "delete", "run_now", "view_history"],
                "description": "Standing-order action to perform.",
            },
            "order_id": {"type": "string", "description": "Standing-order identifier."},
            "name": {"type": "string", "description": "Human-readable order name."},
            "session_id": {"type": "string", "description": "Session to receive autonomous runs."},
            "prompt": {"type": "string", "description": "Prompt executed when the order fires."},
            "description": {"type": "string", "description": "Optional order description."},
            "trigger": {
                "type": "object",
                "description": (
                    "Trigger spec. Cron example: {'type': 'cron', 'cron': '0 9 * * MON', "
                    "'timezone': 'Asia/Seoul'}. Event example: {'type': 'event', "
                    "'event_type': 'file.created', 'filters': {'path_suffix': '.csv'}}."
                ),
            },
            "scope": {"type": "object", "description": "Optional structured scope metadata."},
            "approval_gate": {
                "type": "string",
                "enum": ["auto_report", "approval_required", "notify_only"],
                "description": "How results should be handled after execution.",
            },
            "budget_limit_usd": {
                "type": "number",
                "description": "Per-run budget cap for the standing order.",
            },
            "enabled": {"type": "boolean", "description": "Whether the order is active."},
            "escalation": {
                "type": "object",
                "description": (
                    "Optional escalation rule: {'metric_key': 'z_score', 'operator': '>=', "
                    "'threshold': 3, 'target': 'manager', 'channel': 'telegram'}."
                ),
            },
            "limit": {"type": "integer", "description": "History/list result limit."},
        },
        "required": ["action"],
    },
    timeout=30,
    prompt=(
        "Use standing_order to manage recurring autonomous work.\n"
        "- Prefer cron triggers for weekly or daily checks\n"
        "- Keep prompts concrete and budget-limited\n"
        "- Use view_history after scheduled runs to inspect outcomes"
    ),
)
def standing_order(
    action: str,
    order_id: str | None = None,
    name: str | None = None,
    session_id: str | None = None,
    prompt: str | None = None,
    description: str | None = None,
    trigger: dict[str, Any] | None = None,
    scope: dict[str, Any] | None = None,
    approval_gate: str | None = None,
    budget_limit_usd: float | None = None,
    enabled: bool | None = None,
    escalation: dict[str, Any] | None = None,
    limit: int = 20,
) -> str:
    try:
        service = get_scheduler_service()

        if action == "create":
            order = _build_order(
                name=name,
                session_id=session_id,
                prompt=prompt,
                description=description,
                trigger=trigger,
                scope=scope,
                approval_gate=approval_gate,
                budget_limit_usd=budget_limit_usd,
                enabled=True if enabled is None else enabled,
                escalation=escalation,
            )
            saved = service.register(order)
            return json.dumps({"order": _serialize_order(saved)}, ensure_ascii=False)

        if action == "list":
            orders = service.list_orders(enabled=enabled)
            return json.dumps(
                {
                    "orders": [_serialize_order(order) for order in orders[: max(limit, 1)]],
                    "count": len(orders),
                },
                ensure_ascii=False,
            )

        if action == "update":
            if not order_id:
                return json.dumps({"error": "order_id is required for update"})
            existing = service.get_order(order_id)
            if existing is None:
                return json.dumps({"error": f"Standing order not found: {order_id}"})
            if name is not None:
                existing.name = name
            if session_id is not None:
                existing.session_id = session_id
            if prompt is not None:
                existing.prompt = prompt
            if description is not None:
                existing.description = description
            if trigger is not None:
                existing.trigger = _parse_trigger(trigger)
            if scope is not None:
                existing.scope = dict(scope)
            if approval_gate is not None:
                existing.approval_gate = approval_gate  # type: ignore[assignment]
            if budget_limit_usd is not None:
                existing.budget_limit_usd = budget_limit_usd
            if enabled is not None:
                existing.enabled = enabled
            if escalation is not None:
                existing.escalation = _parse_escalation(escalation)
            saved = service.register(existing)
            return json.dumps({"order": _serialize_order(saved)}, ensure_ascii=False)

        if action == "delete":
            if not order_id:
                return json.dumps({"error": "order_id is required for delete"})
            deleted = service.unregister(order_id)
            return json.dumps({"deleted": deleted, "order_id": order_id}, ensure_ascii=False)

        if action == "run_now":
            if not order_id:
                return json.dumps({"error": "order_id is required for run_now"})
            existing = service.get_order(order_id)
            if existing is None:
                return json.dumps({"error": f"Standing order not found: {order_id}"})
            service.record_result(
                order_id,
                status="run_requested",
                summary="Manual run was requested via standing_order tool.",
            )
            return json.dumps(
                {
                    "order": _serialize_order(existing),
                    "dispatch": {
                        "session_id": existing.session_id,
                        "prompt": service.build_prompt(existing),
                        "budget_limit_usd": existing.budget_limit_usd,
                    },
                },
                ensure_ascii=False,
            )

        if action == "view_history":
            if not order_id:
                return json.dumps({"error": "order_id is required for view_history"})
            return json.dumps(
                {
                    "order_id": order_id,
                    "history": service.list_history(order_id, limit=max(limit, 1)),
                },
                ensure_ascii=False,
            )

        return json.dumps({"error": f"Unsupported action: {action}"})
    except Exception as exc:
        return json.dumps({"error": str(exc), "tool": "standing_order"})


def _build_order(
    *,
    name: str | None,
    session_id: str | None,
    prompt: str | None,
    description: str | None,
    trigger: dict[str, Any] | None,
    scope: dict[str, Any] | None,
    approval_gate: str | None,
    budget_limit_usd: float | None,
    enabled: bool,
    escalation: dict[str, Any] | None,
) -> StandingOrder:
    if not name:
        raise ValueError("name is required for create")
    if not session_id:
        raise ValueError("session_id is required for create")
    if not prompt:
        raise ValueError("prompt is required for create")
    if trigger is None:
        raise ValueError("trigger is required for create")

    return StandingOrder(
        session_id=session_id,
        name=name,
        prompt=prompt,
        description=description or "",
        trigger=_parse_trigger(trigger),
        scope=dict(scope or {}),
        approval_gate=("notify_only" if approval_gate is None else approval_gate),  # type: ignore[arg-type]
        budget_limit_usd=5.0 if budget_limit_usd is None else float(budget_limit_usd),
        enabled=enabled,
        escalation=_parse_escalation(escalation),
    )


def _parse_trigger(payload: dict[str, Any]) -> CronTrigger | EventTrigger:
    trigger_type = str(payload.get("type", "cron")).strip().lower()
    if trigger_type == "event":
        return EventTrigger(
            event_type=str(payload.get("event_type", "")).strip(),
            filters={
                str(key): str(value)
                for key, value in dict(payload.get("filters", {})).items()
            },
        )
    return CronTrigger(
        cron=str(payload.get("cron", "")).strip(),
        timezone=str(payload.get("timezone", "UTC")).strip(),
    )


def _parse_escalation(payload: dict[str, Any] | None) -> EscalationRule | None:
    if payload is None:
        return None
    return EscalationRule(
        metric_key=str(payload.get("metric_key", "")).strip(),
        operator=str(payload.get("operator", ">=")),  # type: ignore[arg-type]
        threshold=float(payload.get("threshold", 0.0)),
        target=str(payload.get("target", "")).strip(),
        channel=str(payload.get("channel", "runtime")).strip(),
    )


def _serialize_order(order: StandingOrder) -> dict[str, Any]:
    escalation = None
    if order.escalation is not None:
        escalation = {
            "metric_key": order.escalation.metric_key,
            "operator": order.escalation.operator,
            "threshold": order.escalation.threshold,
            "target": order.escalation.target,
            "channel": order.escalation.channel,
        }

    trigger: dict[str, object]
    if isinstance(order.trigger, CronTrigger):
        trigger = {
            "type": "cron",
            "cron": order.trigger.cron,
            "timezone": order.trigger.timezone,
        }
    else:
        trigger = {
            "type": "event",
            "event_type": order.trigger.event_type,
            "filters": order.trigger.filters,
        }

    return {
        "order_id": order.order_id,
        "session_id": order.session_id,
        "name": order.name,
        "description": order.description,
        "prompt": order.prompt,
        "trigger": trigger,
        "scope": order.scope,
        "approval_gate": order.approval_gate,
        "budget_limit_usd": order.budget_limit_usd,
        "enabled": order.enabled,
        "last_run_at": order.last_run_at,
        "next_run_at": order.next_run_at,
        "run_count": order.run_count,
        "failure_count": order.failure_count,
        "escalation": escalation,
    }
