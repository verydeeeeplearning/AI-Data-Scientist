"""Evaluation-gated promotion flow for self-improve candidates."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ds_agent.evaluation.application.dtos.eval_report_dto import EvalBatchReport
from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.entities.regression_board import RegressionBoardSnapshot
from ds_agent.evaluation.domain.ports.eval_orchestrator import EvalOrchestrator
from ds_agent.self_improve.promotion_candidates import (
    JsonPromotionCandidateStore,
    PromotionCandidate,
)
from ds_agent.skills.hub import SkillHub

_SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
_BUILTIN_SKILLS_DIR = _SKILLS_ROOT / "builtin"
_SHARED_SKILLS_DIR = _SKILLS_ROOT / "shared"
_DEFAULT_ACTIVE_CUSTOM_SKILLS_DIR = _SKILLS_ROOT / "custom"


class CandidatePromotionDecision(BaseModel):
    """Promotion verdict for one self-improve candidate."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    promoted: bool
    baseline_score: float | None = Field(default=None, ge=0.0, le=1.0)
    candidate_score: float = Field(ge=0.0, le=1.0)
    delta_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    delta_threshold: float = Field(ge=0.0, le=1.0)
    passed_tasks: int = Field(ge=0)
    total_tasks: int = Field(ge=0)
    summary: str = Field(min_length=1)


class CandidateTaggedEvalOrchestrator:
    """Wrap an eval orchestrator and stamp candidate metadata onto each run."""

    def __init__(self, delegate: EvalOrchestrator, *, candidate: PromotionCandidate) -> None:
        self._delegate = delegate
        self._candidate = candidate

    def run_task(self, task: GoldTask) -> EvalRun:
        run = self._delegate.run_task(task)
        metadata = dict(run.metadata)
        metadata["promotionCandidateId"] = self._candidate.candidate_id
        metadata["promotionCandidateType"] = self._candidate.candidate_type
        metadata["promotionCandidateStatus"] = self._candidate.status
        return run.model_copy(update={"metadata": metadata})


class SelfImprovePromotionGate:
    """Apply eval regression rules before promoting one extracted candidate."""

    def __init__(self, candidate_store: JsonPromotionCandidateStore) -> None:
        self._candidate_store = candidate_store

    def get_candidate(self, candidate_id: str) -> PromotionCandidate:
        candidate = self._candidate_store.get(candidate_id)
        if candidate is None:
            raise ValueError(f"Unknown self-improve candidate: {candidate_id}")
        return candidate

    @contextmanager
    def candidate_skill_hub(
        self,
        candidate_id: str,
        *,
        active_custom_dir: str | Path | None = None,
    ) -> Iterator[SkillHub]:
        candidate = self.get_candidate(candidate_id)
        pending_path = Path(candidate.pending_path)
        if not pending_path.exists():
            raise ValueError(f"Candidate markdown is missing: {pending_path}")

        active_dir = (
            Path(active_custom_dir) if active_custom_dir else _DEFAULT_ACTIVE_CUSTOM_SKILLS_DIR
        )
        active_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix=f"ds-agent-candidate-{candidate_id}-") as temp_root:
            temp_custom_dir = Path(temp_root) / "custom"
            temp_custom_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pending_path, temp_custom_dir / pending_path.name)
            yield SkillHub.from_directories(
                [_BUILTIN_SKILLS_DIR, _SHARED_SKILLS_DIR, active_dir, temp_custom_dir]
            )

    def finalize(
        self,
        candidate_id: str,
        *,
        report: EvalBatchReport,
        baseline_snapshot: RegressionBoardSnapshot | None,
        delta_threshold: float = 0.03,
        active_custom_dir: str | Path | None = None,
    ) -> CandidatePromotionDecision:
        candidate = self.get_candidate(candidate_id)
        active_dir = (
            Path(active_custom_dir) if active_custom_dir else _DEFAULT_ACTIVE_CUSTOM_SKILLS_DIR
        )
        active_dir.mkdir(parents=True, exist_ok=True)

        candidate_score = (
            sum(report.per_task_scores.values()) / len(report.per_task_scores)
            if report.per_task_scores
            else 0.0
        )
        baseline_score = self._baseline_score(baseline_snapshot)
        delta_score = None if baseline_score is None else candidate_score - baseline_score
        promoted = report.failed == 0 and (
            delta_score is None or delta_score >= (-1.0 * delta_threshold)
        )

        metadata = {
            "baselineScore": baseline_score,
            "candidateScore": candidate_score,
            "deltaScore": delta_score,
            "deltaThreshold": delta_threshold,
            "passedTasks": report.passed,
            "totalTasks": report.total,
        }
        if promoted:
            promoted_path = active_dir / Path(candidate.pending_path).name
            shutil.copy2(candidate.pending_path, promoted_path)
            summary = self._promoted_summary(
                candidate_score=candidate_score,
                baseline_score=baseline_score,
                delta_score=delta_score,
                threshold=delta_threshold,
            )
            self._candidate_store.mark_promoted(
                candidate_id,
                promoted_path=promoted_path,
                summary=summary,
                gate_metadata=metadata,
            )
            status = "promoted"
        else:
            summary = self._blocked_summary(
                failed_tasks=report.failed,
                candidate_score=candidate_score,
                baseline_score=baseline_score,
                delta_score=delta_score,
                threshold=delta_threshold,
            )
            self._candidate_store.mark_blocked(
                candidate_id,
                summary=summary,
                gate_metadata=metadata,
            )
            status = "blocked"

        return CandidatePromotionDecision(
            candidate_id=candidate_id,
            status=status,
            promoted=promoted,
            baseline_score=baseline_score,
            candidate_score=candidate_score,
            delta_score=delta_score,
            delta_threshold=delta_threshold,
            passed_tasks=report.passed,
            total_tasks=report.total,
            summary=summary,
        )

    @staticmethod
    def _baseline_score(snapshot: RegressionBoardSnapshot | None) -> float | None:
        if snapshot is None:
            return None
        if snapshot.overall.baseline.avg_weighted_score is not None:
            return snapshot.overall.baseline.avg_weighted_score
        return snapshot.overall.recent.avg_weighted_score

    @staticmethod
    def _promoted_summary(
        *,
        candidate_score: float,
        baseline_score: float | None,
        delta_score: float | None,
        threshold: float,
    ) -> str:
        if baseline_score is None or delta_score is None:
            return (
                f"Promoted without historical baseline. Candidate score={candidate_score:.3f}; "
                f"all tasks passed."
            )
        return (
            f"Promoted. Candidate score={candidate_score:.3f}, "
            f"baseline={baseline_score:.3f}, delta={delta_score:+.3f}, "
            f"threshold=-{threshold:.3f}."
        )

    @staticmethod
    def _blocked_summary(
        *,
        failed_tasks: int,
        candidate_score: float,
        baseline_score: float | None,
        delta_score: float | None,
        threshold: float,
    ) -> str:
        if failed_tasks > 0:
            return f"Blocked because {failed_tasks} task(s) failed the suite."
        if baseline_score is not None and delta_score is not None:
            return (
                f"Blocked due to regression. Candidate score={candidate_score:.3f}, "
                f"baseline={baseline_score:.3f}, delta={delta_score:+.3f}, "
                f"threshold=-{threshold:.3f}."
            )
        return "Blocked because the candidate did not satisfy the promotion gate."
