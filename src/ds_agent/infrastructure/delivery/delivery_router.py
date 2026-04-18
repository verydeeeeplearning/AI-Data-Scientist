"""Policy-aware delivery routing for stakeholder artifacts."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, cast

from ds_agent.application.dtos.delivery import (
    DeliveryLogQueryResult,
    DeliveryLogSummary,
    DispatchDeliveryResult,
    DispatchLogRecord,
    DispatchReceipt,
)
from ds_agent.domain.entities.delivery_pack import (
    AudienceKind,
    DeliveryArtifact,
    DeliveryChannel,
    DeliveryDispatchMode,
    DeliveryPack,
)
from ds_agent.runtime.delivery_policy_store import DeliveryPolicy, JsonDeliveryPolicyStore

_AUDIENCE_ALLOWED_CHANNELS: dict[AudienceKind, set[DeliveryChannel]] = {
    AudienceKind.EXECUTIVE: {DeliveryChannel.EMAIL, DeliveryChannel.SLACK_DM},
    AudienceKind.PM: {DeliveryChannel.SLACK_CHANNEL, DeliveryChannel.NOTION_PAGE},
    AudienceKind.DS_PEER: {DeliveryChannel.GIT_PR},
    AudienceKind.ML_ENGINEER: {DeliveryChannel.CONFLUENCE, DeliveryChannel.JIRA_TICKET},
    AudienceKind.AUDITOR: {DeliveryChannel.COMPLIANCE_SYSTEM},
    AudienceKind.JUNIOR_MENTEE: {DeliveryChannel.NOTION_PAGE},
    AudienceKind.SENIOR_STAFF: {DeliveryChannel.CONFLUENCE},
    AudienceKind.OPS: {DeliveryChannel.SLACK_CHANNEL},
    AudienceKind.CUSTOMER: {DeliveryChannel.EMAIL},
}


class ChannelAdapter(Protocol):
    """One channel-specific adapter used by the delivery router."""

    @property
    def name(self) -> str: ...

    def send(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
    ) -> str: ...


@dataclass(frozen=True)
class SimulatedChannelAdapter:
    """Deterministic adapter used until real channel integrations land."""

    name: str

    def send(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
    ) -> str:
        return f"{self.name}:{pack.pack_id}:{artifact.artifact_id}:{channel.value}"


@dataclass(frozen=True)
class DeliveryLogEntry:
    """Persisted dispatch attempt for audit and idempotency."""

    task_id: str
    pack_id: str
    artifact_id: str
    channel: str
    status: str
    idempotency_key: str
    recorded_at: str
    reason: str | None = None
    receipt_id: str | None = None
    adapter_name: str | None = None


class DeliveryDispatchLog(Protocol):
    """Persistence contract for dispatch attempts and idempotency checks."""

    @property
    def path(self) -> Path: ...

    def append(self, entry: DeliveryLogEntry) -> None: ...

    def successful_dispatch_for(self, idempotency_key: str) -> DeliveryLogEntry | None: ...

    def list_for_pack(self, pack_id: str) -> list[DeliveryLogEntry]: ...

    def query(
        self,
        *,
        task_id: str,
        pack_id: str | None = None,
        artifact_ids: set[str] | None = None,
        channels: set[DeliveryChannel] | None = None,
        limit: int = 50,
    ) -> DeliveryLogQueryResult: ...

    def summarize(self, *, pack: DeliveryPack) -> DeliveryLogSummary: ...


class JsonlDeliveryDispatchLog:
    """Append-only dispatch log with idempotency lookup."""

    def __init__(self, base_dir: str | Path) -> None:
        self._path = Path(base_dir) / "delivery_dispatch_log.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, entry: DeliveryLogEntry) -> None:
        payload = json.dumps(asdict(entry), ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")

    def successful_dispatch_for(self, idempotency_key: str) -> DeliveryLogEntry | None:
        with self._lock:
            for entry in reversed(self._load_entries_unlocked()):
                if entry.idempotency_key == idempotency_key and entry.status == "sent":
                    return entry
        return None

    def list_for_pack(self, pack_id: str) -> list[DeliveryLogEntry]:
        with self._lock:
            return [entry for entry in self._load_entries_unlocked() if entry.pack_id == pack_id]

    def query(
        self,
        *,
        task_id: str,
        pack_id: str | None = None,
        artifact_ids: set[str] | None = None,
        channels: set[DeliveryChannel] | None = None,
        limit: int = 50,
    ) -> DeliveryLogQueryResult:
        with self._lock:
            entries = list(reversed(self._load_entries_unlocked()))
        channel_values = {channel.value for channel in channels} if channels is not None else None

        filtered: list[DispatchLogRecord] = []
        for entry in entries:
            if entry.task_id != task_id:
                continue
            if pack_id is not None and entry.pack_id != pack_id:
                continue
            if artifact_ids is not None and entry.artifact_id not in artifact_ids:
                continue
            if channel_values is not None and entry.channel not in channel_values:
                continue
            filtered.append(_log_entry_to_record(entry))
            if len(filtered) >= limit:
                break

        return DeliveryLogQueryResult(
            task_id=task_id,
            pack_id=pack_id,
            log_path=self.path,
            records=tuple(filtered),
        )

    def summarize(self, *, pack: DeliveryPack) -> DeliveryLogSummary:
        with self._lock:
            entries = [
                entry for entry in self._load_entries_unlocked() if entry.pack_id == pack.pack_id
            ]
        return _build_summary_from_entries(pack=pack, entries=entries)

    def _load_entries_unlocked(self) -> list[DeliveryLogEntry]:
        if not self._path.exists():
            return []

        entries: list[DeliveryLogEntry] = []
        for raw_line in self._path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            try:
                entries.append(DeliveryLogEntry(**payload))
            except TypeError:
                continue
        return entries


class SqliteDeliveryDispatchLog:
    """SQLite-backed dispatch log used by persisted task-contract flows."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, entry: DeliveryLogEntry) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO delivery_log (
                    task_id,
                    pack_id,
                    artifact_id,
                    channel,
                    status,
                    attempted_at,
                    reason,
                    receipt_ref,
                    adapter_name,
                    idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.task_id,
                    entry.pack_id,
                    entry.artifact_id,
                    entry.channel,
                    entry.status,
                    entry.recorded_at,
                    entry.reason,
                    entry.receipt_id,
                    entry.adapter_name,
                    entry.idempotency_key,
                ),
            )
            conn.commit()

    def successful_dispatch_for(self, idempotency_key: str) -> DeliveryLogEntry | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    task_id,
                    pack_id,
                    artifact_id,
                    channel,
                    status,
                    attempted_at,
                    reason,
                    receipt_ref,
                    adapter_name,
                    idempotency_key
                FROM delivery_log
                WHERE idempotency_key = ?
                  AND status = 'sent'
                ORDER BY log_id DESC
                LIMIT 1
                """,
                (idempotency_key,),
            ).fetchone()
        return _row_to_delivery_log_entry(row)

    def list_for_pack(self, pack_id: str) -> list[DeliveryLogEntry]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    task_id,
                    pack_id,
                    artifact_id,
                    channel,
                    status,
                    attempted_at,
                    reason,
                    receipt_ref,
                    adapter_name,
                    idempotency_key
                FROM delivery_log
                WHERE pack_id = ?
                ORDER BY log_id ASC
                """,
                (pack_id,),
            ).fetchall()
        return [entry for row in rows if (entry := _row_to_delivery_log_entry(row)) is not None]

    def query(
        self,
        *,
        task_id: str,
        pack_id: str | None = None,
        artifact_ids: set[str] | None = None,
        channels: set[DeliveryChannel] | None = None,
        limit: int = 50,
    ) -> DeliveryLogQueryResult:
        clauses = ["task_id = ?"]
        params: list[str | int] = [task_id]
        if pack_id is not None:
            clauses.append("pack_id = ?")
            params.append(pack_id)
        if artifact_ids:
            placeholders = ", ".join("?" for _ in artifact_ids)
            clauses.append(f"artifact_id IN ({placeholders})")
            params.extend(sorted(artifact_ids))
        if channels:
            placeholders = ", ".join("?" for _ in channels)
            clauses.append(f"channel IN ({placeholders})")
            params.extend(sorted(channel.value for channel in channels))

        where_sql = " AND ".join(clauses)
        query = f"""
            SELECT
                task_id,
                pack_id,
                artifact_id,
                channel,
                status,
                attempted_at,
                reason,
                receipt_ref,
                adapter_name,
                idempotency_key
            FROM delivery_log
            WHERE {where_sql}
            ORDER BY log_id DESC
            LIMIT ?
        """
        params.append(limit)
        with self._lock, self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        return DeliveryLogQueryResult(
            task_id=task_id,
            pack_id=pack_id,
            log_path=self.path,
            records=tuple(
                _log_entry_to_record(entry)
                for row in rows
                if (entry := _row_to_delivery_log_entry(row)) is not None
            ),
        )

    def summarize(self, *, pack: DeliveryPack) -> DeliveryLogSummary:
        fallback = _build_summary_from_entries(pack=pack, entries=self.list_for_pack(pack.pack_id))
        with self._lock, self._connect() as conn:
            counts = {
                str(row["status"]): int(row["count"])
                for row in conn.execute(
                    """
                    SELECT status, COUNT(1) AS count
                    FROM delivery_log
                    WHERE task_id = ?
                      AND pack_id = ?
                    GROUP BY status
                    """,
                    (pack.task_id, pack.pack_id),
                ).fetchall()
            }
            try:
                row = conn.execute(
                    """
                    SELECT
                        status,
                        artifact_count,
                        rendered_count,
                        last_attempt
                    FROM v_delivery_summary
                    WHERE task_id = ?
                      AND pack_id = ?
                    LIMIT 1
                    """,
                    (pack.task_id, pack.pack_id),
                ).fetchone()
            except sqlite3.OperationalError:
                row = None

        if row is None:
            return fallback

        last_attempt = row["last_attempt"]
        return DeliveryLogSummary(
            task_id=pack.task_id,
            pack_id=pack.pack_id,
            pack_status=str(row["status"] or pack.status.value),
            artifact_count=int(row["artifact_count"] or 0),
            rendered_count=int(row["rendered_count"] or 0),
            sent=counts.get("sent", 0),
            blocked=counts.get("blocked", 0),
            duplicate=counts.get("duplicate", 0),
            failed=counts.get("failed", 0),
            dry_run=counts.get("dry_run", 0),
            last_attempt=(
                datetime.fromisoformat(str(last_attempt))
                if last_attempt is not None
                else fallback.last_attempt
            ),
        )

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS delivery_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    pack_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('sent', 'blocked', 'duplicate', 'failed')
                    ),
                    attempted_at TEXT NOT NULL,
                    reason TEXT,
                    receipt_ref TEXT,
                    adapter_name TEXT,
                    idempotency_key TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_delivery_log_pack
                    ON delivery_log(pack_id);
                CREATE INDEX IF NOT EXISTS idx_delivery_log_idempotency
                    ON delivery_log(idempotency_key);
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


