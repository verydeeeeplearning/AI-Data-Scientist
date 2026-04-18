"""Application service for warehouse adapter resolution and execution."""

from __future__ import annotations

from collections.abc import Mapping

from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo, WarehouseAdapter
from ds_agent.domain.value_objects.connector import CostEstimate, QuerySpec

_warehouse_adapters: dict[str, WarehouseAdapter] = {}


def set_warehouse_adapter(name: str, adapter: WarehouseAdapter) -> None:
    """Register or replace a warehouse adapter by connector name."""
    _warehouse_adapters[name] = adapter


def set_warehouse_adapters(adapters: Mapping[str, WarehouseAdapter]) -> None:
    """Replace the full warehouse adapter registry."""
    _warehouse_adapters.clear()
    _warehouse_adapters.update(adapters)


def clear_warehouse_adapters() -> None:
    """Clear the registered warehouse adapters. Intended for tests/bootstrap."""
    _warehouse_adapters.clear()


def get_warehouse_adapter(connector_name: str = "default") -> WarehouseAdapter | None:
    """Return a registered adapter, if present."""
    return _warehouse_adapters.get(connector_name)


def estimate_query_cost(spec: QuerySpec) -> CostEstimate | None:
    """Estimate query cost through the registered adapter, if available."""
    adapter = get_warehouse_adapter(spec.connector_name)
    if adapter is None:
        return None
    return adapter.estimate_cost(spec)


def execute_query(spec: QuerySpec) -> list[dict]:
    """Execute a query through the registered adapter."""
    adapter = get_warehouse_adapter(spec.connector_name)
    if adapter is None:
        raise LookupError(
            f"No warehouse adapter configured for connector '{spec.connector_name}'."
        )
    return adapter.execute_query(spec)


def get_schemas(connector_name: str = "default") -> list[SchemaInfo]:
    """Return schemas from the configured adapter."""
    adapter = get_warehouse_adapter(connector_name)
    if adapter is None:
        raise LookupError(
            f"No warehouse adapter configured for connector '{connector_name}'."
        )
    return adapter.get_schemas()


def get_tables(schema: str, connector_name: str = "default") -> list[TableInfo]:
    """Return tables in a schema from the configured adapter."""
    adapter = get_warehouse_adapter(connector_name)
    if adapter is None:
        raise LookupError(
            f"No warehouse adapter configured for connector '{connector_name}'."
        )
    return adapter.get_tables(schema)


def get_columns(schema: str, table: str, connector_name: str = "default") -> list[ColumnInfo]:
    """Return table columns from the configured adapter."""
    adapter = get_warehouse_adapter(connector_name)
    if adapter is None:
        raise LookupError(
            f"No warehouse adapter configured for connector '{connector_name}'."
        )
    return adapter.get_columns(schema, table)
