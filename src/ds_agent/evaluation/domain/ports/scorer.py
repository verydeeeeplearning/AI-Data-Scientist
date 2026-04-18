"""Scorer port contract."""

from __future__ import annotations

from typing import Protocol

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.eval_score import EvalScore
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType


class Scorer(Protocol):
    """Port implemented by all eval scorers."""

    name: str
    version: str
    judge_type: JudgeType

    def score(self, run: EvalRun, task: GoldTask) -> EvalScore:
        """Return a normalized score for one task/run pair."""

