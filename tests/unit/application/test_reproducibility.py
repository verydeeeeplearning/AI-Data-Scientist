"""Tests for reproducibility exporters."""

from __future__ import annotations

from ds_agent.application.services.reproducibility_exporter import ReproducibilityExporter
from ds_agent.infrastructure.artifact.notebook_engine import NotebookEngine
from ds_agent.memory.experiment_log import ExperimentLog


def _log(tmp_path) -> ExperimentLog:
    return ExperimentLog(data_dir=str(tmp_path / "exp"))


class TestReproducibilityExporter:
    def test_exports_standalone_script(self, tmp_path):
        log = _log(tmp_path)
        exp_id = log.log_experiment(
            project_id="proj-1",
            model_type="lightgbm",
            task_type="classification",
            metrics={"f1": 0.82},
            dataset_hash="data-hash",
            feature_recipe_hash="feature-hash",
            code="print('train')",
            feature_code="print('features')",
            evaluation_code="print('eval')",
            data_paths=["data/train.csv"],
            seed=42,
        )

        exporter = ReproducibilityExporter(log, NotebookEngine())
        payload = exporter.export_experiment(exp_id, format="script")

        script = payload["content"]
        assert "DATASET_HASH = 'data-hash'" in script
        assert "DATA_PATHS = ['data/train.csv']" in script
        assert "print('features')" in script
        assert "print('train')" in script
        assert "print('eval')" in script

    def test_exports_notebook_and_requirements(self, tmp_path):
        log = _log(tmp_path)
        exp_id = log.log_experiment(
            project_id="proj-1",
            model_type="lightgbm",
            task_type="classification",
            metrics={"f1": 0.82},
            decision_memo="Use LightGBM",
            environment={"requirements": ["pandas==2.2.0", "scikit-learn==1.5.0"]},
            code="print('train')",
        )

        exporter = ReproducibilityExporter(log, NotebookEngine())
        payload = exporter.export_experiment(exp_id, format="notebook")

        notebook = payload["content"]
        requirements = payload["requirements"]
        assert notebook["nbformat"] == 4
        assert notebook["cells"][0]["cell_type"] == "markdown"
        assert "pandas==2.2.0" in requirements
