"""External semantic adapter for Snowflake schema introspection."""

from __future__ import annotations

from typing import Any

from ds_agent.domain.interfaces.warehouse import WarehouseAdapter
from ds_agent.domain.value_objects.connector import ConnectorConfig
from ds_agent.memory.semantic.infrastructure.adapters.warehouse_schema_adapter_base import (
    WarehouseSchemaAdapterBase,
)


class SnowflakeSchemaAdapter(WarehouseSchemaAdapterBase):
    """Sync trusted table metadata from a Snowflake connector."""

    def __init__(
        self,
        connector: ConnectorConfig,
        warehouse_adapter: WarehouseAdapter,
        **kwargs: Any,
    ) -> None:
        super().__init__(connector, warehouse_adapter, **kwargs)

    def _is_system_schema(self, schema_name: str) -> bool:
        return schema_name.casefold() == "information_schema"

    def _grade_rationale(self) -> str:
        return (
            "Auto-seeded from Snowflake metadata. Defaulted to silver until "
            "human audit promotes or downgrades the table."
        )
