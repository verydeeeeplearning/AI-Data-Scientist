"""File-backed organization policy and usage store."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from ds_agent.domain.entities.organization import (
    Member,
    Organization,
    OrgRole,
    OrgSettings,
    OrgUsageRecord,
)
from ds_agent.runtime.transcript_store import get_runtime_storage_root

UNSET = object()


class JsonOrganizationStore:
    """Persist organization settings, members, and usage records."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._file = root / "organization.json"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self._file.exists():
            self._save_unlocked(self._default_payload(workspace_dir))

    def get(self) -> Organization:
        """Return the current organization snapshot."""
        data = self._load()
        return self._deserialize_org(data.get("organization", {}))

    def update_settings(
        self,
        *,
        allowed_providers: object = UNSET,
        max_budget_usd_per_user: object = UNSET,
        max_budget_usd_per_org: object = UNSET,
        external_data_transfer_allowed: object = UNSET,
        export_allowed: object = UNSET,
        connector_creation_allowed: object = UNSET,
    ) -> Organization:
        """Update organization settings and persist them."""
        with self._lock:
            data = self._load_unlocked()
            org = self._deserialize_org(data.get("organization", {}))
            if allowed_providers is not UNSET:
                provider_values = allowed_providers if isinstance(allowed_providers, list) else []
                org.settings.allowed_providers = sorted(
                    {item.strip() for item in provider_values if item.strip()}
                )
            if max_budget_usd_per_user is not UNSET:
                org.settings.max_budget_usd_per_user = (
                    None
                    if max_budget_usd_per_user is None or float(max_budget_usd_per_user) <= 0
                    else float(max_budget_usd_per_user)
                )
            if max_budget_usd_per_org is not UNSET:
                org.settings.max_budget_usd_per_org = (
                    None
                    if max_budget_usd_per_org is None or float(max_budget_usd_per_org) <= 0
                    else float(max_budget_usd_per_org)
                )
            if external_data_transfer_allowed is not UNSET:
                org.settings.external_data_transfer_allowed = bool(external_data_transfer_allowed)
            if export_allowed is not UNSET:
                org.settings.export_allowed = bool(export_allowed)
            if connector_creation_allowed is not UNSET:
                org.settings.connector_creation_allowed = bool(connector_creation_allowed)
            org.updated_at = time.time()
            data["organization"] = self._serialize_org(org)
            self._save_unlocked(data)
            return org

    def invite_member(
        self,
        user_id: str,
        *,
        role: OrgRole = OrgRole.VIEWER,
        display_name: str | None = None,
    ) -> Organization:
        """Create or update one organization member."""
        normalized_user_id = user_id.strip()
        if not normalized_user_id:
            raise ValueError("user_id is required")

        with self._lock:
            data = self._load_unlocked()
            org = self._deserialize_org(data.get("organization", {}))
            existing = org.get_member(normalized_user_id)
            if existing is None:
                org.members.append(
                    Member(
                        user_id=normalized_user_id,
                        role=role,
                        display_name=display_name.strip() if display_name else None,
                    )
                )
            else:
                existing.role = role
                if display_name is not None:
                    existing.display_name = display_name.strip() or None
            org.updated_at = time.time()
            data["organization"] = self._serialize_org(org)
            self._save_unlocked(data)
            return org

    def update_member_role(self, user_id: str, role: OrgRole) -> Organization:
        """Update one member role, keeping at least one admin."""
        normalized_user_id = user_id.strip()
        with self._lock:
            data = self._load_unlocked()
            org = self._deserialize_org(data.get("organization", {}))
            member = org.get_member(normalized_user_id)
            if member is None:
                raise ValueError(f"Unknown member: {normalized_user_id}")
            if member.role == OrgRole.ADMIN and role != OrgRole.ADMIN:
                admin_count = sum(1 for item in org.members if item.role == OrgRole.ADMIN)
                if admin_count <= 1:
                    raise ValueError("At least one admin must remain in the organization")
            member.role = role
            org.updated_at = time.time()
            data["organization"] = self._serialize_org(org)
            self._save_unlocked(data)
            return org

    def record_usage(
        self,
        *,
        actor_id: str,
        provider: str,
        cost_usd: float,
        model: str | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
        cache_savings_usd: float = 0.0,
        recorded_at: float | None = None,
    ) -> OrgUsageRecord:
        """Append one usage record."""
        record = OrgUsageRecord(
            actor_id=actor_id.strip() or "local-user",
            provider=provider.strip() or "unknown",
            cost_usd=max(float(cost_usd), 0.0),
            model=model.strip() if isinstance(model, str) and model.strip() else None,
            session_id=session_id,
            run_id=run_id,
            input_tokens=max(int(input_tokens), 0),
            output_tokens=max(int(output_tokens), 0),
            cache_read_tokens=max(int(cache_read_tokens), 0),
            cache_write_tokens=max(int(cache_write_tokens), 0),
            reasoning_tokens=max(int(reasoning_tokens), 0),
            cache_savings_usd=max(float(cache_savings_usd), 0.0),
            recorded_at=time.time() if recorded_at is None else float(recorded_at),
        )
        with self._lock:
            data = self._load_unlocked()
            usage = data.get("usage_records", [])
            if not isinstance(usage, list):
                usage = []
            usage.append(self._serialize_usage(record))
            data["usage_records"] = usage[-5000:]
            self._save_unlocked(data)
        return record

    def list_usage_records(
        self,
        *,
        start_ts: float | None = None,
        end_ts: float | None = None,
        actor_id: str | None = None,
    ) -> list[OrgUsageRecord]:
        """Return usage records filtered by time range and actor."""
        data = self._load()
        usage = data.get("usage_records", [])
        if not isinstance(usage, list):
            return []
        records = [self._deserialize_usage(item) for item in usage if isinstance(item, dict)]
        filtered: list[OrgUsageRecord] = []
        for record in records:
            if actor_id is not None and record.actor_id != actor_id:
                continue
            if start_ts is not None and record.recorded_at < start_ts:
                continue
            if end_ts is not None and record.recorded_at > end_ts:
                continue
            filtered.append(record)
        filtered.sort(key=lambda item: item.recorded_at, reverse=True)
        return filtered

    def get_usage_summary(
        self,
        *,
        start_ts: float | None = None,
        end_ts: float | None = None,
    ) -> dict[str, object]:
        """Return aggregate cost and run counts by actor/provider."""
        records = self.list_usage_records(start_ts=start_ts, end_ts=end_ts)
        per_user: dict[str, dict[str, object]] = {}
        total_cost = 0.0
        total_cache_savings = 0.0
        total_runs = 0
        for record in records:
            total_cost += record.cost_usd
            total_cache_savings += record.cache_savings_usd
            total_runs += 1
            summary = per_user.setdefault(
                record.actor_id,
                {
                    "actorId": record.actor_id,
                    "costUsd": 0.0,
                    "cacheSavingsUsd": 0.0,
                    "runCount": 0,
                    "providers": {},
                },
            )
            summary["costUsd"] = float(summary["costUsd"]) + record.cost_usd
            summary["cacheSavingsUsd"] = (
                float(summary["cacheSavingsUsd"]) + record.cache_savings_usd
            )
            summary["runCount"] = int(summary["runCount"]) + 1
            providers = summary["providers"]
            if isinstance(providers, dict):
                providers[record.provider] = (
                    float(providers.get(record.provider, 0.0)) + record.cost_usd
                )

        return {
            "totalCostUsd": total_cost,
            "totalCacheSavingsUsd": total_cache_savings,
            "totalRunCount": total_runs,
            "perUser": sorted(
                per_user.values(),
                key=lambda item: (-float(item["costUsd"]), str(item["actorId"])),
            ),
        }

    @staticmethod
    def month_range(now: float | None = None) -> tuple[float, float]:
        """Return the current calendar month's inclusive epoch range."""
        import calendar
        from datetime import datetime

        dt = datetime.fromtimestamp(time.time() if now is None else now)
        start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(dt.year, dt.month)[1]
        end = dt.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
        return start.timestamp(), end.timestamp()

    def current_month_cost_for_actor(self, actor_id: str) -> float:
        """Return the actor's current month cost."""
        start_ts, end_ts = self.month_range()
        return sum(
            item.cost_usd
            for item in self.list_usage_records(
                start_ts=start_ts,
                end_ts=end_ts,
                actor_id=actor_id,
            )
        )

    def current_month_cost_for_org(self) -> float:
        """Return the organization's current month cost."""
        start_ts, end_ts = self.month_range()
        return sum(
            item.cost_usd for item in self.list_usage_records(start_ts=start_ts, end_ts=end_ts)
        )

    def is_admin(self, actor_id: str) -> bool:
        """Return whether the actor is an org admin."""
        return self.get().is_admin(actor_id)

    def _load(self) -> dict[str, object]:
        with self._lock:
            return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, object]:
        try:
            payload = json.loads(self._file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            payload = self._default_payload(None)
            self._save_unlocked(payload)
        return payload if isinstance(payload, dict) else self._default_payload(None)

    def _save_unlocked(self, payload: dict[str, object]) -> None:
        self._file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _default_payload(workspace_dir: str | None) -> dict[str, object]:
        workspace_name = "Local Team"
        if workspace_dir:
            workspace_name = f"{Path(workspace_dir).name or 'Workspace'} Team"
        now = time.time()
        return {
            "organization": {
                "id": "local-org",
                "name": workspace_name,
                "members": [
                    {
                        "user_id": "local-user",
                        "role": OrgRole.ADMIN.value,
                        "display_name": "Local Admin",
                        "invited_at": now,
                    }
                ],
                "settings": {
                    "allowed_providers": [],
                    "max_budget_usd_per_user": None,
                    "max_budget_usd_per_org": None,
                    "external_data_transfer_allowed": True,
                    "export_allowed": True,
                    "connector_creation_allowed": True,
                },
                "created_at": now,
                "updated_at": now,
            },
            "usage_records": [],
        }

    @staticmethod
    def _serialize_org(org: Organization) -> dict[str, object]:
        return {
            "id": org.id,
            "name": org.name,
            "members": [
                {
                    "user_id": member.user_id,
                    "role": member.role.value,
                    "display_name": member.display_name,
                    "invited_at": member.invited_at,
                }
                for member in org.members
            ],
            "settings": {
                "allowed_providers": list(org.settings.allowed_providers),
                "max_budget_usd_per_user": org.settings.max_budget_usd_per_user,
                "max_budget_usd_per_org": org.settings.max_budget_usd_per_org,
                "external_data_transfer_allowed": org.settings.external_data_transfer_allowed,
                "export_allowed": org.settings.export_allowed,
                "connector_creation_allowed": org.settings.connector_creation_allowed,
            },
            "created_at": org.created_at,
            "updated_at": org.updated_at,
        }

    @staticmethod
    def _deserialize_org(data: object) -> Organization:
        raw = data if isinstance(data, dict) else {}
        raw_settings = raw.get("settings", {})
        settings = OrgSettings(
            allowed_providers=[
                str(item)
                for item in raw_settings.get("allowed_providers", [])
                if isinstance(item, str)
            ]
            if isinstance(raw_settings, dict)
            else [],
            max_budget_usd_per_user=(
                float(raw_settings["max_budget_usd_per_user"])
                if isinstance(raw_settings, dict)
                and raw_settings.get("max_budget_usd_per_user") is not None
                else None
            ),
            max_budget_usd_per_org=(
                float(raw_settings["max_budget_usd_per_org"])
                if isinstance(raw_settings, dict)
                and raw_settings.get("max_budget_usd_per_org") is not None
                else None
            ),
            external_data_transfer_allowed=bool(
                raw_settings.get("external_data_transfer_allowed", True)
            )
            if isinstance(raw_settings, dict)
            else True,
            export_allowed=bool(raw_settings.get("export_allowed", True))
            if isinstance(raw_settings, dict)
            else True,
            connector_creation_allowed=bool(raw_settings.get("connector_creation_allowed", True))
            if isinstance(raw_settings, dict)
            else True,
        )
        raw_members = raw.get("members", [])
        members = [
            Member(
                user_id=str(item.get("user_id", "")),
                role=OrgRole(str(item.get("role", OrgRole.VIEWER.value))),
                display_name=(
                    str(item["display_name"]) if item.get("display_name") is not None else None
                ),
                invited_at=float(item.get("invited_at", time.time())),
            )
            for item in raw_members
            if isinstance(item, dict)
        ]
        if not members:
            members = [Member(user_id="local-user", role=OrgRole.ADMIN, display_name="Local Admin")]
        return Organization(
            id=str(raw.get("id", "local-org")),
            name=str(raw.get("name", "Local Team")),
            members=members,
            settings=settings,
            created_at=float(raw.get("created_at", time.time())),
            updated_at=float(raw.get("updated_at", time.time())),
        )

    @staticmethod
    def _serialize_usage(record: OrgUsageRecord) -> dict[str, object]:
        return {
            "actor_id": record.actor_id,
            "provider": record.provider,
            "cost_usd": record.cost_usd,
            "model": record.model,
            "session_id": record.session_id,
            "run_id": record.run_id,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
            "cache_read_tokens": record.cache_read_tokens,
            "cache_write_tokens": record.cache_write_tokens,
            "reasoning_tokens": record.reasoning_tokens,
            "cache_savings_usd": record.cache_savings_usd,
            "recorded_at": record.recorded_at,
        }

    @staticmethod
    def _deserialize_usage(data: dict[str, object]) -> OrgUsageRecord:
        return OrgUsageRecord(
            actor_id=str(data.get("actor_id", "local-user")),
            provider=str(data.get("provider", "unknown")),
            cost_usd=float(data.get("cost_usd", 0.0)),
            model=str(data["model"]) if data.get("model") is not None else None,
            session_id=str(data["session_id"]) if data.get("session_id") is not None else None,
            run_id=str(data["run_id"]) if data.get("run_id") is not None else None,
            input_tokens=int(data.get("input_tokens", 0)),
            output_tokens=int(data.get("output_tokens", 0)),
            cache_read_tokens=int(data.get("cache_read_tokens", 0)),
            cache_write_tokens=int(data.get("cache_write_tokens", 0)),
            reasoning_tokens=int(data.get("reasoning_tokens", 0)),
            cache_savings_usd=float(data.get("cache_savings_usd", 0.0)),
            recorded_at=float(data.get("recorded_at", time.time())),
        )
