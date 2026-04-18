"""Fixture-backed orchestrator for batch scoring."""

from __future__ import annotations

from pathlib import Path

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.errors.evaluation_errors import MissingEvalRunError


class DirectoryEvalOrchestrator:
    """Load one eval run JSON per task id from a directory."""

    def __init__(self, runs_dir: str | Path) -> None:
        self._runs_dir = Path(runs_dir).expanduser().resolve()

    def run_task(self, task: GoldTask) -> EvalRun:
        path = self._runs_dir / f"{task.id}.json"
        if not path.exists():
            raise MissingEvalRunError(f"Missing eval run fixture for {task.id}: {path}")
        return EvalRun.model_validate_json(path.read_text(encoding="utf-8"))

