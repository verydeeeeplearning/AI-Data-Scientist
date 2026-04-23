"""Canonical DS analysis stage IDs shared across harness components."""

from __future__ import annotations

from enum import StrEnum


class AnalysisStage(StrEnum):
    SCOPING = "scoping"
    DATA_LOADING = "data_loading"
    PROFILING = "profiling"
    EDA = "eda"
    FEATURE_ENG = "feature_eng"
    MODELING = "modeling"
    EVALUATION = "evaluation"
    REPORTING = "reporting"


ORDERED_STAGES: tuple[AnalysisStage, ...] = (
    AnalysisStage.SCOPING,
    AnalysisStage.DATA_LOADING,
    AnalysisStage.PROFILING,
    AnalysisStage.EDA,
    AnalysisStage.FEATURE_ENG,
    AnalysisStage.MODELING,
    AnalysisStage.EVALUATION,
    AnalysisStage.REPORTING,
)
