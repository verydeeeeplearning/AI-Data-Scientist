"""Composition root for Decision OS feature-registry services."""

from __future__ import annotations

from dataclasses import dataclass

from ds_agent.application.ports.feature_registry_support import (
    FeatureDefinitionLoader,
    SourceTableCatalog,
)
from ds_agent.application.services.feature_registry_usecases import RegisterFeatureUseCase
from ds_agent.domain.interfaces.feature_registry import FeatureRegistryStore
from ds_agent.infrastructure.importers.yaml_feature_importer import YamlFeatureDefinitionLoader
from ds_agent.infrastructure.persistence.feature_registry_store import SqliteFeatureRegistryStore
from ds_agent.infrastructure.semantic_memory_container import build_semantic_memory_container
from ds_agent.memory.semantic.application.ports import TableTrustRepository


class TableTrustSourceTableCatalog(SourceTableCatalog):
    """Schema-catalog adapter backed by semantic table-trust metadata."""

    def __init__(self, trust_repo: TableTrustRepository) -> None:
        self._trust_repo = trust_repo

    def exists(self, fqtn: str) -> bool:
        return self._trust_repo.get(fqtn) is not None


@dataclass(frozen=True)
class FeatureRegistryContainer:
    """Wired services for Decision OS feature registration."""

    store: FeatureRegistryStore
    loader: FeatureDefinitionLoader
    source_tables: SourceTableCatalog
    register: RegisterFeatureUseCase


def build_feature_registry_container(
    workspace_dir: str | None = None,
    *,
    store: FeatureRegistryStore | None = None,
    loader: FeatureDefinitionLoader | None = None,
    source_tables: SourceTableCatalog | None = None,
) -> FeatureRegistryContainer:
    """Build the feature-registry container for one workspace."""

    resolved_store = store or SqliteFeatureRegistryStore.for_workspace(workspace_dir)
    resolved_loader = loader or YamlFeatureDefinitionLoader()
    resolved_source_tables = source_tables or TableTrustSourceTableCatalog(
        build_semantic_memory_container(workspace_dir).trust
    )
    return FeatureRegistryContainer(
        store=resolved_store,
        loader=resolved_loader,
        source_tables=resolved_source_tables,
        register=RegisterFeatureUseCase(
            resolved_store,
            resolved_loader,
            resolved_source_tables,
        ),
    )
