"""Per-chat alert lifecycle state for Telegram operators.

Tracks mutable alert-handling state that is separate from notification
preferences: acknowledgements, temporary mute windows, suppressed alerts
waiting for digest delivery, and the last digest send timestamp.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.runtime.transcript_store import get_runtime_storage_root

_MAX_ACKED_EVENT_IDS = 200
_MAX_SUPPRESSED_ALERTS = 200


@dataclass
class SuppressedAlertRecord:
    """One alert that was intentionally withheld from live delivery."""

    event_id: str
    reason: str
    created_at: float = field(default_factory=time.time)


@dataclass
class OperatorAlertState:
    """Mutable alert lifecycle state for one chat."""

    chat_id: str
    acknowledged_event_ids: list[str] = field(default_factory=list)
    muted_until: float = 0.0
    last_digest_sent_at: float = 0.0
    suppressed_alerts: list[SuppressedAlertRecord] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)


class JsonOperatorAlertStateStore:
    """Persistent JSON-backed store for per-chat alert lifecycle state."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._path = root / "operator-alert-state.json"
        self._lock = threading.Lock()
        self._cache: dict[str, OperatorAlertState] = {}
        self._loaded = False

    def get(self, chat_id: str) -> OperatorAlertState:
        self._ensure_loaded()
        with self._lock:
            state = self._cache.get(chat_id)
            if state is None:
                state = OperatorAlertState(chat_id=chat_id)
                self._cache[chat_id] = state
                self._persist()
            return state

    def update(self, state: OperatorAlertState) -> OperatorAlertState:
        state.updated_at = time.time()
        with self._lock:
            state.acknowledged_event_ids = state.acknowledged_event_ids[-_MAX_ACKED_EVENT_IDS:]
            state.suppressed_alerts = state.suppressed_alerts[-_MAX_SUPPRESSED_ALERTS:]
            self._cache[state.chat_id] = state
            self._persist()
        return state

    def acknowledge(self, chat_id: str, event_id: str) -> OperatorAlertState:
        state = self.get(chat_id)
        if event_id not in state.acknowledged_event_ids:
            state.acknowledged_event_ids.append(event_id)
        state.suppressed_alerts = [
            item for item in state.suppressed_alerts if item.event_id != event_id
        ]
        return self.update(state)

    def is_acknowledged(self, chat_id: str, event_id: str) -> bool:
        return event_id in self.get(chat_id).acknowledged_event_ids

    def set_muted(self, chat_id: str, duration_seconds: float) -> OperatorAlertState:
        state = self.get(chat_id)
        state.muted_until = time.time() + max(0.0, duration_seconds)
        return self.update(state)

    def unmute(self, chat_id: str) -> OperatorAlertState:
        state = self.get(chat_id)
        state.muted_until = 0.0
        return self.update(state)

    def is_muted(self, chat_id: str) -> bool:
        return self.get(chat_id).muted_until > time.time()

    def record_suppressed(self, chat_id: str, event_id: str, reason: str) -> OperatorAlertState:
        state = self.get(chat_id)
        if all(item.event_id != event_id for item in state.suppressed_alerts):
            state.suppressed_alerts.append(
                SuppressedAlertRecord(
                    event_id=event_id,
                    reason=reason,
                )
            )
        return self.update(state)

    def suppression_reason(self, chat_id: str, event_id: str) -> str | None:
        state = self.get(chat_id)
        for item in reversed(state.suppressed_alerts):
            if item.event_id == event_id:
                return item.reason
        return None

    def list_suppressed(
        self,
        chat_id: str,
        *,
        limit: int = 50,
    ) -> list[SuppressedAlertRecord]:
        state = self.get(chat_id)
        if limit <= 0:
            return []
        return list(state.suppressed_alerts[-limit:])

    def should_send_digest(
        self,
        chat_id: str,
        interval_seconds: float,
        *,
        cadence: str = "interval",
        timezone: str = "UTC",
        now: float | None = None,
    ) -> bool:
        state = self.get(chat_id)
        if not state.suppressed_alerts:
            return False
        current_time = time.time() if now is None else float(now)
        if cadence != "interval":
            slot_start = _digest_slot_start(current_time, cadence=cadence, timezone=timezone)
            if slot_start is None:
                return False
            if state.last_digest_sent_at >= slot_start:
                return False
            return any(item.created_at < slot_start for item in state.suppressed_alerts)
        anchor = state.last_digest_sent_at
        if anchor <= 0.0:
            anchor = state.suppressed_alerts[0].created_at
        return (current_time - anchor) >= max(60.0, interval_seconds)

    def mark_digest_sent(
        self,
        chat_id: str,
        *,
        delivered_event_ids: list[str] | None = None,
    ) -> OperatorAlertState:
        state = self.get(chat_id)
        state.last_digest_sent_at = time.time()
        if delivered_event_ids is None:
            state.suppressed_alerts.clear()
        else:
            delivered = set(delivered_event_ids)
            state.suppressed_alerts = [
                item for item in state.suppressed_alerts if item.event_id not in delivered
            ]
        return self.update(state)

    def list_all(self) -> list[OperatorAlertState]:
        self._ensure_loaded()
        with self._lock:
            return list(self._cache.values())

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            if self._path.exists():
                try:
                    data = json.loads(self._path.read_text(encoding="utf-8"))
                    for chat_id, raw in data.items():
                        if not isinstance(raw, dict):
                            continue
                        raw.setdefault("chat_id", chat_id)
                        suppressed_raw = raw.pop("suppressed_alerts", [])
                        state = OperatorAlertState(**raw)
                        if isinstance(suppressed_raw, list):
                            state.suppressed_alerts = [
                                SuppressedAlertRecord(
                                    event_id=str(item.get("event_id", "")),
                                    reason=str(item.get("reason", "unknown")),
                                    created_at=float(item.get("created_at", 0.0)),
                                )
                                for item in suppressed_raw
                                if isinstance(item, dict)
                            ]
                        self._cache[chat_id] = state
                except Exception:
                    pass
            self._loaded = True

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serializable: dict[str, dict[str, object]] = {}
        for chat_id, state in self._cache.items():
            payload = asdict(state)
            serializable[chat_id] = payload
        self._path.write_text(
            json.dumps(serializable, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _digest_slot_start(
    now: float,
    *,
    cadence: str,
    timezone: str,
) -> float | None:
    """Return the current slot start timestamp for one named digest cadence."""
    current = _localized_datetime(now, timezone)
    if cadence == "hourly":
        return current.replace(minute=0, second=0, microsecond=0).timestamp()
    if cadence == "morning":
        slot = current.replace(hour=9, minute=0, second=0, microsecond=0)
        if current < slot:
            return None
        return slot.timestamp()
    if cadence == "end_of_day":
        slot = current.replace(hour=18, minute=0, second=0, microsecond=0)
        if current < slot:
            return None
        return slot.timestamp()
    return None


def _localized_datetime(now: float, timezone: str) -> datetime:
    try:
        from zoneinfo import ZoneInfo

        tzinfo = ZoneInfo(timezone)
    except Exception:
        tzinfo = UTC
    return datetime.fromtimestamp(now, tz=tzinfo)
