"""Persistence contract for Decision OS feature definitions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.feature import Feature, FeatureAlias


@runtime_checkable
class FeatureRegistryStore(Protocol):
    """Storage contract for versioned feature definitions."""

    def get(self, feature_id: str, version: int) -> Feature | None: ...

    def get_latest(self, feature_id: str) -> Feature | None: ...

    def list_versions(self, feature_id: str) -> list[Feature]: ...

    def list_features(
        self,
        *,
        alias: FeatureAlias | None = None,
        limit: int = 100,
    ) -> list[Feature]: ...

    def save(self, feature: Feature) -> None: ...

    def list_experiments_using(self, feature_id: str) -> list[str]: ...

    def list_by_source_table(self, source_table: str) -> list[Feature]: ...
