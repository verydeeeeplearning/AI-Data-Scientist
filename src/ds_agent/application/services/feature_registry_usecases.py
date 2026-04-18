"""Decision OS feature-registry use cases."""

from __future__ import annotations

from pathlib import Path

from ds_agent.application.dtos.feature_registry import FeatureRegistrationResultDTO
from ds_agent.application.ports.feature_registry_support import (
    FeatureDefinitionLoader,
    SourceTableCatalog,
)
from ds_agent.domain.entities.feature import Feature
from ds_agent.domain.errors.feature_registry_errors import (
    FeatureVersionConflictError,
    UnknownSourceTableError,
)
from ds_agent.domain.interfaces.feature_registry import FeatureRegistryStore


class RegisterFeatureUseCase:
    """Register a YAML-backed feature definition into the feature registry."""

    def __init__(
        self,
        store: FeatureRegistryStore,
        loader: FeatureDefinitionLoader,
        source_table_catalog: SourceTableCatalog,
    ) -> None:
        self._store = store
        self._loader = loader
        self._source_table_catalog = source_table_catalog

    def execute(self, yaml_uri: str | Path) -> FeatureRegistrationResultDTO:
        feature = self._loader.load(yaml_uri)
        missing_tables = [
            table for table in feature.source_tables if not self._source_table_catalog.exists(table)
        ]
        if missing_tables:
            raise UnknownSourceTableError(
                "Unknown source tables: " + ", ".join(sorted(missing_tables))
            )

        if self._store.get(feature.feature_id, feature.version) is not None:
            raise FeatureVersionConflictError(
                f"Feature {feature.feature_id} v{feature.version} already exists."
            )

        latest = self._store.get_latest(feature.feature_id)
        if latest is not None and feature.version < latest.version:
            raise FeatureVersionConflictError(
                f"Feature {feature.feature_id} must advance beyond latest version {latest.version}."
            )

        self._store.save(feature)
        return FeatureRegistrationResultDTO(
            feature_id=feature.feature_id,
            version=feature.version,
            alias=feature.alias,
            validation_warnings=self._build_warnings(feature),
        )

    @staticmethod
    def _build_warnings(feature: Feature) -> list[str]:
        warnings: list[str] = []
        if not feature.point_in_time_safe:
            warnings.append(
                "point_in_time_safe is false; leakage review is required before experiment use."
            )
        if feature.alias == "deprecated":
            warnings.append(
                "alias is deprecated; new experiments should not adopt this feature version."
            )
        return warnings
