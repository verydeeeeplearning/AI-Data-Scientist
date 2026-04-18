"""JSON-backed dedupe state for automatic regression-alert dispatches."""

from __future__ import annotations

import json
from pathlib import Path

from ds_agent.evaluation.domain.entities.regression_alert_state import (
    RegressionAlertDispatchState,
)
from ds_agent.runtime.transcript_store import get_runtime_storage_root


class JsonRegressionAlertStateStore:
    """Persist one dispatch fingerprint per regression-alert scope."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_workspace(cls, workspace_dir: str | None) -> JsonRegressionAlertStateStore:
        root = get_runtime_storage_root(workspace_dir) / "evaluation"
        return cls(root / "regression_alert_state.json")

    def get(self, dedupe_key: str) -> RegressionAlertDispatchState | None:
        return self._load().get(dedupe_key)

    def upsert(self, state: RegressionAlertDispatchState) -> RegressionAlertDispatchState:
        states = self._load()
        states[state.dedupe_key] = state
        self._save(states)
        return state

    def clear(self, dedupe_key: str) -> None:
        states = self._load()
        if dedupe_key in states:
            del states[dedupe_key]
            self._save(states)

    def _load(self) -> dict[str, RegressionAlertDispatchState]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return {}
        records: dict[str, RegressionAlertDispatchState] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            record = RegressionAlertDispatchState.model_validate(item)
            records[record.dedupe_key] = record
        return records

    def _save(self, states: dict[str, RegressionAlertDispatchState]) -> None:
        payload = [
            item.model_dump(mode="json")
            for item in sorted(states.values(), key=lambda record: record.dedupe_key)
        ]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
