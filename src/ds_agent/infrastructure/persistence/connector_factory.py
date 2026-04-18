"""Factory for concrete warehouse adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ds_agent.domain.interfaces.warehouse import WarehouseAdapter
from ds_agent.domain.value_objects.connector import ConnectorConfig, ConnectorType
from ds_agent.infrastructure.persistence.bigquery_adapter import BigQueryAdapter
from ds_agent.infrastructure.persistence.postgres_adapter import PostgresAdapter
from ds_agent.infrastructure.persistence.snowflake_adapter import SnowflakeAdapter


def create_connector_adapter(
    config: ConnectorConfig,
    **kwargs: Any,
) -> WarehouseAdapter:
    """Create one concrete warehouse adapter from config."""
    if config.type == ConnectorType.SNOWFLAKE:
        return SnowflakeAdapter(config, **kwargs)
    if config.type == ConnectorType.BIGQUERY:
        return BigQueryAdapter(config, **kwargs)
    if config.type == ConnectorType.POSTGRES:
        return PostgresAdapter(config, **kwargs)
    raise ValueError(f"Unsupported connector type: {config.type}")


def create_connector_adapters(
    configs: Mapping[str, ConnectorConfig],
) -> dict[str, WarehouseAdapter]:
    """Create a named adapter mapping from connector configs."""
    return {
        name: create_connector_adapter(config)
        for name, config in configs.items()
    }
