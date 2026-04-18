"""Analysis routing tests for PLAN 17 Phase 6."""

from __future__ import annotations

from ds_agent.application.services.analysis_type_router import AnalysisTypeRouter


class TestAnalysisTypeRouter:
    def test_classifies_diagnosis_requests(self):
        router = AnalysisTypeRouter()

        result = router.route("왜 매출이 떨어졌지?")

        assert result.type == "diagnosis"

    def test_classifies_forecasting_requests(self):
        router = AnalysisTypeRouter()

        result = router.route("다음 달 매출 예측해줘")

        assert result.type == "forecasting"
        assert "backtesting" in result.required_skills

    def test_classifies_experiment_requests(self):
        router = AnalysisTypeRouter()

        result = router.route("이 실험 결과 분석해줘")

        assert result.type == "experimentation"
        assert "SRM" in result.required_guards

    def test_builds_workflow_template(self):
        router = AnalysisTypeRouter()

        result = router.route("다음 분기 수요를 forecast 해줘")

        assert "temporal_eda" in result.workflow_stages
        assert result.workflow_template.startswith("scoping")
