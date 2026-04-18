"""JSONL persistence for human rubric reviews."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ds_agent.evaluation.domain.entities.human_rubric import HumanRubricRecord
from ds_agent.runtime.transcript_store import get_runtime_storage_root


class JsonlHumanRubricStore:
    """Append-only JSONL store for human rubric records."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None) -> JsonlHumanRubricStore:
        root = get_runtime_storage_root(workspace_dir)
        return cls(root / "eval-human-rubrics.jsonl")

    def append(self, record: HumanRubricRecord) -> None:
        payload = json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")

    def latest(
        self,
        *,
        session_id: str,
        run_id: str | None = None,
    ) -> HumanRubricRecord | None:
        matches = [
            record
            for record in self.load_all()
            if record.session_id == session_id and (run_id is None or record.run_id == run_id)
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.recorded_at)

    def load_all(self) -> list[HumanRubricRecord]:
        if not self._path.exists():
            return []
        with self._lock:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        return [HumanRubricRecord.model_validate_json(line) for line in lines if line.strip()]
