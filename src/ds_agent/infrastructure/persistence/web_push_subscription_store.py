"""JSON-backed persistence for web push subscriptions (Wave 4 PLAN_06b).

Per-operator file layout, mirroring
:mod:`ds_agent.runtime.deferred_notification_store` so we don't share a
single hot write target across every operator.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.runtime.transcript_store import (
    _SESSION_ID_SAFE_CHARS,
    get_runtime_storage_root,
)


@dataclass(frozen=True, slots=True)
class WebPushSubscription:
    """One browser PushManager subscription, persisted per operator.

    Field names match the W3C Push API ``PushSubscription.toJSON()``
    output ``keys.{p256dh,auth}`` to keep the round-trip with the renderer
    one-to-one.
    """

    endpoint: str
    p256dh_key: str
    auth_key: str
    created_at: datetime
    last_used_at: datetime | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.endpoint.strip():
            raise ValueError("WebPushSubscription.endpoint must be non-empty")
        if not self.p256dh_key.strip() or not self.auth_key.strip():
            raise ValueError("WebPushSubscription requires p256dh_key and auth_key")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.last_used_at is not None and self.last_used_at.tzinfo is None:
            raise ValueError("last_used_at must be timezone-aware")


class JsonWebPushSubscriptionStore:
    """Persist :class:`WebPushSubscription` objects as per-operator JSON.

    Structural impl of
    :class:`ds_agent.application.use_cases.dispatch_web_push_usecase.WebPushSubscriptionStorePort`.
    The Protocol is intentionally NOT subclassed: ``WebPushSubscription``
    here is a concrete dataclass while the Protocol declares structural
    ``WebPushSubscription`` properties — invariant ``list[…]`` returns
    fail nominal subtype checks but satisfy the structural contract.

    De-duplicates by ``endpoint`` so re-registering the same browser
    subscription updates ``last_used_at`` rather than creating a phantom
    duplicate that would produce double pushes.
    """

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._dir = root / "web-push-subscriptions"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        operator_id: str,
        subscription: WebPushSubscription,
    ) -> WebPushSubscription:
        """Insert or refresh *subscription* for *operator_id*.

        Returns the stored subscription (may have an updated
        ``last_used_at``).
        """
        with self._lock:
            records = self._load_records_unlocked(operator_id)
            now = datetime.now(UTC)
            updated: list[WebPushSubscription] = []
            replaced = False
            for existing in records:
                if existing.endpoint == subscription.endpoint:
                    refreshed = replace(
                        existing,
                        p256dh_key=subscription.p256dh_key,
                        auth_key=subscription.auth_key,
                        last_used_at=now,
                    )
                    updated.append(refreshed)
                    replaced = True
                else:
                    updated.append(existing)
            if not replaced:
                updated.append(subscription)
            self._write_records_unlocked(operator_id, updated)
            for stored in updated:
                if stored.endpoint == subscription.endpoint:
                    return stored
            return subscription  # pragma: no cover - defensive

    def unregister(self, operator_id: str, endpoint: str) -> bool:
        """Remove the subscription with *endpoint*; return True if removed."""
        with self._lock:
            records = self._load_records_unlocked(operator_id)
            kept = [r for r in records if r.endpoint != endpoint]
            if len(kept) == len(records):
                return False
            self._write_records_unlocked(operator_id, kept)
            return True

    def list_for(self, operator_id: str) -> list[WebPushSubscription]:
        """Return the operator's currently registered subscriptions."""
        with self._lock:
            return list(self._load_records_unlocked(operator_id))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _record_file(self, operator_id: str) -> Path:
        safe_id = _SESSION_ID_SAFE_CHARS.sub("_", operator_id).strip("._-") or "operator"
        digest = hashlib.sha1(operator_id.encode("utf-8")).hexdigest()[:10]
        return self._dir / f"{safe_id}-{digest}.json"

    def _load_records_unlocked(self, operator_id: str) -> list[WebPushSubscription]:
        path = self._record_file(operator_id)
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(raw, dict):
            return []
        payload = raw.get("subscriptions", [])
        if not isinstance(payload, list):
            return []

        records: list[WebPushSubscription] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                created_raw = item.get("created_at")
                last_raw = item.get("last_used_at")
                if not isinstance(created_raw, str):
                    continue
                created_at = datetime.fromisoformat(created_raw)
                last_used_at: datetime | None
                if isinstance(last_raw, str) and last_raw:
                    last_used_at = datetime.fromisoformat(last_raw)
                else:
                    last_used_at = None
                records.append(
                    WebPushSubscription(
                        endpoint=str(item.get("endpoint", "")),
                        p256dh_key=str(item.get("p256dh_key", "")),
                        auth_key=str(item.get("auth_key", "")),
                        created_at=created_at,
                        last_used_at=last_used_at,
                    )
                )
            except (TypeError, ValueError):
                continue
        return records

    def _write_records_unlocked(
        self,
        operator_id: str,
        records: list[WebPushSubscription],
    ) -> None:
        path = self._record_file(operator_id)
        payload = {
            "operator_id": operator_id,
            "subscriptions": [
                {
                    "endpoint": record.endpoint,
                    "p256dh_key": record.p256dh_key,
                    "auth_key": record.auth_key,
                    "created_at": record.created_at.isoformat(),
                    "last_used_at": (
                        record.last_used_at.isoformat() if record.last_used_at is not None else None
                    ),
                }
                for record in records
            ],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


__all__ = ["JsonWebPushSubscriptionStore", "WebPushSubscription"]
