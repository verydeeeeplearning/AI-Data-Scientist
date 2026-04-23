"""Per-subscription web push health metrics."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from ds_agent.runtime.transcript_store import _SESSION_ID_SAFE_CHARS, get_runtime_storage_root


@dataclass(frozen=True, slots=True)
class WebPushMetricsSummary:
    delivered_count: int
    failed_count: int
    pruned_count: int
    unique_endpoints: int


@dataclass(frozen=True, slots=True)
class _WebPushMetricRecord:
    ts: str
    operator_id: str
    endpoint: str
    kind: str
    ok: bool | None = None
    reason: str | None = None


class JsonWebPushMetricsStore:
    """Append-only JSONL metrics store keyed by operator id."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._dir = root / "web-push-metrics"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record_delivery(self, operator_id: str, endpoint: str, ok: bool) -> None:
        """Append one delivery attempt."""

        self._append_record(
            _WebPushMetricRecord(
                ts=datetime.now(UTC).isoformat(),
                operator_id=operator_id,
                endpoint=endpoint,
                kind="delivery",
                ok=ok,
            )
        )

    def record_prune(self, operator_id: str, endpoint: str, reason: str) -> None:
        """Append one expired-subscription prune event."""

        self._append_record(
            _WebPushMetricRecord(
                ts=datetime.now(UTC).isoformat(),
                operator_id=operator_id,
                endpoint=endpoint,
                kind="prune",
                reason=reason.strip() or "unknown",
            )
        )

    def summary(self, operator_id: str, since: datetime) -> WebPushMetricsSummary:
        """Return a windowed count summary for one operator."""

        since_utc = _coerce_utc(since)
        delivered = 0
        failed = 0
        pruned = 0
        endpoints: set[str] = set()

        for record in self._load_records(operator_id):
            record_ts = _parse_dt(record.get("ts"))
            if record_ts is None or record_ts < since_utc:
                continue
            endpoint = record.get("endpoint")
            if isinstance(endpoint, str) and endpoint:
                endpoints.add(endpoint)
            kind = record.get("kind")
            if kind == "delivery":
                if record.get("ok") is True:
                    delivered += 1
                else:
                    failed += 1
            elif kind == "prune":
                pruned += 1

        return WebPushMetricsSummary(
            delivered_count=delivered,
            failed_count=failed,
            pruned_count=pruned,
            unique_endpoints=len(endpoints),
        )

    def _record_file(self, operator_id: str) -> Path:
        safe_id = _SESSION_ID_SAFE_CHARS.sub("_", operator_id).strip("._-") or "operator"
        digest = hashlib.sha1(operator_id.encode("utf-8")).hexdigest()[:10]
        return self._dir / f"{safe_id}-{digest}.jsonl"

    def _append_record(self, record: _WebPushMetricRecord) -> None:
        with self._lock:
            path = self._record_file(record.operator_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(record), ensure_ascii=False))
                handle.write("\n")

    def _load_records(self, operator_id: str) -> list[dict[str, object]]:
        path = self._record_file(operator_id)
        if not path.exists():
            return []
        try:
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []

        records: list[dict[str, object]] = []
        for line in raw_lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("operator_id") != operator_id:
                continue
            records.append(payload)
        return records


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return _coerce_utc(parsed)


__all__ = [
    "JsonWebPushMetricsStore",
    "WebPushMetricsSummary",
]
