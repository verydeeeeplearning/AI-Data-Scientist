"""JSON persistence for the latest frozen regression baseline."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ds_agent.evaluation.domain.entities.regression_board import RegressionBoardBaseline
from ds_agent.runtime.transcript_store import get_runtime_storage_root


class JsonRegressionBaselineStore:
    """Persist the latest regression baseline as one JSON document."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    @classmethod
    def for_workspace(cls, workspace_dir: str | None) -> JsonRegressionBaselineStore:
        root = get_runtime_storage_root(workspace_dir)
        return cls(root / "evaluation" / "regression_baseline.json")

    @property
    def path(self) -> Path:
        return self._path

    def save(self, baseline: RegressionBoardBaseline) -> None:
        payload = json.dumps(
            baseline.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        with self._lock:
            self._path.write_text(payload, encoding="utf-8")

    def load_latest(self) -> RegressionBoardBaseline | None:
        if not self._path.exists():
            return None
        with self._lock:
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return RegressionBoardBaseline.model_validate(payload)
