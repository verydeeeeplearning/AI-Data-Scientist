"""Port for obtaining eval runs from a task definition."""

from __future__ import annotations

from typing import Protocol

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask


class EvalOrchestrator(Protocol):
    """Provides an eval run for a gold task."""

    def run_task(self, task: GoldTask) -> EvalRun:
        """Execute or load a run for the given task."""

