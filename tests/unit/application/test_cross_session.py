"""Cross-session learning tests for PLAN 17 Phase 6."""

from __future__ import annotations

from ds_agent.application.services.cross_session_learner import CrossSessionLearner
from ds_agent.memory.unified_store import UnifiedMemoryStore
from ds_agent.self_improve.post_project import ProjectOutcome


class TestCrossSessionLearner:
    def test_stores_success_patterns_and_recovers_them(self, tmp_path):
        store = UnifiedMemoryStore(str(tmp_path / "memory.db"))
        learner = CrossSessionLearner(memory_store=store)

        learner.learn_from_outcome(
            ProjectOutcome(
                project_id="proj-a",
                task_type="churn_prediction",
                success=True,
                primary_metric="f1",
                primary_metric_value=0.84,
                best_model="lightgbm",
                domain="telecom",
                key_findings=["Top features: tenure, contract_type"],
            )
        )

        context = learner.build_prompt_context("new churn prediction analysis")

        assert "lightgbm" in context.lower()
        assert "tenure" in context.lower()

    def test_surfaces_failure_patterns(self, tmp_path):
        store = UnifiedMemoryStore(str(tmp_path / "memory.db"))
        learner = CrossSessionLearner(memory_store=store)

        learner.learn_from_outcome(
            ProjectOutcome(
                project_id="proj-b",
                task_type="forecasting",
                success=False,
                primary_metric="mape",
                primary_metric_value=0.4,
                domain="finance",
                failure_reason="Random split for time series caused leakage",
            )
        )

        context = learner.build_prompt_context("build a time series forecast for demand")

        assert "avoid" in context.lower()
        assert "random split" in context.lower()
