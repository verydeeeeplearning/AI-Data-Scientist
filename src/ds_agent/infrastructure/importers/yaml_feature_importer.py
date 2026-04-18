"""YAML-backed feature definition importer."""

from __future__ import annotations

from pathlib import Path

import yaml

from ds_agent.domain.entities.feature import Feature


class YamlFeatureDefinitionLoader:
    """Load a feature definition from a YAML file."""

    def load(self, source: str | Path) -> Feature:
        resolved = Path(source).expanduser().resolve()
        payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Feature YAML must deserialize to an object.")
        return Feature.model_validate(payload)
