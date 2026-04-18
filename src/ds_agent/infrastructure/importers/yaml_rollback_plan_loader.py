"""YAML-backed rollback-plan loader for Decision OS promotion gates."""

from __future__ import annotations

from pathlib import Path

import yaml

from ds_agent.domain.entities.promotion import RollbackPlan


class YamlRollbackPlanLoader:
    """Load and validate a rollback plan from YAML."""

    def __init__(self, workspace_dir: str | Path | None = None) -> None:
        self._workspace_dir = Path(workspace_dir).resolve() if workspace_dir is not None else None

    def load(self, source: str) -> RollbackPlan:
        path = Path(source).expanduser()
        if not path.is_absolute() and self._workspace_dir is not None:
            path = self._workspace_dir / path
        resolved = path.resolve()
        payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Rollback plan YAML must deserialize to an object.")
        return RollbackPlan.model_validate(payload)
