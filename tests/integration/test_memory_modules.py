"""Integration tests for memory modules."""

import pytest

from ds_agent.memory.code_registry import CodeRegistry
from ds_agent.memory.domain_kb import DomainKB
from ds_agent.memory.experiment_log import ExperimentLog
from ds_agent.memory.project_store import ProjectStore


class TestExperimentLog:
    @pytest.fixture
    def log(self, tmp_path):
        return ExperimentLog(data_dir=str(tmp_path / "exp"))

    def test_log_and_retrieve(self, log):
        exp_id = log.log_experiment(
            project_id="proj-1",
            model_type="lightgbm",
            task_type="binary_classification",
            metrics={"f1": 0.85, "auc": 0.92},
            hyperparameters={"num_leaves": 31},
        )
        assert exp_id is not None

        exps = log.get_experiments(project_id="proj-1")
        assert len(exps) == 1
        assert exps[0]["model_type"] == "lightgbm"
        assert exps[0]["metrics"]["f1"] == 0.85

    def test_filter_by_task_type(self, log):
        log.log_experiment("p1", "rf", "regression", {"rmse": 1.5})
        log.log_experiment("p1", "lgb", "classification", {"f1": 0.9})

        reg = log.get_experiments(task_type="regression")
        assert len(reg) == 1
        assert reg[0]["task_type"] == "regression"

    def test_get_best_experiment(self, log):
        log.log_experiment("p1", "rf", "classification", {"f1": 0.7})
        log.log_experiment("p1", "lgb", "classification", {"f1": 0.9})
        log.log_experiment("p1", "xgb", "classification", {"f1": 0.85})

        best = log.get_best_experiment("p1", "f1", higher_is_better=True)
        assert best is not None
        assert best["model_type"] == "lgb"


class TestCodeRegistry:
    @pytest.fixture
    def registry(self, tmp_path):
        return CodeRegistry(data_dir=str(tmp_path / "code"))

    def test_store_and_retrieve(self, registry):
        registry.store_pattern(
            name="lgb_cv_template",
            code="import lightgbm as lgb\n# ...",
            description="LightGBM cross-validation template",
            tags=["lightgbm", "cv"],
        )
        pattern = registry.get_pattern("lgb_cv_template")
        assert pattern is not None
        assert "lightgbm" in pattern["code"]

    def test_search_patterns(self, registry):
        registry.store_pattern("p1", "code1", "XGBoost template", tags=["xgboost"])
        registry.store_pattern("p2", "code2", "LightGBM template", tags=["lightgbm"])

        results = registry.search_patterns("lightgbm")
        assert len(results) == 1
        assert results[0]["name"] == "p2"

    def test_use_count(self, registry):
        registry.store_pattern("p1", "code", "desc")
        registry.increment_use_count("p1")
        registry.increment_use_count("p1")
        pattern = registry.get_pattern("p1")
        assert pattern["use_count"] == 2


class TestDomainKB:
    @pytest.fixture
    def kb(self, tmp_path):
        return DomainKB(data_dir=str(tmp_path / "kb"))

    def test_store_and_retrieve(self, kb):
        kb.store_insight("healthcare", "HIPAA compliance requires de-identification")
        insights = kb.get_insights(domain="healthcare")
        assert len(insights) == 1
        assert "HIPAA" in insights[0]["content"]

    def test_memory_hints(self, kb):
        kb.store_insight("finance", "Use log returns for financial data")
        kb.store_insight("finance", "Check for autocorrelation in time series")

        hints = kb.get_memory_hints(domain="finance")
        assert "log returns" in hints
        assert "autocorrelation" in hints

    def test_empty_hints(self, kb):
        hints = kb.get_memory_hints(domain="unknown")
        assert hints == ""


class TestProjectStore:
    @pytest.fixture
    def store(self, tmp_path):
        return ProjectStore(data_dir=str(tmp_path / "projects"))

    def test_create_project(self, store):
        pid = store.create_project("Titanic Analysis", task_type="classification")
        assert pid is not None

        project = store.get_project(pid)
        assert project["name"] == "Titanic Analysis"
        assert project["task_type"] == "classification"

    def test_list_projects(self, store):
        store.create_project("Project A")
        store.create_project("Project B")

        projects = store.list_projects()
        assert len(projects) == 2

    def test_register_artifact(self, store):
        pid = store.create_project("Test")
        store.register_artifact(pid, "data_profile", "/path/to/profile.json")

        project = store.get_project(pid)
        assert len(project["artifacts"]) == 1
        assert project["artifacts"][0]["type"] == "data_profile"

    def test_project_directories_created(self, store):
        pid = store.create_project("Test")
        project_dir = store.get_project_dir(pid)
        assert (project_dir / "artifacts").exists()
        assert (project_dir / "plots").exists()
        assert (project_dir / "models").exists()
