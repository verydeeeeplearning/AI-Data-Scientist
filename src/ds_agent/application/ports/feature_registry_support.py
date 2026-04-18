"""Support ports for Decision OS feature-registry use cases."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.feature import Feature


@runtime_checkable
class FeatureDefinitionLoader(Protocol):
    """Loads feature definitions from external sources such as YAML."""

    def load(self, source: str | Path) -> Feature: ...


@runtime_checkable
class SourceTableCatalog(Protocol):
    """Minimal schema-catalog lookup used by feature registration."""

    def exists(self, fqtn: str) -> bool: ...
