"""Self-improvement module tests."""

from unittest.mock import MagicMock

from ds_agent.self_improve.memory_hints import MemoryHintBuilder
from ds_agent.self_improve.pattern_learner import PatternLearner
from ds_agent.self_improve.post_project import PostProjectLearner, ProjectOutcome


class TestProjectOutcome:
    def test_successful_outcome(self):
        outcome = ProjectOutcome(
            project_id="p1",
            task_type="classification",
            success=True,
            primary_metric="f1",
            primary_metric_value=0.92,
            models_tried=["lightgbm", "xgboost"],
            best_model="lightgbm",
        )
        assert outcome.success
        assert outcome.best_model == "lightgbm"

    def test_failed_outcome(self):
        outcome = ProjectOutcome(
            project_id="p1",
            task_type="regression",
            success=False,
            primary_metric="rmse",
            primary_metric_value=100.0,
        )
        assert not outcome.success


class TestPostProjectLearner:
    def test_learn_from_successful_project(self, tmp_path):
        exp_log = MagicMock()
        code_registry = MagicMock()
        domain_kb = MagicMock()

        learner = PostProjectLearner(
            experiment_log=exp_log,
            code_registry=code_registry,
            domain_kb=domain_kb,
        )

        outcome = ProjectOutcome(
            project_id="p1",
            task_type="classification",
            success=True,
            primary_metric="f1",
            primary_metric_value=0.92,
            best_model="lightgbm",
            domain="healthcare",
            key_findings=["Feature X was most important", "Class imbalance handled with SMOTE"],
        )

        result = learner.learn(outcome)

        assert result["experiments_logged"] >= 1
        # Domain KB must be updated with findings
        assert domain_kb.store_insight.called

    def test_learn_from_failed_project(self, tmp_path):
        learner = PostProjectLearner(
            experiment_log=MagicMock(),
            code_registry=MagicMock(),
            domain_kb=MagicMock(),
        )

        outcome = ProjectOutcome(
            project_id="p2",
            task_type="regression",
            success=False,
            primary_metric="rmse",
            primary_metric_value=999.0,
            failure_reason="Data quality too poor",
        )

        result = learner.learn(outcome)
        assert result is not None


class TestPatternLearner:
    def test_extract_patterns_from_code(self):
        learner = PatternLearner()
        code = """
import pandas as pd
from sklearn.model_selection import train_test_split
from lightgbm import LGBMClassifier

df = pd.read_csv("data.csv")
X = df.drop("target", axis=1)
y = df["target"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratified=True)
model = LGBMClassifier(num_leaves=31)
model.fit(X_train, y_train)
"""
        patterns = learner.extract_patterns(code, task_type="classification")
        assert isinstance(patterns, list)
        # Should detect libraries used
        assert any("lightgbm" in str(p).lower() for p in patterns)

    def test_extract_from_empty_code(self):
        learner = PatternLearner()
        patterns = learner.extract_patterns("", task_type="general")
        assert patterns == []


class TestMemoryHintBuilder:
    def test_build_hints_with_insights(self):
        domain_kb = MagicMock()
        domain_kb.get_memory_hints.return_value = (
            "- [healthcare] HIPAA compliance needed\n"
            "- [healthcare] Use stratified sampling for rare events"
        )

        builder = MemoryHintBuilder(domain_kb=domain_kb)
        hints = builder.build_hints(domain="healthcare")

        assert "HIPAA" in hints
        assert "stratified" in hints

    def test_build_hints_empty(self):
        domain_kb = MagicMock()
        domain_kb.get_memory_hints.return_value = ""

        builder = MemoryHintBuilder(domain_kb=domain_kb)
        hints = builder.build_hints(domain="unknown")
        assert hints == ""

    def test_build_hints_respects_token_budget(self):
        domain_kb = MagicMock()
        domain_kb.get_memory_hints.return_value = "hint " * 1000

        builder = MemoryHintBuilder(domain_kb=domain_kb, max_tokens=100)
        hints = builder.build_hints()
        # Should be truncated
        assert len(hints) <= 100 * 5  # rough char estimate
