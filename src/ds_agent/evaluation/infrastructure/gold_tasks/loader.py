"""YAML loader for gold task suites."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.errors.evaluation_errors import GoldTaskValidationError


class GoldTaskLoader:
    """Load one or many gold tasks from disk."""

    def load_file(self, path: str | Path) -> GoldTask:
        resolved = Path(path).expanduser().resolve()
        try:
            payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise GoldTaskValidationError(f"{resolved} must contain a YAML mapping.")
            return GoldTask.model_validate(payload)
        except (OSError, yaml.YAMLError, ValidationError, ValueError) as exc:
            raise GoldTaskValidationError(f"Invalid gold task file {resolved}: {exc}") from exc

    def load_suite(self, root: str | Path, *, domain: str | None = None) -> list[GoldTask]:
        resolved = Path(root).expanduser().resolve()
        tasks = [self.load_file(path) for path in sorted(resolved.rglob("*.yaml"))]
        if domain is None:
            return tasks
        return [task for task in tasks if task.domain == domain]

