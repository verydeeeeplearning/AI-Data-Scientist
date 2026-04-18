"""Temporal leakage scorer."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.scorers.base import build_score


class TemporalLeakageDetectionScorer:
    """Detect simple temporal leakage flags from a run payload."""

    name = "temporal_leakage_detection"
    version = "0.1.0"
    judge_type = JudgeType.DETERMINISTIC

    def score(self, run: EvalRun, task: GoldTask):
        violations = list(run.temporal_violations)
        if run.metadata.get("train_test_not_time_ordered"):
            violations.append("train_test_not_time_ordered")
        value = max(0.0, 1.0 - 0.25 * len(violations))
        return build_score(
            name=self.name,
            value=value,
            rationale=(
                "No temporal leakage signals detected."
                if not violations
                else f"Detected {len(violations)} temporal leakage signal(s)."
            ),
            judge_type=self.judge_type,
            version=self.version,
            sub_scores={"leakage_free": 1.0 if not violations else 0.0},
            evidence_refs=violations,
        )

