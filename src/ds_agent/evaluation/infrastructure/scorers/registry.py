"""Default scorer registry."""

from __future__ import annotations

from collections.abc import Sequence

from ds_agent.evaluation.domain.ports.judge_llm import JudgeLLM
from ds_agent.evaluation.domain.ports.scorer import Scorer
from ds_agent.evaluation.infrastructure.scorers.approval_judgment import ApprovalJudgmentScorer
from ds_agent.evaluation.infrastructure.scorers.artifact_faithfulness import (
    ArtifactFaithfulnessScorer,
)
from ds_agent.evaluation.infrastructure.scorers.exec_summary_accuracy import (
    ExecSummaryAccuracyScorer,
)
from ds_agent.evaluation.infrastructure.scorers.metric_selection_accuracy import (
    MetricSelectionAccuracyScorer,
)
from ds_agent.evaluation.infrastructure.scorers.operator_satisfaction import (
    OperatorSatisfactionScorer,
)
from ds_agent.evaluation.infrastructure.scorers.scoping_accuracy import ScopingAccuracyScorer
from ds_agent.evaluation.infrastructure.scorers.session_completeness import (
    SessionCompletenessScorer,
)
from ds_agent.evaluation.infrastructure.scorers.temporal_leakage_detection import (
    TemporalLeakageDetectionScorer,
)
from ds_agent.evaluation.infrastructure.scorers.time_to_decision import TimeToDecisionScorer
from ds_agent.evaluation.infrastructure.scorers.tool_trajectory import ToolTrajectoryScorer


def build_default_scorers(judge: JudgeLLM | None = None) -> Sequence[Scorer]:
    """Return the default dimension scorer set."""

    return (
        ScopingAccuracyScorer(judge=judge),
        MetricSelectionAccuracyScorer(),
        TemporalLeakageDetectionScorer(),
        ToolTrajectoryScorer(),
        ArtifactFaithfulnessScorer(judge=judge),
        ExecSummaryAccuracyScorer(judge=judge),
        ApprovalJudgmentScorer(),
        SessionCompletenessScorer(),
        OperatorSatisfactionScorer(),
        TimeToDecisionScorer(),
    )