class DeliveryPolicyEngine:
    """Evaluates whether one artifact may be sent to one channel."""

    def __init__(
        self,
        *,
        policy_store: JsonDeliveryPolicyStore | None = None,
        default_policy: DeliveryPolicy | None = None,
    ) -> None:
        self._policy_store = policy_store
        self._default_policy = default_policy or DeliveryPolicy()

    def allow(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
        approve_manual_review: bool,
    ) -> tuple[bool, str | None]:
        policy = (
            self._policy_store.resolve(
                tenant=pack.tenant,
                project=pack.global_context.get("project"),
            )
            if self._policy_store is not None
            else self._default_policy
        )
        if not policy.artifact_auto_delivery_enabled:
            return False, "artifact_auto_delivery_disabled"
        if artifact.rendered_uri is None:
            return False, "artifact_not_rendered"
        if channel not in artifact.delivery_channel:
            return False, "channel_not_configured"
        if channel not in _AUDIENCE_ALLOWED_CHANNELS.get(artifact.audience, set()):
            return False, "channel_not_allowed_for_audience"
        if (
            artifact.dispatch_mode == DeliveryDispatchMode.MANUAL_REVIEW
            and not approve_manual_review
        ):
            return False, "manual_review_required"
        if (
            artifact.dispatch_mode == DeliveryDispatchMode.AUTO_WITH_SIGNATURE
            and not pack.signature
        ):
            return False, "signature_required"
        if (
            artifact.audience == AudienceKind.AUDITOR
            and channel != DeliveryChannel.COMPLIANCE_SYSTEM
        ):
            return False, "auditor_channel_restricted"
        return True, None


