"""Batch evaluation use case."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from ds_agent.evaluation.application.dtos.eval_report_dto import EvalBatchReport, ScoredRunReport
from ds_agent.evaluation.application.dtos.eval_request_dto import EvalBatchRequest
from ds_agent.evaluation.application.use_cases.score_run import ScoreRun
from ds_agent.evaluation.domain.ports.eval_dataset_store import EvalDatasetStore
from ds_agent.evaluation.domain.ports.eval_orchestrator import EvalOrchestrator
from ds_agent.evaluation.domain.ports.scorer import Scorer


class RunEvalBatch:
    """Run or load a suite of eval runs and score them."""

    def __init__(
        self,
        *,
        orchestrator: EvalOrchestrator,
        scorers: Sequence[Scorer],
        eval_store: EvalDatasetStore | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._score_run = ScoreRun(scorers)
        self._eval_store = eval_store

    def execute(self, request: EvalBatchRequest) -> EvalBatchReport:
        task_reports: list[ScoredRunReport] = []
        dimension_values: dict[str, list[float]] = defaultdict(list)

        for task in request.tasks:
            run = self._orchestrator.run_task(task)
            report = self._score_run.execute(
                run=run,
                task=task,
                scorer_filters=request.scorer_filters,
            )
            task_reports.append(report)
            if self._eval_store is not None:
                self._eval_store.append(report.to_record())
            for name, score in report.scores.items():
                dimension_values[name].append(score.value)

        passed = sum(1 for report in task_reports if report.passed)
        return EvalBatchReport(
            total=len(task_reports),
            passed=passed,
            failed=len(task_reports) - passed,
            per_task_scores={report.task_id: report.weighted_score for report in task_reports},
            per_dimension_means={
                name: sum(values) / len(values) for name, values in dimension_values.items()
            },
            task_reports=tuple(task_reports),
        )

