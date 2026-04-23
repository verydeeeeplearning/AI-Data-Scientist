"""JSON-backed persistence for quiet-hours deferred notifications.

Stores deferred notifications in one file per operator so quiet-hours
suppression can survive process restarts without sharing a single hot
write target across every operator.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ds_agent.application.use_cases.build_digest_usecase import DigestEntrySourcePort
from ds_agent.application.use_cases.send_notification_usecase import (
    DeferredNotificationStorePort,
)
from ds_agent.domain.notification import (
    DigestEntry,
    InlineButton,
    Notification,
    NotificationCategory,
)
from ds_agent.runtime.transcript_store import (
    _SESSION_ID_SAFE_CHARS,
    get_runtime_storage_root,
)


@dataclass(frozen=True, slots=True)
class DeferredNotificationRecord:
    """One notification withheld because quiet hours were active."""

    operator_id: str
    notification: Notification
    deferred_at: datetime

    def to_digest_entry(self) -> DigestEntry:
        return DigestEntry(
            category=self.notification.category,
            title=self.notification.title,
            occurred_at=self.deferred_at,
            workspace_id=self.notification.workspace_id,
            run_id=self.notification.run_id,
            deep_link=self.notification.deep_link,
        )


class JsonDeferredNotificationStore(DeferredNotificationStorePort, DigestEntrySourcePort):
    """Persist quiet-hours-suppressed notifications as per-operator JSON files."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._dir = root / "deferred-notifications"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def park(
        self,
        *,
        operator_id: str,
        notification: Notification,
        deferred_at: datetime,
    ) -> None:
        """Append one deferred notification for an operator."""
        if deferred_at.tzinfo is None:
            raise ValueError("deferred_at must be timezone-aware")

        record = DeferredNotificationRecord(
            operator_id=operator_id,
            notification=notification,
            deferred_at=deferred_at,
        )
        with self._lock:
            records = self._load_records_unlocked(operator_id)
            records.append(record)
            self._write_records_unlocked(operator_id, records)

    def list_parked(
        self,
        operator_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = None,
    ) -> list[DeferredNotificationRecord]:
        """Return deferred notifications for one operator."""
        if since is not None and since.tzinfo is None:
            raise ValueError("since must be timezone-aware")
        if until is not None and until.tzinfo is None:
            raise ValueError("until must be timezone-aware")

        with self._lock:
            records = list(self._load_records_unlocked(operator_id))

        if since is not None:
            records = [record for record in records if record.deferred_at >= since]
        if until is not None:
            records = [record for record in records if record.deferred_at <= until]
        if limit is not None:
            if limit <= 0:
                return []
            records = records[-limit:]
        return records

    def list_entries(
        self,
        *,
        operator_id: str,
        since: datetime,
        until: datetime,
    ) -> list[DigestEntry]:
        """Expose deferred notifications as digest-source entries."""
        records = self.list_parked(operator_id, since=since, until=until)
        return [record.to_digest_entry() for record in records]

    def _record_file(self, operator_id: str) -> Path:
        safe_id = _SESSION_ID_SAFE_CHARS.sub("_", operator_id).strip("._-") or "operator"
        digest = hashlib.sha1(operator_id.encode("utf-8")).hexdigest()[:10]
        return self._dir / f"{safe_id}-{digest}.json"

    def _load_records_unlocked(self, operator_id: str) -> list[DeferredNotificationRecord]:
        path = self._record_file(operator_id)
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(raw, dict):
            return []

        payload = raw.get("notifications", [])
        if not isinstance(payload, list):
            return []

        records: list[DeferredNotificationRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            record = self._deserialize_record(operator_id, item)
            if record is not None:
                records.append(record)
        return records

    def _write_records_unlocked(
        self,
        operator_id: str,
        records: list[DeferredNotificationRecord],
    ) -> None:
        path = self._record_file(operator_id)
        payload = {
            "operator_id": operator_id,
            "notifications": [self._serialize_record(record) for record in records],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _serialize_record(record: DeferredNotificationRecord) -> dict[str, object]:
        notification = record.notification
        return {
            "category": notification.category.value,
            "title": notification.title,
            "body": notification.body,
            "deep_link": notification.deep_link,
            "inline_keyboard": [
                {
                    "text": button.text,
                    "callback_data": button.callback_data,
                    "url": button.url,
                }
                for button in notification.inline_keyboard
            ],
            "sensitive": notification.sensitive,
            "workspace_id": notification.workspace_id,
            "run_id": notification.run_id,
            "deferred_at": record.deferred_at.isoformat(),
        }

    @staticmethod
    def _deserialize_record(
        operator_id: str,
        payload: dict[str, object],
    ) -> DeferredNotificationRecord | None:
        try:
            deferred_at_raw = payload.get("deferred_at")
            if not isinstance(deferred_at_raw, str):
                return None
            deferred_at = datetime.fromisoformat(deferred_at_raw)
            if deferred_at.tzinfo is None:
                return None

            category = NotificationCategory(str(payload.get("category", "")))
            buttons = _deserialize_buttons(payload.get("inline_keyboard"))
            notification = Notification(
                category=category,
                title=str(payload.get("title", "")),
                body=str(payload.get("body", "")),
                deep_link=(
                    str(payload["deep_link"]) if payload.get("deep_link") is not None else None
                ),
                inline_keyboard=tuple(buttons),
                sensitive=bool(payload.get("sensitive", False)),
                workspace_id=(
                    str(payload["workspace_id"])
                    if payload.get("workspace_id") is not None
                    else None
                ),
                run_id=str(payload["run_id"]) if payload.get("run_id") is not None else None,
            )
        except (TypeError, ValueError):
            return None

        return DeferredNotificationRecord(
            operator_id=operator_id,
            notification=notification,
            deferred_at=deferred_at,
        )


def _deserialize_buttons(raw: object) -> list[InlineButton]:
    if not isinstance(raw, list):
        return []

    buttons: list[InlineButton] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        callback_data = item.get("callback_data")
        url = item.get("url")
        if not isinstance(text, str):
            continue
        if callback_data is not None and not isinstance(callback_data, str):
            continue
        if url is not None and not isinstance(url, str):
            continue
        try:
            buttons.append(
                InlineButton(
                    text=text,
                    callback_data=callback_data,
                    url=url,
                )
            )
        except ValueError:
            continue
    return buttons
