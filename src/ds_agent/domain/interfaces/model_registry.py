"""Persistence contract for Decision OS model registry."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ds_agent.domain.entities.model import Model, ModelAlias


@runtime_checkable
class ModelRegistryStore(Protocol):
    """Storage contract for registered model versions."""

    def get(self, model_id: str, version: int) -> Model | None: ...

    def get_by_alias(self, alias: ModelAlias) -> Model | None: ...

    def list_from_run(self, run_id: str) -> list[Model]: ...

    def list_models(
        self,
        *,
        alias: ModelAlias | None = None,
        limit: int = 100,
    ) -> list[Model]: ...

    def save(self, model: Model) -> None: ...

    def update_alias(
        self,
        model_id: str,
        version: int,
        alias: ModelAlias,
        *,
        promoted_at: datetime | None = None,
        retired_at: datetime | None = None,
    ) -> None: ...
