"""JSONL dataset store for eval reports."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ds_agent.evaluation.domain.entities.eval_score import EvalDatasetRecord
from ds_agent.runtime.transcript_store import get_runtime_storage_root


class JsonlEvalDatasetStore:
    """Append-only JSONL persistence for evaluation dataset records."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None) -> JsonlEvalDatasetStore:
        root = get_runtime_storage_root(workspace_dir)
        return cls(root / "evaluation" / "dataset_records.jsonl")

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: EvalDatasetRecord) -> None:
        payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")

    def load_all(self) -> list[EvalDatasetRecord]:
        if not self._path.exists():
            return []
        with self._lock:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        return [EvalDatasetRecord.model_validate_json(line) for line in lines if line.strip()]
