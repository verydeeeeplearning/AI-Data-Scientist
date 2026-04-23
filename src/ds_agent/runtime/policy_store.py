"""File-backed store for recurring goals, standing orders, and matrix overrides."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ds_agent.domain.entities.risk_tier_matrix import RiskTierMatrixSnapshot
from ds_agent.domain.entities.standing_order import (
    CronTrigger,
    EscalationRule,
    EventTrigger,
    StandingOrder,
)
from ds_agent.domain.value_objects.authority_mode import AuthorityMode
from ds_agent.runtime.action_matrix import ActionMatrix, Verdict
from ds_agent.runtime.transcript_store import get_runtime_storage_root


@dataclass(slots=True)
class RecurringGoal:
    """One recurring autonomous goal rule."""

    goal_id: str
    session_id: str
    prompt: str
    interval_seconds: float
    enabled: bool = True
    last_triggered_at: float | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class JsonPolicyStore:
    """Persist recurring goals, standing orders, and action-matrix overrides."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._file = root / "policy.json"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        risk_dir = self._file.parent / "policy"
        risk_dir.mkdir(parents=True, exist_ok=True)
        self._risk_tier_matrix_file = risk_dir / "risk_tier_matrix.json"
        self._risk_tier_history_file = risk_dir / "risk_tier_matrix_history.jsonl"
        self._lock = threading.Lock()
        self._risk_tier_lock = threading.Lock()

    def list_recurring_goals(self) -> list[RecurringGoal]:
        """Return all recurring goals."""
        data = self._load()
        items = data.get("recurring_goals", [])
        goals = [self._deserialize_goal(item) for item in items if isinstance(item, dict)]
        goals.sort(key=lambda item: item.updated_at, reverse=True)
        return goals

    def upsert_recurring_goal(
        self,
        *,
        session_id: str,
        prompt: str,
        interval_seconds: float,
        enabled: bool = True,
        goal_id: str | None = None,
    ) -> RecurringGoal:
        """Create or update one recurring goal."""
        with self._lock:
            data = self._load_unlocked()
            goals = [
                self._deserialize_goal(item)
                for item in data.get("recurring_goals", [])
                if isinstance(item, dict)
            ]
            now = time.time()
            target = next((goal for goal in goals if goal.goal_id == goal_id), None)
            if target is None:
                target = RecurringGoal(
                    goal_id=goal_id or uuid.uuid4().hex[:12],
                    session_id=session_id,
                    prompt=prompt.strip(),
                    interval_seconds=max(float(interval_seconds), 1.0),
                    enabled=enabled,
                    created_at=now,
                    updated_at=now,
                )
                goals.append(target)
            else:
                target.session_id = session_id
                target.prompt = prompt.strip()
                target.interval_seconds = max(float(interval_seconds), 1.0)
                target.enabled = enabled
                target.updated_at = now
            data["recurring_goals"] = [self._serialize_goal(goal) for goal in goals]
            self._save_unlocked(data)
            return target

    def get_due_recurring_goals(self, now: float | None = None) -> list[RecurringGoal]:
        """Return enabled recurring goals that are due to trigger."""
        now_ts = time.time() if now is None else now
        due: list[RecurringGoal] = []
        for goal in self.list_recurring_goals():
            if not goal.enabled:
                continue
            if goal.last_triggered_at is None:
                due.append(goal)
                continue
            if (now_ts - goal.last_triggered_at) >= goal.interval_seconds:
                due.append(goal)
        return due

    def mark_recurring_goal_triggered(
        self,
        goal_id: str,
        triggered_at: float | None = None,
    ) -> None:
        """Persist the latest trigger time for one recurring goal."""
        with self._lock:
            data = self._load_unlocked()
            goals = data.get("recurring_goals", [])
            if not isinstance(goals, list):
                goals = []
            now = time.time() if triggered_at is None else triggered_at
            for item in goals:
                if not isinstance(item, dict) or item.get("goal_id") != goal_id:
                    continue
                item["last_triggered_at"] = now
                item["updated_at"] = now
            data["recurring_goals"] = goals
            self._save_unlocked(data)

    def get_standing_orders(self) -> list[str]:
        """Return standing order strings."""
        data = self._load()
        return [str(item) for item in data.get("standing_orders", []) if isinstance(item, str)]

    def set_standing_orders(self, orders: list[str]) -> None:
        """Persist standing order strings."""
        with self._lock:
            data = self._load_unlocked()
            data["standing_orders"] = [str(item).strip() for item in orders if str(item).strip()]
            self._save_unlocked(data)

    def get_action_matrix_overrides(self) -> dict[str, dict[str, str]]:
        """Return persisted authority x action-class matrix overrides."""

        data = self._load()
        return _normalize_action_matrix_overrides(
            data.get("action_matrix_overrides"),
            strict=False,
        )

    def set_action_matrix_overrides(
        self,
        overrides: dict[str, dict[str, str]] | dict[str, dict[AuthorityMode, Verdict]],
    ) -> dict[str, dict[str, str]]:
        """Replace persisted action-matrix overrides."""

        normalized = _normalize_action_matrix_overrides(overrides, strict=True)
        with self._lock:
            data = self._load_unlocked()
            data["action_matrix_overrides"] = normalized
            self._save_unlocked(data)
        return normalized

    def build_action_matrix(self) -> ActionMatrix:
        """Return the effective action matrix with persisted overrides applied."""

        matrix = ActionMatrix.default().with_overrides(self.get_action_matrix_overrides())
        return matrix.with_risk_tier_overlay(self.load_risk_tier_matrix())

    def list_standing_order_records(self, enabled: bool | None = None) -> list[StandingOrder]:
        """Return structured standing-order records."""
        data = self._load()
        orders = [
            self._deserialize_standing_order(item)
            for item in data.get("standing_order_records", [])
            if isinstance(item, dict)
        ]
        if enabled is not None:
            orders = [order for order in orders if order.enabled is enabled]
        orders.sort(key=lambda item: item.updated_at, reverse=True)
        return orders

    def get_standing_order(self, order_id: str) -> StandingOrder | None:
        """Return one standing order by id."""
        data = self._load()
        for item in data.get("standing_order_records", []):
            if isinstance(item, dict) and item.get("order_id") == order_id:
                return self._deserialize_standing_order(item)
        return None

    def upsert_standing_order(self, order: StandingOrder) -> StandingOrder:
        """Create or replace one structured standing order."""
        with self._lock:
            data = self._load_unlocked()
            raw_orders = data.get("standing_order_records", [])
            if not isinstance(raw_orders, list):
                raw_orders = []

            serialized = self._serialize_standing_order(order)
            replaced = False
            updated_orders: list[dict[str, object]] = []
            for item in raw_orders:
                if not isinstance(item, dict):
                    continue
                if item.get("order_id") == order.order_id:
                    updated_orders.append(serialized)
                    replaced = True
                else:
                    updated_orders.append(item)
            if not replaced:
                updated_orders.append(serialized)

            data["standing_order_records"] = updated_orders
            self._save_unlocked(data)
            return order

    def delete_standing_order(self, order_id: str) -> bool:
        """Delete one structured standing order and its history."""
        with self._lock:
            data = self._load_unlocked()
            raw_orders = data.get("standing_order_records", [])
            if not isinstance(raw_orders, list):
                raw_orders = []
            kept = [
                item
                for item in raw_orders
                if not isinstance(item, dict) or item.get("order_id") != order_id
            ]
            if len(kept) == len(raw_orders):
                return False
            data["standing_order_records"] = kept
            history = data.get("standing_order_history", {})
            if isinstance(history, dict):
                history.pop(order_id, None)
                data["standing_order_history"] = history
            self._save_unlocked(data)
            return True

    def mark_standing_order_triggered(
        self,
        order_id: str,
        *,
        triggered_at: float | None = None,
        next_run_at: float | None = None,
        run_id: str | None = None,
    ) -> StandingOrder | None:
        """Advance one standing order after dispatch."""
        with self._lock:
            data = self._load_unlocked()
            raw_orders = data.get("standing_order_records", [])
            if not isinstance(raw_orders, list):
                raw_orders = []

            now = time.time() if triggered_at is None else float(triggered_at)
            target: StandingOrder | None = None
            updated_orders: list[dict[str, object]] = []
            for item in raw_orders:
                if not isinstance(item, dict):
                    continue
                if item.get("order_id") != order_id:
                    updated_orders.append(item)
                    continue

                order = self._deserialize_standing_order(item)
                order.last_run_at = now
                order.next_run_at = next_run_at
                order.run_count += 1
                order.updated_at = now
                target = order
                updated_orders.append(self._serialize_standing_order(order))

            if target is None:
                return None

            data["standing_order_records"] = updated_orders
            self._append_standing_order_history_unlocked(
                data,
                order_id,
                {
                    "status": "dispatched",
                    "summary": "Standing order dispatched.",
                    "run_id": run_id,
                    "recorded_at": now,
                },
            )
            self._save_unlocked(data)
            return target

    def record_standing_order_result(
        self,
        order_id: str,
        *,
        status: str,
        summary: str,
        run_id: str | None = None,
        metadata: dict[str, object] | None = None,
        recorded_at: float | None = None,
    ) -> dict[str, object] | None:
        """Append one standing-order execution result entry."""
        with self._lock:
            data = self._load_unlocked()
            raw_orders = data.get("standing_order_records", [])
            if not isinstance(raw_orders, list):
                raw_orders = []

            target_index = None
            target_order: StandingOrder | None = None
            for index, item in enumerate(raw_orders):
                if not isinstance(item, dict) or item.get("order_id") != order_id:
                    continue
                target_index = index
                target_order = self._deserialize_standing_order(item)
                break

            if target_order is None or target_index is None:
                return None

            target_order.updated_at = time.time() if recorded_at is None else float(recorded_at)
            if status in {"failed", "error"}:
                target_order.failure_count += 1
            raw_orders[target_index] = self._serialize_standing_order(target_order)
            data["standing_order_records"] = raw_orders

            entry = {
                "status": status,
                "summary": summary.strip(),
                "run_id": run_id,
                "metadata": dict(metadata or {}),
                "recorded_at": target_order.updated_at,
            }
            self._append_standing_order_history_unlocked(data, order_id, entry)
            self._save_unlocked(data)
            return entry

    def list_standing_order_history(
        self,
        order_id: str,
        *,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        """Return recent standing-order history entries."""
        data = self._load()
        history = data.get("standing_order_history", {})
        if not isinstance(history, dict):
            return []
        items = history.get(order_id, [])
        if not isinstance(items, list):
            return []
        normalized = [dict(item) for item in items if isinstance(item, dict)]
        normalized.sort(key=lambda item: float(item.get("recorded_at", 0.0)), reverse=True)
        return normalized[:limit]

    # -- Risk-tier matrix persistence ---------------------------------------

    def save_risk_tier_matrix(
        self,
        matrix: dict[str, dict[str, str]],
        *,
        saved_by: str | None = None,
        saved_at: float | None = None,
    ) -> RiskTierMatrixSnapshot:
        """Persist the current risk-tier matrix and append one history entry.

        The shape is ``{action_name: {authority_level: tier_label}}``. The
        method returns the snapshot that was appended to the history log so
        callers can echo it back to the operator UI.
        """
        normalized = _normalize_risk_tier_matrix(matrix)
        timestamp = float(saved_at) if saved_at is not None else time.time()
        actor = saved_by if isinstance(saved_by, str) and saved_by.strip() else None
        if actor is not None:
            actor = actor.strip()

        with self._risk_tier_lock:
            self._risk_tier_matrix_file.write_text(
                json.dumps(
                    {"savedAt": timestamp, "matrix": normalized, "savedBy": actor},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            entry = {"savedAt": timestamp, "matrix": normalized, "savedBy": actor}
            with self._risk_tier_history_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return RiskTierMatrixSnapshot(
            saved_at=timestamp,
            matrix=normalized,
            saved_by=actor,
        )

    def load_risk_tier_matrix(self) -> dict[str, dict[str, str]]:
        """Return the persisted risk-tier matrix or ``{}`` if none was saved."""
        with self._risk_tier_lock:
            if not self._risk_tier_matrix_file.exists():
                return {}
            try:
                payload = json.loads(
                    self._risk_tier_matrix_file.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                return {}
        if not isinstance(payload, dict):
            return {}
        matrix = payload.get("matrix")
        if not isinstance(matrix, dict):
            return {}
        return _normalize_risk_tier_matrix(matrix, strict=False)

    def risk_tier_matrix_history(self, limit: int = 50) -> list[RiskTierMatrixSnapshot]:
        """Return persisted risk-tier matrix snapshots, newest first.

        ``limit`` caps how many snapshots are returned. The on-disk log is
        an append-only JSONL file, so order is preserved by file position.
        """
        capped = max(int(limit), 0)
        with self._risk_tier_lock:
            if not self._risk_tier_history_file.exists():
                return []
            try:
                lines = self._risk_tier_history_file.read_text(
                    encoding="utf-8"
                ).splitlines()
            except OSError:
                return []

        snapshots: list[RiskTierMatrixSnapshot] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            matrix_raw = payload.get("matrix")
            matrix = (
                _normalize_risk_tier_matrix(matrix_raw, strict=False)
                if isinstance(matrix_raw, dict)
                else {}
            )
            try:
                saved_at = float(payload.get("savedAt", 0.0))
            except (TypeError, ValueError):
                saved_at = 0.0
            saved_by = payload.get("savedBy")
            saved_by_str = (
                saved_by
                if isinstance(saved_by, str) and saved_by.strip()
                else None
            )
            snapshots.append(
                RiskTierMatrixSnapshot(
                    saved_at=saved_at,
                    matrix=matrix,
                    saved_by=saved_by_str,
                )
            )

        snapshots.sort(key=lambda item: item.saved_at, reverse=True)
        if capped == 0:
            return []
        return snapshots[:capped]

    def _load(self) -> dict[str, object]:
        with self._lock:
            return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, object]:
        if not self._file.exists():
            return self._empty_payload()
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return self._empty_payload()
        if not isinstance(data, dict):
            return self._empty_payload()
        data.setdefault("recurring_goals", [])
        data.setdefault("standing_orders", [])
        data.setdefault("action_matrix_overrides", {})
        data.setdefault("standing_order_records", [])
        data.setdefault("standing_order_history", {})
        return data

    def _save_unlocked(self, data: dict[str, object]) -> None:
        payload = {
            "recurring_goals": data.get("recurring_goals", []),
            "standing_orders": data.get("standing_orders", []),
            "action_matrix_overrides": data.get("action_matrix_overrides", {}),
            "standing_order_records": data.get("standing_order_records", []),
            "standing_order_history": data.get("standing_order_history", {}),
        }
        self._file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _empty_payload() -> dict[str, object]:
        return {
            "recurring_goals": [],
            "standing_orders": [],
            "action_matrix_overrides": {},
            "standing_order_records": [],
            "standing_order_history": {},
        }

    @staticmethod
    def _serialize_goal(goal: RecurringGoal) -> dict[str, object]:
        return {
            "goal_id": goal.goal_id,
            "session_id": goal.session_id,
            "prompt": goal.prompt,
            "interval_seconds": goal.interval_seconds,
            "enabled": goal.enabled,
            "last_triggered_at": goal.last_triggered_at,
            "created_at": goal.created_at,
            "updated_at": goal.updated_at,
        }

    @staticmethod
    def _deserialize_goal(data: dict[str, object]) -> RecurringGoal:
        return RecurringGoal(
            goal_id=str(data.get("goal_id", "")),
            session_id=str(data.get("session_id", "")),
            prompt=str(data.get("prompt", "")),
            interval_seconds=float(data.get("interval_seconds", 300.0)),
            enabled=bool(data.get("enabled", True)),
            last_triggered_at=(
                float(data["last_triggered_at"])
                if data.get("last_triggered_at") is not None
                else None
            ),
            created_at=float(data.get("created_at", 0.0)),
            updated_at=float(data.get("updated_at", 0.0)),
        )

    @staticmethod
    def _serialize_standing_order(order: StandingOrder) -> dict[str, object]:
        escalation = None
        if order.escalation is not None:
            escalation = {
                "metric_key": order.escalation.metric_key,
                "operator": order.escalation.operator,
                "threshold": order.escalation.threshold,
                "target": order.escalation.target,
                "channel": order.escalation.channel,
            }

        if isinstance(order.trigger, CronTrigger):
            trigger: dict[str, object] = {
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
            "escalation": escalation,
            "budget_limit_usd": order.budget_limit_usd,
            "enabled": order.enabled,
            "last_run_at": order.last_run_at,
            "next_run_at": order.next_run_at,
            "run_count": order.run_count,
            "failure_count": order.failure_count,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }

    @staticmethod
    def _deserialize_standing_order(data: dict[str, object]) -> StandingOrder:
        raw_trigger = data.get("trigger", {})
        if not isinstance(raw_trigger, dict):
            raise ValueError("Standing order trigger must be a dict")
        trigger_type = str(raw_trigger.get("type", "cron"))
        if trigger_type == "event":
            trigger = EventTrigger(
                event_type=str(raw_trigger.get("event_type", "")),
                filters={
                    str(key): str(value)
                    for key, value in dict(raw_trigger.get("filters", {})).items()
                },
            )
        else:
            trigger = CronTrigger(
                cron=str(raw_trigger.get("cron", "* * * * *")),
                timezone=str(raw_trigger.get("timezone", "UTC")),
            )

        escalation = None
        raw_escalation = data.get("escalation")
        if isinstance(raw_escalation, dict):
            escalation = EscalationRule(
                metric_key=str(raw_escalation.get("metric_key", "")),
                operator=str(raw_escalation.get("operator", ">=")),  # type: ignore[arg-type]
                threshold=float(raw_escalation.get("threshold", 0.0)),
                target=str(raw_escalation.get("target", "")),
                channel=str(raw_escalation.get("channel", "runtime")),
            )

        scope = data.get("scope", {})
        return StandingOrder(
            order_id=str(data.get("order_id", "")),
            session_id=str(data.get("session_id", "")),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            prompt=str(data.get("prompt", "")),
            trigger=trigger,
            scope=dict(scope) if isinstance(scope, dict) else {},
            approval_gate=str(data.get("approval_gate", "notify_only")),  # type: ignore[arg-type]
            escalation=escalation,
            budget_limit_usd=float(data.get("budget_limit_usd", 5.0)),
            enabled=bool(data.get("enabled", True)),
            last_run_at=(
                float(data["last_run_at"]) if data.get("last_run_at") is not None else None
            ),
            next_run_at=(
                float(data["next_run_at"]) if data.get("next_run_at") is not None else None
            ),
            run_count=int(data.get("run_count", 0)),
            failure_count=int(data.get("failure_count", 0)),
            created_at=float(data.get("created_at", 0.0)),
            updated_at=float(data.get("updated_at", 0.0)),
        )

    @staticmethod
    def _append_standing_order_history_unlocked(
        data: dict[str, object],
        order_id: str,
        entry: dict[str, object],
    ) -> None:
        history = data.get("standing_order_history", {})
        if not isinstance(history, dict):
            history = {}
        items = history.get(order_id, [])
        if not isinstance(items, list):
            items = []
        items.append(entry)
        history[order_id] = items[-50:]
        data["standing_order_history"] = history


_VALID_ACTION_CLASS_NAMES = frozenset(ActionMatrix.default().matrix.keys())
_VALID_RISK_TIER_AUTHORITIES = frozenset(mode.value for mode in AuthorityMode)


def _normalize_risk_tier_matrix(
    raw: Any,
    *,
    strict: bool = True,
) -> dict[str, dict[str, str]]:
    """Validate and coerce a `{action: {authority: tier}}` matrix.

    The matrix shape is intentionally permissive about action and tier
    labels (operator-defined) but requires authority levels to match
    ``AuthorityMode`` so the matrix can be merged with the runtime
    autonomy axis without ambiguous keys.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        if strict:
            raise ValueError("risk_tier_matrix must be an object")
        return {}

    normalized: dict[str, dict[str, str]] = {}
    for action_name, authority_map in raw.items():
        action_key = str(action_name).strip()
        if not action_key:
            if strict:
                raise ValueError("risk_tier_matrix keys must be non-empty strings")
            continue
        if not isinstance(authority_map, dict):
            if strict:
                raise ValueError(
                    f"risk_tier_matrix entry for {action_key} must be an object"
                )
            continue

        per_action: dict[str, str] = {}
        for authority_name, tier_label in authority_map.items():
            authority_key = str(authority_name).strip().lower()
            if authority_key not in _VALID_RISK_TIER_AUTHORITIES:
                if strict:
                    raise ValueError(
                        f"Invalid authority level for {action_key}: {authority_name}"
                    )
                continue
            tier_str = str(tier_label).strip()
            if not tier_str:
                if strict:
                    raise ValueError(
                        f"risk_tier_matrix tier for {action_key}.{authority_key} "
                        "must be non-empty"
                    )
                continue
            per_action[authority_key] = tier_str

        if per_action:
            normalized[action_key] = per_action

    return normalized


def _normalize_action_matrix_overrides(
    raw: Any,
    *,
    strict: bool,
) -> dict[str, dict[str, str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        if strict:
            raise ValueError("action_matrix_overrides must be an object")
        return {}

    normalized: dict[str, dict[str, str]] = {}
    for action_name, verdict_map in raw.items():
        action_key = str(action_name).strip()
        if not action_key:
            if strict:
                raise ValueError("action_matrix_overrides keys must be non-empty strings")
            continue
        if action_key not in _VALID_ACTION_CLASS_NAMES:
            if strict:
                raise ValueError(f"Unknown action class override: {action_key}")
            continue
        if not isinstance(verdict_map, dict):
            if strict:
                raise ValueError(f"Override entry for {action_key} must be an object")
            continue

        per_action: dict[str, str] = {}
        for authority_name, verdict_name in verdict_map.items():
            try:
                authority = AuthorityMode.coerce(authority_name)
                verdict = Verdict(str(verdict_name))
            except ValueError:
                if strict:
                    raise ValueError(
                        f"Invalid action-matrix override for {action_key}: "
                        f"{authority_name}={verdict_name}"
                    ) from None
                continue
            per_action[authority.value] = verdict.value

        if per_action:
            normalized[action_key] = per_action

    return normalized
