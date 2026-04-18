"""Analysis type routing for PLAN 17 Phase 6."""

from __future__ import annotations

from typing import ClassVar

from ds_agent.domain.value_objects.analysis_type import AnalysisType


class AnalysisTypeRouter:
    """Route user requests to the right DS workflow template."""

    _ROUTES: ClassVar[list[tuple[tuple[str, ...], AnalysisType]]] = [
        (
            ("forecast", "예측", "다음 달", "다음 분기", "수요", "시계열"),
            AnalysisType(
                type="forecasting",
                required_skills=["backtesting", "uncertainty-quantification"],
                required_guards=["walk-forward", "temporal-join"],
                typical_artifacts=["forecast", "prediction_interval"],
                workflow_template=(
                    "scoping -> data_loading -> profiling -> temporal_eda -> "
                    "backtesting_setup -> modeling -> backtesting -> reporting"
                ),
                workflow_stages=[
                    "scoping",
                    "data_loading",
                    "profiling",
                    "temporal_eda",
                    "backtesting_setup",
                    "modeling",
                    "backtesting",
                    "reporting",
                ],
            ),
        ),
        (
            ("a/b", "ab test", "experiment", "실험", "treatment", "control"),
            AnalysisType(
                type="experimentation",
                required_skills=["backtesting", "hypothesis-ranking"],
                required_guards=["SRM", "multiple-comparison"],
                typical_artifacts=["experiment_report", "decision"],
                workflow_template=(
                    "scoping -> data_loading -> profiling -> experiment_checks -> "
                    "analysis -> reporting"
                ),
                workflow_stages=[
                    "scoping",
                    "data_loading",
                    "profiling",
                    "experiment_checks",
                    "analysis",
                    "reporting",
                ],
            ),
        ),
        (
            ("왜", "원인", "떨어졌", "하락", "drop", "decline"),
            AnalysisType(
                type="diagnosis",
                required_skills=["hypothesis-ranking"],
                required_guards=["cross-check"],
                typical_artifacts=["root_cause_tree", "actions"],
                workflow_template=(
                    "scoping -> data_loading -> profiling -> cohort_analysis -> "
                    "root_cause_analysis -> reporting"
                ),
                workflow_stages=[
                    "scoping",
                    "data_loading",
                    "profiling",
                    "cohort_analysis",
                    "root_cause_analysis",
                    "reporting",
                ],
            ),
        ),
        (
            ("anomaly", "이상", "비정상", "fraud"),
            AnalysisType(
                type="anomaly_detection",
                required_skills=["uncertainty-quantification"],
                required_guards=["false-positive-rate"],
                typical_artifacts=["threshold_policy", "alert_spec"],
                workflow_template=(
                    "scoping -> data_loading -> profiling -> anomaly_eda -> "
                    "thresholding -> evaluation -> reporting"
                ),
                workflow_stages=[
                    "scoping",
                    "data_loading",
                    "profiling",
                    "anomaly_eda",
                    "thresholding",
                    "evaluation",
                    "reporting",
                ],
            ),
        ),
        (
            ("uplift", "인과", "효과", "did", "causal"),
            AnalysisType(
                type="causal_inference",
                required_skills=["causal-assumption-check", "uncertainty-quantification"],
                required_guards=["SUTVA", "overlap"],
                typical_artifacts=["treatment_effect", "caveats"],
                workflow_template=(
                    "scoping -> data_loading -> profiling -> assumption_checks -> "
                    "effect_estimation -> reporting"
                ),
                workflow_stages=[
                    "scoping",
                    "data_loading",
                    "profiling",
                    "assumption_checks",
                    "effect_estimation",
                    "reporting",
                ],
            ),
        ),
        (
            ("segment", "세그먼트", "군집", "cluster"),
            AnalysisType(
                type="segmentation",
                required_skills=["hypothesis-ranking"],
                required_guards=["stability", "actionability"],
                typical_artifacts=["segments", "playbook"],
                workflow_template=(
                    "scoping -> data_loading -> profiling -> feature_space -> "
                    "clustering -> reporting"
                ),
                workflow_stages=[
                    "scoping",
                    "data_loading",
                    "profiling",
                    "feature_space",
                    "clustering",
                    "reporting",
                ],
            ),
        ),
        (
            ("rank", "ranking", "랭킹", "순위"),
            AnalysisType(
                type="ranking",
                required_skills=["hypothesis-ranking"],
                required_guards=["position-bias"],
                typical_artifacts=["ranked_list", "ndcg"],
                workflow_template=(
                    "scoping -> data_loading -> profiling -> relevance_modeling -> "
                    "ranking_eval -> reporting"
                ),
                workflow_stages=[
                    "scoping",
                    "data_loading",
                    "profiling",
                    "relevance_modeling",
                    "ranking_eval",
                    "reporting",
                ],
            ),
        ),
    ]

    def route(self, user_message: str) -> AnalysisType:
        """Classify the request into an analysis type."""
        normalized = user_message.lower()
        for keywords, analysis in self._ROUTES:
            if any(keyword in normalized for keyword in keywords):
                return analysis
        return AnalysisType(
            type="prediction",
            required_skills=["modeling", "evaluation"],
            required_guards=["baseline", "overfitting"],
            typical_artifacts=["model", "model_card"],
            workflow_template=(
                "scoping -> data_loading -> profiling -> eda -> feature_eng -> "
                "modeling -> evaluation -> reporting"
            ),
            workflow_stages=[
                "scoping",
                "data_loading",
                "profiling",
                "eda",
                "feature_eng",
                "modeling",
                "evaluation",
                "reporting",
            ],
        )
