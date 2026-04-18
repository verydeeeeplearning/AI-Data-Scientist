"""Application service for automatic and explicit lineage capture."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from ds_agent.application.ports.lineage_store_port import LineageStorePort
from ds_agent.domain.entities.lineage import LineageRecord, LineageRecordType


class LineageCaptureService:
    """Capture and query lineage records for datasets, features, models, and decisions."""

    def __init__(self, store: LineageStorePort) -> None:
        self._store = store

    def capture_dataset(
        self,
        path: str,
        schema: list[str] | dict[str, object],
        row_count: int,
        *,
        session_id: str | None = None,
    ) -> LineageRecord:
        resolved = Path(path).expanduser()
        content: dict[str, object] = {
            "path": str(resolved),
            "sha256": _sha256_for_path(resolved),
            "schema": schema,
            "row_count": row_count,
            "exists": resolved.exists(),
        }
        record = LineageRecord(
            record_type=LineageRecordType.DATASET,
            content=content,
            session_id=session_id,
        )
        self._store.save(record)
        return record

    def capture_feature(
        self,
        code: str,
        params: dict[str, object],
        input_data_id: str | None,
        *,
        session_id: str | None = None,
    ) -> LineageRecord:
        record = LineageRecord(
            record_type=LineageRecordType.FEATURE,
            parent_id=input_data_id,
            session_id=session_id,
            content={
                "code": code,
                "params": params,
                "feature_recipe_hash": _sha256_text(code),
                "input_data_id": input_data_id,
            },
        )
        self._store.save(record)
        return record

    def capture_model(
        self,
        hyperparams: dict[str, object],
        seed: int | None,
        env_info: dict[str, object],
        feature_id: str | None,
        *,
        session_id: str | None = None,
        model_type: str | None = None,
        model_path: str | None = None,
    ) -> LineageRecord:
        record = LineageRecord(
            record_type=LineageRecordType.MODEL,
            parent_id=feature_id,
            session_id=session_id,
            content={
                "model_type": model_type,
                "model_path": model_path,
                "hyperparameters": hyperparams,
                "seed": seed,
                "environment": env_info,
                "feature_id": feature_id,
            },
        )
        self._store.save(record)
        return record

    def capture_evaluation(
        self,
        metrics: dict[str, object],
        holdout_data_id: str | None,
        model_id: str | None,
        *,
        session_id: str | None = None,
    ) -> LineageRecord:
        record = LineageRecord(
            record_type=LineageRecordType.EVALUATION,
            parent_id=model_id,
            session_id=session_id,
            content={
                "metrics": metrics,
                "holdout_data_id": holdout_data_id,
                "model_id": model_id,
            },
        )
        self._store.save(record)
        return record

    def capture_decision(
        self,
        what: str,
        why: str,
        alternatives_considered: list[str] | None = None,
        *,
        session_id: str | None = None,
        parent_id: str | None = None,
    ) -> LineageRecord:
        record = LineageRecord(
            record_type=LineageRecordType.DECISION,
            parent_id=parent_id,
            session_id=session_id,
            content={
                "what": what,
                "why": why,
                "alternatives_considered": list(alternatives_considered or []),
            },
        )
        self._store.save(record)
        return record

    def trace(self, record_id: str) -> list[LineageRecord]:
        chain: list[LineageRecord] = []
        current = self._store.get(record_id)
        while current is not None:
            chain.append(current)
            if current.parent_id is None:
                break
            current = self._store.get(current.parent_id)
        chain.reverse()
        return chain

    def latest_for_session(
        self,
        session_id: str,
        *,
        record_type: LineageRecordType | None = None,
    ) -> LineageRecord | None:
        return self._store.latest_for_session(session_id, record_type=record_type)


def _sha256_for_path(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return _sha256_text(str(path))
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def infer_seed_from_code(code: str) -> int | None:
    match = re.search(r"random_state\s*=\s*(\d+)", code)
    if not match:
        return None
    return int(match.group(1))


def current_environment_info() -> dict[str, object]:
    import sys

    return {
        "python": sys.version.split()[0],
        "platform": os.name,
    }


_lineage_service: LineageCaptureService | None = None


def get_lineage_service() -> LineageCaptureService:
    """Return the process-global lineage service.

    The composition root (``ds_agent.agent.factory``) is responsible for
    wiring a concrete :class:`LineageStorePort` adapter via
    :func:`set_lineage_service` before any consumer invokes this accessor.
    """
    global _lineage_service
    if _lineage_service is None:
        raise RuntimeError(
            "Lineage service is not configured. "
            "Call set_lineage_service() at the composition root before use."
        )
    return _lineage_service


def set_lineage_service(service: LineageCaptureService) -> None:
    """Replace the process-global lineage service."""
    global _lineage_service
    _lineage_service = service