class DeliveryRouter:
    """Dispatch stakeholder artifacts through policy-gated adapters."""

    def __init__(
        self,
        *,
        adapters: Mapping[DeliveryChannel, ChannelAdapter],
        policy: DeliveryPolicyEngine,
        log: DeliveryDispatchLog,
    ) -> None:
        self._adapters = dict(adapters)
        self._policy = policy
        self._log = log

    def dispatch(
        self,
        *,
        pack: DeliveryPack,
        artifact_ids: set[str] | None = None,
        channels: set[DeliveryChannel] | None = None,
        dry_run: bool = False,
        approve_manual_review: bool = False,
    ) -> DispatchDeliveryResult:
        available_artifact_ids = {artifact.artifact_id for artifact in pack.artifacts}
        if artifact_ids is not None:
            missing_artifacts = sorted(artifact_ids - available_artifact_ids)
            if missing_artifacts:
                raise ValueError(
                    "Unknown delivery artifacts: " + ", ".join(missing_artifacts)
                )

        selected_artifacts = [
            artifact
            for artifact in pack.artifacts
            if artifact_ids is None or artifact.artifact_id in artifact_ids
        ]
        if not selected_artifacts:
            raise ValueError("No delivery artifacts matched the requested filters")

        if channels is not None and not any(
            any(channel in channels for channel in artifact.delivery_channel)
            for artifact in selected_artifacts
        ):
            requested = ", ".join(sorted(channel.value for channel in channels))
            raise ValueError(f"No delivery channels matched the requested filters: {requested}")

        receipts: list[DispatchReceipt] = []
        for artifact in selected_artifacts:
            selected_channels = [
                channel
                for channel in artifact.delivery_channel
                if channels is None or channel in channels
            ]
            for channel in selected_channels:
                receipt = self._dispatch_one(
                    pack=pack,
                    artifact=artifact,
                    channel=channel,
                    dry_run=dry_run,
                    approve_manual_review=approve_manual_review,
                )
                receipts.append(receipt)

        dispatch_status = self._resolve_status(receipts, dry_run=dry_run)
        return DispatchDeliveryResult(
            task_id=pack.task_id,
            pack_id=pack.pack_id,
            dispatch_status=dispatch_status,
            dry_run=dry_run,
            receipts=tuple(receipts),
            log_path=self._log.path,
        )

    def _dispatch_one(
        self,
        *,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        channel: DeliveryChannel,
        dry_run: bool,
        approve_manual_review: bool,
    ) -> DispatchReceipt:
        now = datetime.now(UTC)
        idempotency_key = f"{pack.pack_id}:{artifact.artifact_id}:{channel.value}"

        successful = None if dry_run else self._log.successful_dispatch_for(idempotency_key)
        if successful is not None:
            receipt = DispatchReceipt(
                artifact_id=artifact.artifact_id,
                channel=channel,
                status="duplicate",
                idempotency_key=idempotency_key,
                recorded_at=now,
                reason="idempotent_replay",
                receipt_id=successful.receipt_id,
                adapter_name=successful.adapter_name,
            )
            self._append_log(pack=pack, receipt=receipt)
            return receipt

        allowed, reason = self._policy.allow(
            pack=pack,
            artifact=artifact,
            channel=channel,
            approve_manual_review=approve_manual_review,
        )
        if not allowed:
            receipt = DispatchReceipt(
                artifact_id=artifact.artifact_id,
                channel=channel,
                status="blocked",
                idempotency_key=idempotency_key,
                recorded_at=now,
                reason=reason,
            )
            if not dry_run:
                self._append_log(pack=pack, receipt=receipt)
            return receipt

        if dry_run:
            adapter = self._adapters.get(channel)
            return DispatchReceipt(
                artifact_id=artifact.artifact_id,
                channel=channel,
                status="dry_run",
                idempotency_key=idempotency_key,
                recorded_at=now,
                adapter_name=adapter.name if adapter is not None else None,
            )

        adapter = self._adapters.get(channel)
        if adapter is None:
            receipt = DispatchReceipt(
                artifact_id=artifact.artifact_id,
                channel=channel,
                status="failed",
                idempotency_key=idempotency_key,
                recorded_at=now,
                reason="adapter_unavailable",
            )
            self._append_log(pack=pack, receipt=receipt)
            return receipt

        try:
            receipt_id = adapter.send(pack=pack, artifact=artifact, channel=channel)
        except Exception as exc:  # pragma: no cover - exercised in future adapters
            receipt = DispatchReceipt(
                artifact_id=artifact.artifact_id,
                channel=channel,
                status="failed",
                idempotency_key=idempotency_key,
                recorded_at=now,
                reason=str(exc),
                adapter_name=adapter.name,
            )
            self._append_log(pack=pack, receipt=receipt)
            return receipt

        receipt = DispatchReceipt(
            artifact_id=artifact.artifact_id,
            channel=channel,
            status="sent",
            idempotency_key=idempotency_key,
            recorded_at=now,
            receipt_id=receipt_id,
            adapter_name=adapter.name,
        )
        self._append_log(pack=pack, receipt=receipt)
        return receipt

    def _append_log(self, *, pack: DeliveryPack, receipt: DispatchReceipt) -> None:
        self._log.append(
            DeliveryLogEntry(
                task_id=pack.task_id,
                pack_id=pack.pack_id,
                artifact_id=receipt.artifact_id,
                channel=receipt.channel.value,
                status=receipt.status,
                idempotency_key=receipt.idempotency_key,
                recorded_at=receipt.recorded_at.isoformat(),
                reason=receipt.reason,
                receipt_id=receipt.receipt_id,
                adapter_name=receipt.adapter_name,
            )
        )

    @staticmethod
    def _resolve_status(
        receipts: list[DispatchReceipt],
        *,
        dry_run: bool,
    ) -> Literal["dispatched", "partial", "blocked", "dry_run"]:
        if dry_run:
            return "dry_run"

        success_count = sum(1 for receipt in receipts if receipt.status in {"sent", "duplicate"})
        blocked_or_failed = sum(
            1 for receipt in receipts if receipt.status in {"blocked", "failed"}
        )
        if success_count and not blocked_or_failed:
            return "dispatched"
        if success_count:
            return "partial"
        return "blocked"


