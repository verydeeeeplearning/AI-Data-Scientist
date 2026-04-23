"""Filesystem-backed store for operator-promoted result-card artifacts.

Each ``PromotedArtifact`` is persisted as a single JSON file under
``<workspace>/runtime/promoted/<artifact_id>.json``. The store is intentionally
small: it is a write-then-list adapter, not a query engine. The use case layer
treats it via the ``PromotedArtifactStorePort`` Protocol so business code
never imports this module directly.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from ds_agent.domain.entities.run_lineage import (
    PROMOTED_ARTIFACT_AUDIENCES,
    PromotedArtifact,
    PromotedArtifactAudience,
)
from ds_agent.runtime.transcript_store import get_runtime_storage_root


class JsonPromotedArtifactStore:
    """Persist ``PromotedArtifact`` records as one JSON file per artifact."""

    def __init__(
        self,
        workspace_dir: str | None = None,
        *,
        base_dir: str | Path | None = None,
    ) -> None:
        root = Path(base_dir) if base_dir is not None else get_runtime_storage_root(workspace_dir)
        self._dir = root / "promoted"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save_promoted_artifact(
        self,
        *,
        run_id: str,
        card_id: str,
        audience: str,
        title: str,
    ) -> PromotedArtifact:
        run_id_norm = run_id.strip()
        if not run_id_norm:
            raise ValueError("run_id is required")
        card_id_norm = card_id.strip()
        if not card_id_norm:
            raise ValueError("card_id is required")
        audience_norm = audience.strip().lower()
        if audience_norm not in PROMOTED_ARTIFACT_AUDIENCES:
            raise ValueError(
                "audience must be one of: " + ", ".join(PROMOTED_ARTIFACT_AUDIENCES)
            )
        title_norm = title.strip() or card_id_norm
        artifact = PromotedArtifact(
            artifact_id=f"art_{uuid.uuid4().hex[:12]}",
            run_id=run_id_norm,
            card_id=card_id_norm,
            audience=_cast_audience(audience_norm),
            title=title_norm,
            created_at=time.time(),
        )
        path = self._dir / f"{artifact.artifact_id}.json"
        with self._lock:
            path.write_text(
                json.dumps(_serialize(artifact), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return artifact

    def list_promoted_artifacts(
        self,
        run_id: str,
        *,
        card_id: str | None = None,
        limit: int = 50,
    ) -> list[PromotedArtifact]:
        run_id_norm = run_id.strip()
        if not run_id_norm:
            return []
        card_id_norm = card_id.strip() if card_id is not None else None
        if card_id_norm == "":
            card_id_norm = None
        records: list[PromotedArtifact] = []
        with self._lock:
            for path in self._dir.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if not isinstance(payload, dict):
                    continue
                if str(payload.get("run_id", "")) != run_id_norm:
                    continue
                if card_id_norm is not None and str(payload.get("card_id", "")) != card_id_norm:
                    continue
                artifact = _deserialize(payload)
                if artifact is None:
                    continue
                records.append(artifact)
        records.sort(key=lambda item: item.created_at, reverse=True)
        if limit < 0:
            limit = 0
        return records[:limit]


def _cast_audience(value: str) -> PromotedArtifactAudience:
    # Already validated against PROMOTED_ARTIFACT_AUDIENCES.
    if value == "ds":
        return "ds"
    if value == "exec":
        return "exec"
    return "ml"


def _serialize(artifact: PromotedArtifact) -> dict[str, object]:
    return {
        "artifact_id": artifact.artifact_id,
        "run_id": artifact.run_id,
        "card_id": artifact.card_id,
        "audience": artifact.audience,
        "title": artifact.title,
        "created_at": artifact.created_at,
    }


def _deserialize(payload: dict[str, object]) -> PromotedArtifact | None:
    audience_raw = str(payload.get("audience", ""))
    if audience_raw not in PROMOTED_ARTIFACT_AUDIENCES:
        return None
    try:
        created_at_raw = payload.get("created_at", 0.0)
        if not isinstance(created_at_raw, (int, float, str)):
            created_at_raw = 0.0
        return PromotedArtifact(
            artifact_id=str(payload["artifact_id"]),
            run_id=str(payload["run_id"]),
            card_id=str(payload["card_id"]),
            audience=_cast_audience(audience_raw),
            title=str(payload.get("title", "")),
            created_at=float(created_at_raw),
        )
    except (KeyError, TypeError, ValueError):
        return None
