"""Delivery policy model and persistence.

Defines the policy schema that governs what gets pushed live, batched
into digests, auto-delivered as artifacts, or suppressed.  Persisted
as a single JSON file inside the workspace.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Telegram Bot API hard limits baked into default policy.
_MAX_AUTO_SEND_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
_MAX_AUTO_SEND_ARTIFACTS_PER_RUN = 3
_MIN_PUSH_INTERVAL_SECONDS = 1.0  # ~1 msg/sec per chat
_MAX_GROUP_MESSAGES_PER_MINUTE = 20

# Auto-send-worthy file extensions (safe, typically small).
_AUTO_SEND_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".svg", ".html", ".csv", ".txt", ".md"}
)

# Never auto-send these extensions.
_BLOCKED_EXTENSIONS: frozenset[str] = frozenset(
    {".pkl", ".joblib", ".h5", ".parquet", ".feather", ".arrow", ".log", ".env"}
)


@dataclass
class DeliveryPolicyDefaults:
    """Platform-level delivery constraints."""

    max_auto_send_file_size_bytes: int = _MAX_AUTO_SEND_FILE_SIZE_BYTES
    max_auto_send_artifacts_per_run: int = _MAX_AUTO_SEND_ARTIFACTS_PER_RUN
    min_push_interval_seconds: float = _MIN_PUSH_INTERVAL_SECONDS
    max_group_messages_per_minute: int = _MAX_GROUP_MESSAGES_PER_MINUTE


@dataclass
class DeliveryPolicy:
    """Top-level delivery policy for the runtime."""

    live_push_enabled: bool = True
    digest_enabled: bool = False
    digest_interval_seconds: float = 900.0
    artifact_auto_delivery_enabled: bool = True
    auto_send_extensions: list[str] = field(default_factory=lambda: sorted(_AUTO_SEND_EXTENSIONS))
    blocked_extensions: list[str] = field(default_factory=lambda: sorted(_BLOCKED_EXTENSIONS))
    quiet_hours_start: str = ""
    quiet_hours_end: str = ""
    quiet_hours_timezone: str = "UTC"
    escalation_enabled: bool = True
    escalation_repeat_threshold: int = 3
    platform_defaults: DeliveryPolicyDefaults = field(default_factory=DeliveryPolicyDefaults)
    updated_at: float = field(default_factory=time.time)


@dataclass
class DeliveryPolicyOverride:
    """Partial override applied on top of the default policy."""

    live_push_enabled: bool | None = None
    digest_enabled: bool | None = None
    digest_interval_seconds: float | None = None
    artifact_auto_delivery_enabled: bool | None = None
    auto_send_extensions: list[str] | None = None
    blocked_extensions: list[str] | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_timezone: str | None = None
    escalation_enabled: bool | None = None
    escalation_repeat_threshold: int | None = None
    platform_defaults: DeliveryPolicyDefaults | None = None


class JsonDeliveryPolicyStore:
    """Persistent delivery policy store backed by a single JSON file."""

    def __init__(self, workspace_dir: str | Path) -> None:
        self._path = Path(workspace_dir) / ".ds_agent" / "delivery_policy.json"
        self._lock = threading.Lock()
        self._policy: DeliveryPolicy | None = None
        self._tenant_overrides: dict[str, DeliveryPolicyOverride] = {}
        self._project_overrides: dict[str, DeliveryPolicyOverride] = {}

    def get(self) -> DeliveryPolicy:
        """Return the current delivery policy, creating defaults if absent."""
        with self._lock:
            if self._policy is None:
                self._load()
            assert self._policy is not None
            return self._policy

    def update(self, policy: DeliveryPolicy) -> DeliveryPolicy:
        """Save an updated policy."""
        policy.updated_at = time.time()
        with self._lock:
            self._policy = policy
            self._persist()
        return policy

    def resolve(
        self,
        *,
        tenant: str | None = None,
        project: str | None = None,
    ) -> DeliveryPolicy:
        """Return the effective policy after tenant/project overrides."""

        with self._lock:
            if self._policy is None:
                self._load()
            assert self._policy is not None
            resolved = _copy_policy(self._policy)
            if tenant:
                override = self._tenant_overrides.get(tenant)
                if override is not None:
                    resolved = _apply_override(resolved, override)
            if project:
                override = self._project_overrides.get(project)
                if override is not None:
                    resolved = _apply_override(resolved, override)
            return resolved

    def update_tenant_override(
        self,
        tenant: str,
        override: DeliveryPolicyOverride | dict[str, object],
    ) -> DeliveryPolicyOverride:
        """Persist one tenant-scoped override."""

        with self._lock:
            if self._policy is None:
                self._load()
            payload = _coerce_override(override)
            self._tenant_overrides[str(tenant)] = payload
            self._persist()
            return payload

    def update_project_override(
        self,
        project: str,
        override: DeliveryPolicyOverride | dict[str, object],
    ) -> DeliveryPolicyOverride:
        """Persist one project-scoped override."""

        with self._lock:
            if self._policy is None:
                self._load()
            payload = _coerce_override(override)
            self._project_overrides[str(project)] = payload
            self._persist()
            return payload

    def should_auto_send_file(
        self,
        file_path: str,
        file_size: int,
        *,
        tenant: str | None = None,
        project: str | None = None,
    ) -> bool:
        """Return True if a file is eligible for auto-delivery."""
        policy = self.resolve(tenant=tenant, project=project)
        if not policy.artifact_auto_delivery_enabled:
            return False
        if file_size > policy.platform_defaults.max_auto_send_file_size_bytes:
            return False
        ext = Path(file_path).suffix.lower()
        if ext in {e.lower() for e in policy.blocked_extensions}:
            return False
        return ext in {e.lower() for e in policy.auto_send_extensions}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and (
                    "default_policy" in raw
                    or "tenant_overrides" in raw
                    or "project_overrides" in raw
                ):
                    default_raw = raw.get("default_policy", {})
                    self._policy = _coerce_policy(default_raw)
                    self._tenant_overrides = {
                        str(key): _coerce_override(value)
                        for key, value in dict(raw.get("tenant_overrides", {})).items()
                    }
                    self._project_overrides = {
                        str(key): _coerce_override(value)
                        for key, value in dict(raw.get("project_overrides", {})).items()
                    }
                else:
                    self._policy = _coerce_policy(raw)
                    self._tenant_overrides = {}
                    self._project_overrides = {}
                return
            except Exception:
                pass
        self._policy = DeliveryPolicy()
        self._tenant_overrides = {}
        self._project_overrides = {}
        self._persist()

    def _persist(self) -> None:
        if self._policy is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "default_policy": asdict(self._policy),
            "tenant_overrides": {
                key: _serialize_override(value)
                for key, value in self._tenant_overrides.items()
            },
            "project_overrides": {
                key: _serialize_override(value)
                for key, value in self._project_overrides.items()
            },
        }
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _coerce_policy(raw: object) -> DeliveryPolicy:
    payload = dict(raw) if isinstance(raw, dict) else {}
    defaults_raw = payload.pop("platform_defaults", {})
    defaults = (
        DeliveryPolicyDefaults(**defaults_raw)
        if isinstance(defaults_raw, dict) and defaults_raw
        else DeliveryPolicyDefaults()
    )
    return DeliveryPolicy(**payload, platform_defaults=defaults)


def _copy_policy(policy: DeliveryPolicy) -> DeliveryPolicy:
    return _coerce_policy(asdict(policy))


def _coerce_override(raw: DeliveryPolicyOverride | dict[str, object]) -> DeliveryPolicyOverride:
    if isinstance(raw, DeliveryPolicyOverride):
        return raw
    payload = dict(raw)
    defaults_raw = payload.get("platform_defaults")
    platform_defaults: DeliveryPolicyDefaults | None = None
    if isinstance(defaults_raw, DeliveryPolicyDefaults):
        platform_defaults = defaults_raw
    elif isinstance(defaults_raw, dict):
        platform_defaults = DeliveryPolicyDefaults(**defaults_raw)
    return DeliveryPolicyOverride(
        live_push_enabled=_optional_bool(payload.get("live_push_enabled")),
        digest_enabled=_optional_bool(payload.get("digest_enabled")),
        digest_interval_seconds=_optional_float(payload.get("digest_interval_seconds")),
        artifact_auto_delivery_enabled=_optional_bool(
            payload.get("artifact_auto_delivery_enabled")
        ),
        auto_send_extensions=_optional_str_list(payload.get("auto_send_extensions")),
        blocked_extensions=_optional_str_list(payload.get("blocked_extensions")),
        quiet_hours_start=_optional_str(payload.get("quiet_hours_start")),
        quiet_hours_end=_optional_str(payload.get("quiet_hours_end")),
        quiet_hours_timezone=_optional_str(payload.get("quiet_hours_timezone")),
        escalation_enabled=_optional_bool(payload.get("escalation_enabled")),
        escalation_repeat_threshold=_optional_int(payload.get("escalation_repeat_threshold")),
        platform_defaults=platform_defaults,
    )


def _apply_override(
    policy: DeliveryPolicy,
    override: DeliveryPolicyOverride,
) -> DeliveryPolicy:
    resolved = _copy_policy(policy)
    for field_name, value in asdict(override).items():
        if value is None:
            continue
        if field_name == "platform_defaults":
            resolved.platform_defaults = DeliveryPolicyDefaults(**value)
            continue
        setattr(resolved, field_name, value)
    return resolved


def _serialize_override(override: DeliveryPolicyOverride) -> dict[str, object]:
    payload = asdict(override)
    return {
        key: value
        for key, value in payload.items()
        if value is not None
    }


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_float(value: object) -> float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_str_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return list(value)
