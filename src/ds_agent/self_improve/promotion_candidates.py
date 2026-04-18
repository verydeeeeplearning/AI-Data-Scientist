"""Persistence for self-improve promotion candidates."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.runtime.transcript_store import get_runtime_storage_root

CandidateStatus = Literal["pending_promotion", "promoted", "blocked"]


class PromotionCandidate(BaseModel):
    """One extracted artifact waiting for evaluation-gated promotion."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(min_length=1)
    candidate_type: Literal["skill"] = "skill"
    status: CandidateStatus = "pending_promotion"
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_project_id: str = Field(min_length=1)
    pending_path: str = Field(min_length=1)
    created_at: float = Field(default_factory=time.time, ge=0.0)
    promoted_path: str | None = None
    gate_summary: str | None = None
    gate_metadata: dict[str, Any] = Field(default_factory=dict)


class JsonPromotionCandidateStore:
    """JSON-backed store for self-improve promotion candidates."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_workspace(cls, workspace_dir: str | None) -> JsonPromotionCandidateStore:
        root = get_runtime_storage_root(workspace_dir) / "self_improve"
        return cls(root / "promotion_candidates.json")

    def register_skill_candidate(
        self,
        *,
        candidate_id: str,
        name: str,
        description: str,
        source_project_id: str,
        pending_path: str | Path,
    ) -> PromotionCandidate:
        candidate = PromotionCandidate(
            candidate_id=candidate_id,
            candidate_type="skill",
            status="pending_promotion",
            name=name,
            description=description,
            source_project_id=source_project_id,
            pending_path=str(Path(pending_path)),
        )
        records = self._load()
        records[candidate_id] = candidate
        self._save(records)
        return candidate

    def get(self, candidate_id: str) -> PromotionCandidate | None:
        return self._load().get(candidate_id)

    def list(self, *, status: CandidateStatus | None = None) -> list[PromotionCandidate]:
        records = list(self._load().values())
        if status is not None:
            records = [record for record in records if record.status == status]
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records

    def mark_promoted(
        self,
        candidate_id: str,
        *,
        promoted_path: str | Path,
        summary: str,
        gate_metadata: dict[str, Any] | None = None,
    ) -> PromotionCandidate:
        return self._update(
            candidate_id,
            status="promoted",
            promoted_path=str(Path(promoted_path)),
            gate_summary=summary,
            gate_metadata=dict(gate_metadata or {}),
        )

    def mark_blocked(
        self,
        candidate_id: str,
        *,
        summary: str,
        gate_metadata: dict[str, Any] | None = None,
    ) -> PromotionCandidate:
        return self._update(
            candidate_id,
            status="blocked",
            gate_summary=summary,
            gate_metadata=dict(gate_metadata or {}),
        )

    def _update(
        self,
        candidate_id: str,
        *,
        status: CandidateStatus,
        promoted_path: str | None = None,
        gate_summary: str | None = None,
        gate_metadata: dict[str, Any] | None = None,
    ) -> PromotionCandidate:
        records = self._load()
        current = records.get(candidate_id)
        if current is None:
            raise KeyError(f"Unknown promotion candidate: {candidate_id}")
        updated = current.model_copy(
            update={
                "status": status,
                "promoted_path": promoted_path,
                "gate_summary": gate_summary,
                "gate_metadata": dict(gate_metadata or {}),
            }
        )
        records[candidate_id] = updated
        self._save(records)
        return updated

    def _load(self) -> dict[str, PromotionCandidate]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return {}
        records: dict[str, PromotionCandidate] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            record = PromotionCandidate.model_validate(item)
            records[record.candidate_id] = record
        return records

    def _save(self, records: dict[str, PromotionCandidate]) -> None:
        payload = [
            record.model_dump(mode="json")
            for record in sorted(records.values(), key=lambda item: item.created_at)
        ]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
