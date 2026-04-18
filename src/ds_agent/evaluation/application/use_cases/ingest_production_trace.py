"""Use case for scoring one persisted production session."""

from __future__ import annotations

from collections.abc import Sequence

from ds_agent.evaluation.application.dtos.eval_report_dto import ScoredRunReport
from ds_agent.evaluation.application.use_cases.score_run import ScoreRun
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.ports.eval_dataset_store import EvalDatasetStore
from ds_agent.evaluation.domain.ports.scorer import Scorer
from ds_agent.evaluation.domain.ports.trace_reader import TraceReader


class IngestProductionTrace:
    """Read, score, and optionally persist one production run."""

    def __init__(
        self,
        *,
        trace_reader: TraceReader,
        scorers: Sequence[Scorer],
        eval_store: EvalDatasetStore | None = None,
    ) -> None:
        self._trace_reader = trace_reader
        self._score_run = ScoreRun(scorers)
        self._eval_store = eval_store

    def execute(
        self,
        *,
        session_id: str,
        task: GoldTask,
        task_id: str | None = None,
        run_id: str | None = None,
        run: EvalRun | None = None,
    ) -> ScoredRunReport:
        resolved_run = run or self._trace_reader.read_session(
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
        )
        if resolved_run.mode != "online":
            resolved_run = resolved_run.model_copy(update={"mode": "online"})
        report = self._score_run.execute(run=resolved_run, task=task)
        if self._eval_store is not None:
            self._eval_store.append(report.to_record())
        return report

