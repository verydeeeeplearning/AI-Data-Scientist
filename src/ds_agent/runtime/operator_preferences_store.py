"""Per-chat operator notification preferences.

Each Telegram chat (or future channel target) can express what it wants
to receive and how.  Preferences are persisted as a single JSON file
inside the workspace directory.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_NOTIFICATION_CATEGORIES: frozenset[str] = frozenset(
    {
        "recovery",
        "approval",
        "health",
        "pressure",
        "policy",
    }
)

_ALL_SEVERITIES = ("info", "warning", "error", "critical")
_DIGEST_CADENCES = ("interval", "hourly", "morning", "end_of_day")
_DIGEST_CADENCE_ALIASES = {
    "interval": "interval",
    "hourly": "hourly",
    "morning": "morning",
    "eod": "end_of_day",
    "end_of_day": "end_of_day",
    "end-of-day": "end_of_day",
}


def normalize_digest_cadence(value: str) -> str | None:
    """Normalize user-facing digest cadence tokens to one stored value."""
    return _DIGEST_CADENCE_ALIASES.get(value.strip().lower())


def digest_cadence_label(cadence: str, interval_seconds: float) -> str:
    """Return a compact operator-facing label for one digest cadence."""
    normalized = normalize_digest_cadence(cadence) or "interval"
    if normalized == "hourly":
        return "hourly"
    if normalized == "morning":
        return "morning 09:00"
    if normalized == "end_of_day":
        return "end-of-day 18:00"
    interval = max(60, int(interval_seconds))
    if interval < 3600:
        return f"{interval // 60}m interval"
    if interval % 3600 == 0:
        return f"{interval // 3600}h interval"
    return f"{interval // 60}m interval"


@dataclass
class ChatPreference:
    """Notification preferences for one operator chat."""

    chat_id: str
    enabled: bool = True
    muted_until: float = 0.0
    min_severity: str = "warning"
    subscribed_categories: set[str] = field(
        default_factory=lambda: set(DEFAULT_NOTIFICATION_CATEGORIES)
    )
    approvals_only: bool = False
    digest_mode: bool = False
    digest_interval_seconds: float = 900.0
    digest_cadence: str = "interval"
    timezone: str = "UTC"
    updated_at: float = field(default_factory=time.time)


class JsonOperatorPreferencesStore:
    """Persistent per-chat preference store backed by a single JSON file."""

    def __init__(self, workspace_dir: str | Path) -> None:
        self._path = Path(workspace_dir) / ".ds_agent" / "operator_preferences.json"
        self._lock = threading.Lock()
        self._cache: dict[str, ChatPreference] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, chat_id: str) -> ChatPreference:
        """Return preference for *chat_id*, creating defaults if absent."""
        self._ensure_loaded()
        with self._lock:
            if chat_id not in self._cache:
                self._cache[chat_id] = ChatPreference(chat_id=chat_id)
                self._persist()
            return self._cache[chat_id]

    def update(self, pref: ChatPreference) -> ChatPreference:
        """Save an updated preference and return it."""
        pref.updated_at = time.time()
        with self._lock:
            self._cache[pref.chat_id] = pref
            self._persist()
        return pref

    def set_min_severity(self, chat_id: str, severity: str) -> ChatPreference:
        """Change minimum push severity for *chat_id*."""
        if severity not in _ALL_SEVERITIES:
            raise ValueError(f"Unknown severity: {severity}")
        pref = self.get(chat_id)
        pref.min_severity = severity
        return self.update(pref)

    def set_enabled(self, chat_id: str, enabled: bool) -> ChatPreference:
        """Enable or disable live notifications for *chat_id*."""
        pref = self.get(chat_id)
        pref.enabled = enabled
        return self.update(pref)

    def set_muted(self, chat_id: str, duration_seconds: float) -> ChatPreference:
        """Mute a chat for *duration_seconds*."""
        pref = self.get(chat_id)
        pref.muted_until = time.time() + duration_seconds
        return self.update(pref)

    def unmute(self, chat_id: str) -> ChatPreference:
        pref = self.get(chat_id)
        pref.muted_until = 0.0
        return self.update(pref)

    def set_approvals_only(self, chat_id: str, value: bool) -> ChatPreference:
        pref = self.get(chat_id)
        pref.approvals_only = value
        return self.update(pref)

    def set_digest_mode(
        self,
        chat_id: str,
        enabled: bool,
        interval_seconds: float | None = None,
        cadence: str | None = None,
    ) -> ChatPreference:
        pref = self.get(chat_id)
        pref.digest_mode = enabled
        if interval_seconds is not None:
            pref.digest_interval_seconds = max(60.0, interval_seconds)
        if cadence is not None:
            normalized = normalize_digest_cadence(cadence)
            if normalized is None:
                raise ValueError(f"Unknown digest cadence: {cadence}")
            pref.digest_cadence = normalized
        return self.update(pref)

    def set_timezone(self, chat_id: str, timezone: str) -> ChatPreference:
        pref = self.get(chat_id)
        pref.timezone = timezone.strip() or "UTC"
        return self.update(pref)

    def set_subscribed_categories(
        self,
        chat_id: str,
        categories: set[str],
    ) -> ChatPreference:
        pref = self.get(chat_id)
        pref.subscribed_categories = categories
        return self.update(pref)

    def is_muted(self, chat_id: str) -> bool:
        pref = self.get(chat_id)
        return pref.muted_until > time.time()

    def should_push(self, chat_id: str, category: str, severity: str) -> bool:
        """Return True if a live push should be sent to this chat."""
        pref = self.get(chat_id)
        if not pref.enabled:
            return False
        if pref.approvals_only and category != "approval":
            return False
        if self.is_muted(chat_id) and severity != "critical":
            return False
        if category not in pref.subscribed_categories:
            return False
        sev_index = _ALL_SEVERITIES.index(severity) if severity in _ALL_SEVERITIES else 0
        min_index = (
            _ALL_SEVERITIES.index(pref.min_severity) if pref.min_severity in _ALL_SEVERITIES else 0
        )
        return sev_index >= min_index

    def list_all(self) -> list[ChatPreference]:
        self._ensure_loaded()
        with self._lock:
            return list(self._cache.values())

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

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
                        raw.setdefault("chat_id", chat_id)
                        cats = raw.pop("subscribed_categories", None)
                        pref = ChatPreference(**raw)
                        if isinstance(cats, list):
                            pref.subscribed_categories = set(cats)
                        self._cache[chat_id] = pref
                except Exception:
                    pass
            self._loaded = True

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serializable: dict[str, dict] = {}
        for chat_id, pref in self._cache.items():
            d = asdict(pref)
            d["subscribed_categories"] = sorted(pref.subscribed_categories)
            serializable[chat_id] = d
        self._path.write_text(
            json.dumps(serializable, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
