"""External semantic adapter for BigQuery schema introspection."""

from __future__ import annotations

from typing import Any

from ds_agent.domain.interfaces.warehouse import WarehouseAdapter
from ds_agent.domain.value_objects.connector import ConnectorConfig
from ds_agent.memory.semantic.infrastructure.adapters.warehouse_schema_adapter_base import (
    WarehouseSchemaAdapterBase,
)


class BigQuerySchemaAdapter(WarehouseSchemaAdapterBase):
    """Sync trusted table metadata from a BigQuery connector."""

    def __init__(
        self,
        connector: ConnectorConfig,
        warehouse_adapter: WarehouseAdapter,
        **kwargs: Any,
    ) -> None:
        super().__init__(connector, warehouse_adapter, **kwargs)

    def _is_system_schema(self, schema_name: str) -> bool:
        return schema_name.casefold().endswith("information_schema")

    def _grade_rationale(self) -> str:
        return (
            "Auto-seeded from BigQuery dataset metadata. Defaulted to silver until "
            "human audit promotes or downgrades the table."
        )
