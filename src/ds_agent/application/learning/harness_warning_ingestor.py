"""Persist harness warnings into the governed learning inbox."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ds_agent.application.learning.submit_learning_proposal import (
    Clock,
    SubmitLearningProposalUseCase,
)
from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
    LearningItemType,
    SourceInfo,
)

_DEFAULT_SEVERITY = "medium"
_VALID_SEVERITIES = {"low", "medium", "high"}


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class NormalizedHarnessWarning:
    warning_id: str
    warning_type: str
    severity: str
    message: str
    suggestion: str | None
    signature: str
    title: str
    content: str
    tags: list[str]
    metadata: dict[str, Any]


class HarnessWarningIngestor:
    """Normalize harness warnings into proposed learning items."""

    def __init__(self, store: LearningStore, clock: Clock | None = None) -> None:
        self._store = store
        self._clock = clock or SystemClock()
        self._submit = SubmitLearningProposalUseCase(store, self._clock)

    def ingest(
        self,
        payload: Mapping[str, Any],
        *,
        session_id: str | None,
        run_id: str | None,
        surface: str,
    ) -> LearningItem | None:
        normalized = normalize_harness_warning(
            payload,
            session_id=session_id,
            run_id=run_id,
            surface=surface,
        )
        if normalized is None:
            return None
        now = self._clock.now()
        existing = self._store.find_by_signature(normalized.signature)
        if existing is not None and existing.status not in {
            LearningItemStatus.ARCHIVED,
            LearningItemStatus.REJECTED,
        }:
            merged_metadata = _merge_warning_metadata(
                existing.metadata,
                normalized.metadata,
                session_id=session_id,
                run_id=run_id,
                surface=surface,
                seen_at=now,
            )
            if merged_metadata == existing.metadata:
                return existing
            updated = existing.model_copy(
                update={
                    "updated_at": now,
                    "metadata": merged_metadata,
                }
            )
            self._store.save_item(updated)
            return updated
        return self._submit.execute(
            item_type=LearningItemType.PATTERN,
            title=normalized.title,
            content=normalized.content,
            signature=normalized.signature,
            source=SourceInfo(
                source_type="manual",
                project_id=session_id,
                session_id=session_id,
                extractor_version="harness_warning_ingestor.v1",
            ),
            tags=normalized.tags,
            scope="project",
            metadata=_build_warning_metadata(
                normalized.metadata,
                session_id=session_id,
                run_id=run_id,
                surface=surface,
                seen_at=now,
            ),
        )


def normalize_harness_warning(
    payload: Mapping[str, Any],
    *,
    session_id: str | None,
    run_id: str | None,
    surface: str,
) -> NormalizedHarnessWarning | None:
    warning_type = str(payload.get("type", "") or "").strip().lower() or "unknown"
    message = str(payload.get("message", "") or "").strip()
    if not message:
        return None
    suggestion = _normalize_optional_text(payload.get("suggestion"))
    severity = str(payload.get("severity", "") or "").strip().lower()
    if severity not in _VALID_SEVERITIES:
        severity = _DEFAULT_SEVERITY
    signature = _signature_for_warning(
        warning_type=warning_type,
        message=message,
        suggestion=suggestion,
    )
    warning_id = _normalize_optional_text(payload.get("id")) or f"hw-{signature[:12]}"
    title = f"Harness warning: {warning_type}"
    content = message if suggestion is None else f"{message}\n\nSuggestion: {suggestion}"
    metadata = {
        "warningId": warning_id,
        "warningType": warning_type,
        "severity": severity,
        "sessionId": session_id,
        "runId": run_id,
        "surface": surface,
        "rawPayload": dict(payload),
        "failureSourceKind": "harness.warning",
        "failureSignalType": warning_type,
        "failureSourceRef": warning_id,
    }
    for key in (
        "failureSourceKind",
        "failureSignalType",
        "failureSourceRef",
        "failureSourceCreatedAt",
        "mismatchKind",
        "sourceRef",
    ):
        normalized_value = _normalize_optional_text(payload.get(key))
        if normalized_value is not None:
            metadata[key] = normalized_value
    return NormalizedHarnessWarning(
        warning_id=warning_id,
        warning_type=warning_type,
        severity=severity,
        message=message,
        suggestion=suggestion,
        signature=signature,
        title=title,
        content=content,
        tags=[
            "harness.warning",
            warning_type,
            f"severity:{severity}",
            f"surface:{surface}",
        ],
        metadata=metadata,
    )


def _signature_for_warning(
    *,
    warning_type: str,
    message: str,
    suggestion: str | None,
) -> str:
    marker = json.dumps(
        {
            "type": warning_type,
            "message": message,
            "suggestion": suggestion,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(marker.encode("utf-8")).hexdigest()


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_warning_metadata(
    metadata: Mapping[str, Any],
    *,
    session_id: str | None,
    run_id: str | None,
    surface: str,
    seen_at: datetime,
) -> dict[str, Any]:
    built = dict(metadata)
    source_ref = _normalize_optional_text(metadata.get("sourceRef"))
    built["recurrenceCount"] = 1
    built["firstSeenAt"] = seen_at.isoformat()
    built["lastSeenAt"] = seen_at.isoformat()
    built["sessionIds"] = _append_unique([], session_id)
    built["runIds"] = _append_unique([], run_id)
    built["surfaces"] = _append_unique([], surface)
    built["sourceRefs"] = _append_unique([], source_ref)
    return built


def _merge_warning_metadata(
    existing: Mapping[str, Any],
    latest: Mapping[str, Any],
    *,
    session_id: str | None,
    run_id: str | None,
    surface: str,
    seen_at: datetime,
) -> dict[str, Any]:
    merged = dict(existing)
    merged.update(dict(latest))
    source_ref = _normalize_optional_text(latest.get("sourceRef"))
    source_refs = _append_unique(existing.get("sourceRefs"), source_ref)
    is_new_source = source_ref is None or _missing_string(existing.get("sourceRefs"), source_ref)
    merged["recurrenceCount"] = _coerce_positive_int(existing.get("recurrenceCount"), default=1) + (
        1 if is_new_source else 0
    )
    merged["firstSeenAt"] = (
        _normalize_optional_text(existing.get("firstSeenAt")) or seen_at.isoformat()
    )
    merged["lastSeenAt"] = (
        seen_at.isoformat()
        if is_new_source
        else _normalize_optional_text(existing.get("lastSeenAt")) or seen_at.isoformat()
    )
    merged["sessionIds"] = _append_unique(existing.get("sessionIds"), session_id)
    merged["runIds"] = _append_unique(existing.get("runIds"), run_id)
    merged["surfaces"] = _append_unique(existing.get("surfaces"), surface)
    merged["sourceRefs"] = source_refs
    return merged


def _append_unique(existing: object, candidate: str | None) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    if isinstance(existing, list):
        for item in existing:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if not normalized:
                continue
            marker = normalized.casefold()
            if marker in seen:
                continue
            seen.add(marker)
            values.append(normalized)
    if isinstance(candidate, str):
        normalized_candidate = candidate.strip()
        if normalized_candidate:
            marker = normalized_candidate.casefold()
            if marker not in seen:
                seen.add(marker)
                values.append(normalized_candidate)
    return values


def _missing_string(existing: object, candidate: str) -> bool:
    normalized_candidate = candidate.strip()
    if not normalized_candidate:
        return False
    existing_values = _append_unique(existing, None)
    return all(value.casefold() != normalized_candidate.casefold() for value in existing_values)


def _coerce_positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)
