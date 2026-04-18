"""Run one shadow agent execution and compare it with a production baseline."""

from __future__ import annotations

from collections.abc import Sequence

from ds_agent.evaluation.application.use_cases.score_run import ScoreRun
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.eval_score import EvalScore
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.shadow_comparison import (
    ShadowComparisonRecord,
    ShadowDimensionComparison,
)
from ds_agent.evaluation.domain.ports.eval_dataset_store import EvalDatasetStore
from ds_agent.evaluation.domain.ports.eval_orchestrator import EvalOrchestrator
from ds_agent.evaluation.domain.ports.scorer import Scorer
from ds_agent.evaluation.domain.ports.shadow_comparison_store import ShadowComparisonStore
from ds_agent.evaluation.domain.ports.trace_reader import TraceReader


class RunShadowComparison:
    """Score one production run, execute its shadow twin, and persist the delta."""

    def __init__(
        self,
        *,
        trace_reader: TraceReader,
        shadow_orchestrator: EvalOrchestrator,
        scorers: Sequence[Scorer],
        comparison_store: ShadowComparisonStore,
        eval_store: EvalDatasetStore | None = None,
        shadow_model: str | None = None,
        shadow_budget_factor: float = 0.5,
    ) -> None:
        self._trace_reader = trace_reader
        self._shadow_orchestrator = shadow_orchestrator
        self._score_run = ScoreRun(scorers)
        self._comparison_store = comparison_store
        self._eval_store = eval_store
        self._shadow_model = shadow_model
        self._shadow_budget_factor = shadow_budget_factor

    def execute(
        self,
        *,
        session_id: str,
        task: GoldTask,
        task_id: str | None = None,
        run_id: str | None = None,
        baseline_run: EvalRun | None = None,
    ) -> ShadowComparisonRecord:
        resolved_baseline = baseline_run or self._trace_reader.read_session(
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
        )
        if resolved_baseline.mode != "online":
            resolved_baseline = resolved_baseline.model_copy(update={"mode": "online"})
        baseline_report = self._score_run.execute(run=resolved_baseline, task=task)

        shadow_run = self._shadow_orchestrator.run_task(task)
        if shadow_run.mode != "shadow":
            shadow_run = shadow_run.model_copy(update={"mode": "shadow"})
        shadow_report = self._score_run.execute(run=shadow_run, task=task)

        record = ShadowComparisonRecord(
            session_id=session_id,
            task_id=task.id,
            baseline_run_id=baseline_report.run_id,
            shadow_run_id=shadow_report.run_id,
            baseline_mode=baseline_report.mode,
            shadow_mode=shadow_report.mode,
            baseline_weighted_score=baseline_report.weighted_score,
            shadow_weighted_score=shadow_report.weighted_score,
            weighted_score_delta=round(
                shadow_report.weighted_score - baseline_report.weighted_score,
                6,
            ),
            baseline_passed=baseline_report.passed,
            shadow_passed=shadow_report.passed,
            baseline_scores=baseline_report.scores,
            shadow_scores=shadow_report.scores,
            dimension_deltas=_build_dimension_deltas(
                baseline_scores=baseline_report.scores,
                shadow_scores=shadow_report.scores,
            ),
            baseline_metadata=dict(baseline_report.run_metadata),
            shadow_metadata=dict(shadow_report.run_metadata),
            baseline_model=_resolve_model_name(baseline_report.run_metadata),
            shadow_model=self._shadow_model or _resolve_model_name(shadow_report.run_metadata),
            shadow_budget_factor=self._shadow_budget_factor,
        )
        self._comparison_store.append(record)

        if self._eval_store is not None:
            self._eval_store.append(
                baseline_report.model_copy(
                    update={
                        "run_metadata": {
                            **baseline_report.run_metadata,
                            "shadowComparisonId": record.comparison_id,
                            "shadowRole": "baseline",
                            "shadowRunId": record.shadow_run_id,
                        }
                    }
                ).to_record()
            )
            self._eval_store.append(
                shadow_report.model_copy(
                    update={
                        "run_metadata": {
                            **shadow_report.run_metadata,
                            "shadowComparisonId": record.comparison_id,
                            "shadowRole": "shadow",
                            "baselineRunId": record.baseline_run_id,
                            "shadowBudgetFactor": record.shadow_budget_factor,
                        }
                    }
                ).to_record()
            )

        return record


def _build_dimension_deltas(
    *,
    baseline_scores: dict[str, EvalScore],
    shadow_scores: dict[str, EvalScore],
) -> tuple[ShadowDimensionComparison, ...]:
    names = sorted(set(baseline_scores) | set(shadow_scores))
    deltas: list[ShadowDimensionComparison] = []
    for name in names:
        baseline = baseline_scores.get(name)
        shadow = shadow_scores.get(name)
        if baseline is None or shadow is None:
            continue
        deltas.append(
            ShadowDimensionComparison(
                name=name,
                baseline_value=baseline.value,
                shadow_value=shadow.value,
                delta=round(shadow.value - baseline.value, 6),
                baseline_rationale=baseline.rationale,
                shadow_rationale=shadow.rationale,
            )
        )
    deltas.sort(key=lambda item: abs(item.delta), reverse=True)
    return tuple(deltas)


def _resolve_model_name(metadata: dict[str, object]) -> str | None:
    raw = metadata.get("model")
    return str(raw) if raw else None