def build_default_channel_adapters(
    environment: Mapping[str, str] | None = None,
) -> dict[DeliveryChannel, ChannelAdapter]:
    """Return env-configured real adapters with simulated fallbacks."""

    from ds_agent.infrastructure.delivery.channel_adapters import (
        build_configured_channel_adapters,
    )

    return build_configured_channel_adapters(environment)


def _row_to_delivery_log_entry(row: sqlite3.Row | None) -> DeliveryLogEntry | None:
    if row is None:
        return None
    return DeliveryLogEntry(
        task_id=str(row["task_id"]),
        pack_id=str(row["pack_id"]),
        artifact_id=str(row["artifact_id"]),
        channel=str(row["channel"]),
        status=str(row["status"]),
        idempotency_key=str(row["idempotency_key"]),
        recorded_at=str(row["attempted_at"]),
        reason=str(row["reason"]) if row["reason"] is not None else None,
        receipt_id=str(row["receipt_ref"]) if row["receipt_ref"] is not None else None,
        adapter_name=str(row["adapter_name"]) if row["adapter_name"] is not None else None,
    )


def _log_entry_to_record(entry: DeliveryLogEntry) -> DispatchLogRecord:
    return DispatchLogRecord(
        task_id=entry.task_id,
        pack_id=entry.pack_id,
        artifact_id=entry.artifact_id,
        channel=DeliveryChannel(entry.channel),
        status=cast("Literal['sent', 'blocked', 'duplicate', 'failed', 'dry_run']", entry.status),
        idempotency_key=entry.idempotency_key,
        recorded_at=datetime.fromisoformat(entry.recorded_at),
        reason=entry.reason,
        receipt_id=entry.receipt_id,
        adapter_name=entry.adapter_name,
    )


def _build_summary_from_entries(
    *,
    pack: DeliveryPack,
    entries: list[DeliveryLogEntry],
) -> DeliveryLogSummary:
    counts = _status_counts(entries)
    last_attempt = max(
        (datetime.fromisoformat(entry.recorded_at) for entry in entries),
        default=None,
    )
    return DeliveryLogSummary(
        task_id=pack.task_id,
        pack_id=pack.pack_id,
        pack_status=str(pack.status),
        artifact_count=len(pack.artifacts),
        rendered_count=sum(1 for artifact in pack.artifacts if artifact.rendered_uri),
        sent=counts["sent"],
        blocked=counts["blocked"],
        duplicate=counts["duplicate"],
        failed=counts["failed"],
        dry_run=counts["dry_run"],
        last_attempt=last_attempt,
    )


def _status_counts(entries: list[DeliveryLogEntry]) -> dict[str, int]:
    counts = {
        "sent": 0,
        "blocked": 0,
        "duplicate": 0,
        "failed": 0,
        "dry_run": 0,
    }
    for entry in entries:
        if entry.status in counts:
            counts[entry.status] += 1
    return counts
