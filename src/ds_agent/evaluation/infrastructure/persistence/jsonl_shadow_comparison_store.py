"""JSONL store for production-vs-shadow comparison records."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ds_agent.evaluation.domain.entities.shadow_comparison import ShadowComparisonRecord
from ds_agent.runtime.transcript_store import get_runtime_storage_root


class JsonlShadowComparisonStore:
    """Append-only JSONL persistence for shadow comparison records."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None) -> JsonlShadowComparisonStore:
        root = get_runtime_storage_root(workspace_dir)
        return cls(root / "evaluation" / "shadow_comparisons.jsonl")

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: ShadowComparisonRecord) -> None:
        payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")

    def load_all(self) -> list[ShadowComparisonRecord]:
        if not self._path.exists():
            return []
        with self._lock:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        return [ShadowComparisonRecord.model_validate_json(line) for line in lines if line.strip()]

    def latest_for_baseline_run(self, baseline_run_id: str) -> ShadowComparisonRecord | None:
        matches = [
            record for record in self.load_all() if record.baseline_run_id == baseline_run_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

