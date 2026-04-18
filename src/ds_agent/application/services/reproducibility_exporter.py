"""Export experiment records into reproducible scripts or notebooks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ds_agent.application.ports.notebook_engine_port import NotebookEnginePort
from ds_agent.memory.experiment_log import ExperimentLog


class ReproducibilityExporter:
    """Build standalone exports from experiment registry records."""

    def __init__(
        self,
        experiment_log: ExperimentLog,
        notebook_engine: NotebookEnginePort,
    ) -> None:
        self._experiment_log = experiment_log
        self._notebook_engine = notebook_engine

    def export_experiment(
        self,
        exp_id: str,
        format: str = "script",
        output_path: str | None = None,
    ) -> dict[str, object]:
        record = self._experiment_log.get_experiment(exp_id)
        if record is None:
            raise LookupError(f"Experiment not found: {exp_id}")

        content: str | dict[str, object]
        if format == "script":
            content = self._build_script(record)
        elif format == "notebook":
            content = self._build_notebook(record)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        requirements = self._build_requirements(record)
        if output_path is not None:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if format == "script":
                path.write_text(str(content), encoding="utf-8")
            else:
                path.write_text(json.dumps(content, indent=2), encoding="utf-8")

        return {
            "experiment_id": exp_id,
            "format": format,
            "content": content,
            "requirements": requirements,
            "output_path": output_path,
        }

    def _build_script(self, record: dict[str, object]) -> str:
        code = str(record.get("code", "")).strip()
        feature_code = str(record.get("feature_code", "")).strip()
        evaluation_code = str(record.get("evaluation_code", "")).strip()
        data_paths = record.get("data_paths", [])
        if not isinstance(data_paths, list):
            data_paths = []
        metrics = record.get("metrics", {})
        lines = [
            f"# Reproducible experiment export: {record.get('id', 'unknown')}",
            f"# Generated with Python {sys.version.split()[0]}",
            f"DATASET_HASH = {record.get('dataset_hash', '')!r}",
            f"FEATURE_RECIPE_HASH = {record.get('feature_recipe_hash', '')!r}",
            f"SEED = {record.get('seed')!r}",
            f"DATA_PATHS = {data_paths!r}",
            f"EXPECTED_METRICS = {metrics!r}",
            "",
        ]
        if feature_code:
            lines.extend(["# Feature engineering", feature_code, ""])
        if code:
            lines.extend(["# Model training", code, ""])
        if evaluation_code:
            lines.extend(["# Evaluation", evaluation_code, ""])
        if not (feature_code or code or evaluation_code):
            lines.append("print('No code captured for this experiment.')")
        return "\n".join(lines).strip() + "\n"

    def _build_notebook(self, record: dict[str, object]) -> dict[str, object]:
        markdown_blocks = [
            f"# Experiment {record.get('id', 'unknown')}",
            f"- Model: {record.get('model_type', 'unknown')}",
            f"- Dataset hash: `{record.get('dataset_hash', '')}`",
            f"- Decision memo: {record.get('decision_memo', 'n/a')}",
        ]
        code_blocks = [
            block
            for block in [
                str(record.get("feature_code", "")).strip(),
                str(record.get("code", "")).strip(),
                str(record.get("evaluation_code", "")).strip(),
            ]
            if block
        ]
        return self._notebook_engine.build(
            markdown_blocks=markdown_blocks,
            code_blocks=code_blocks,
        )

    @staticmethod
    def _build_requirements(record: dict[str, object]) -> str:
        environment = record.get("environment")
        requirements = []
        if isinstance(environment, dict):
            raw_requirements = environment.get("requirements")
            if isinstance(raw_requirements, list):
                requirements = [str(item) for item in raw_requirements]
        header = f"# python=={sys.version.split()[0]}"
        if not requirements:
            return header + "\n"
        return header + "\n" + "\n".join(requirements) + "\n"
