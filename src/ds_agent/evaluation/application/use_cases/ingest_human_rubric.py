"""Use case for persisting and scoring human rubric reviews."""

from __future__ import annotations

from collections.abc import Sequence

from ds_agent.evaluation.application.dtos.eval_report_dto import ScoredRunReport
from ds_agent.evaluation.application.use_cases.score_run import ScoreRun
from ds_agent.evaluation.domain.entities.eval_run import EvalArtifact, EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.human_rubric import HumanRubric, HumanRubricRecord
from ds_agent.evaluation.domain.ports.eval_dataset_store import EvalDatasetStore
from ds_agent.evaluation.domain.ports.human_rubric_store import HumanRubricStore
from ds_agent.evaluation.domain.ports.scorer import Scorer
from ds_agent.evaluation.domain.ports.trace_reader import TraceReader


class IngestHumanRubric:
    """Attach a human rubric to a run, score it, and persist the outcome."""

    def __init__(
        self,
        *,
        trace_reader: TraceReader,
        rubric_store: HumanRubricStore,
        scorers: Sequence[Scorer],
        eval_store: EvalDatasetStore | None = None,
    ) -> None:
        self._trace_reader = trace_reader
        self._rubric_store = rubric_store
        self._score_run = ScoreRun(scorers)
        self._eval_store = eval_store

    def execute(
        self,
        *,
        session_id: str,
        rubric: HumanRubric,
        task: GoldTask,
        task_id: str | None = None,
        run_id: str | None = None,
        run: EvalRun | None = None,
    ) -> ScoredRunReport:
        _validate_rubric_dimensions(rubric, task)
        resolved_run = run or self._trace_reader.read_session(
            session_id=session_id,
            task_id=task_id,
            run_id=run_id,
        )
        record = HumanRubricRecord(
            session_id=session_id,
            run_id=resolved_run.run_id,
            task_id=task_id or task.id,
            rubric=rubric,
        )
        self._rubric_store.append(record)
        enriched_run = _apply_human_rubric_record(resolved_run, record)
        report = self._score_run.execute(run=enriched_run, task=task)
        if self._eval_store is not None:
            self._eval_store.append(report.to_record())
        return report


def _validate_rubric_dimensions(rubric: HumanRubric, task: GoldTask) -> None:
    allowed = set(task.scoring_rubric)
    unknown = sorted(name for name in rubric.dimensions if name not in allowed)
    if unknown:
        raise ValueError(f"Unknown rubric dimensions: {', '.join(unknown)}")


def _apply_human_rubric_record(run: EvalRun, record: HumanRubricRecord) -> EvalRun:
    rubric = record.rubric
    metadata = dict(run.metadata)
    metadata["humanRubricReviewerId"] = rubric.reviewer_id
    metadata["humanRubricDimensions"] = dict(rubric.dimensions)
    metadata["humanRubricRecordedAt"] = record.recorded_at
    if rubric.comment:
        metadata["humanRubricComment"] = rubric.comment

    feedback = run.operator_feedback
    human_score = rubric.dimensions.get("operator_satisfaction")
    if human_score is not None:
        feedback = feedback.model_copy(update={"human_score": human_score})

    artifact = EvalArtifact(
        artifact_type="human_rubric",
        content=_render_human_rubric_text(rubric),
        metadata={
            "reviewerId": rubric.reviewer_id,
            "dimensions": dict(rubric.dimensions),
            "comment": rubric.comment,
        },
        evidence_refs=(f"human_rubric:{rubric.reviewer_id}",),
    )
    artifacts = tuple(
        artifact
        for artifact in run.artifacts
        if artifact.artifact_type != "human_rubric"
    )
    return run.model_copy(
        update={
            "operator_feedback": feedback,
            "human_rubric": rubric,
            "metadata": metadata,
            "artifacts": (*artifacts, artifact),
        }
    )


def _render_human_rubric_text(rubric: HumanRubric) -> str:
    lines = [f"reviewer_id: {rubric.reviewer_id}"]
    for name, value in sorted(rubric.dimensions.items()):
        lines.append(f"{name}: {value:.3f}")
    if rubric.comment:
        lines.append(f"comment: {rubric.comment}")
    return "\n".join(lines)
