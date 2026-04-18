"""Tests for schema_inspect tool."""

from __future__ import annotations

import json

import pytest

from ds_agent.application.services.schema_cache_service import clear_schema_cache
from ds_agent.application.services.warehouse_service import (
    clear_warehouse_adapters,
    set_warehouse_adapter,
)
from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo
from ds_agent.domain.value_objects.connector import CostEstimate, SqlValidationResult


class FakeWarehouseAdapter:
    def __init__(self) -> None:
        self.table_calls = 0
        self.executed_sql: list[str] = []

    def execute_query(self, spec):
        self.executed_sql.append(spec.sql)
        if "LIMIT 5" in spec.sql:
            return [
                {"order_id": 1, "amount": 10.0},
                {"order_id": 2, "amount": 20.0},
            ]
        return []

    def get_schemas(self) -> list[SchemaInfo]:
        return [SchemaInfo(name="analytics"), SchemaInfo(name="public")]

    def get_tables(self, schema: str) -> list[TableInfo]:
        self.table_calls += 1
        if schema == "analytics":
            return [
                TableInfo(
                    name="users",
                    schema="analytics",
                    row_count_estimate=123,
                    description="User dimension",
                ),
                TableInfo(
                    name="orders",
                    schema="analytics",
                    row_count_estimate=456,
                ),
            ]
        return []

    def get_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        if table != "users":
            return []
        return [
            ColumnInfo(name="user_id", data_type="integer", nullable=False),
            ColumnInfo(name="created_at", data_type="timestamp", nullable=False),
            ColumnInfo(name="email", data_type="string", nullable=True),
        ]

    def estimate_cost(self, spec) -> CostEstimate:
        return CostEstimate(estimated_cost_usd=0.1, estimated_rows=10)

    def validate_query(self, sql: str) -> SqlValidationResult:
        return SqlValidationResult(is_safe=True)


@pytest.fixture(autouse=True)
def _reset_warehouse_state() -> None:
    clear_warehouse_adapters()
    clear_schema_cache()
    yield
    clear_warehouse_adapters()
    clear_schema_cache()


class TestSchemaInspectTool:
    @pytest.mark.asyncio
    async def test_list_tables_returns_table_metadata(self) -> None:
        from ds_agent.tools.schema_tools import schema_inspect

        adapter = FakeWarehouseAdapter()
        set_warehouse_adapter("default", adapter)

        result = await schema_inspect(action="list_tables", schema="analytics")
        payload = json.loads(result)

        assert payload["schema"] == "analytics"
        assert payload["count"] == 2
        assert payload["tables"][0]["name"] == "users"
        assert payload["tables"][0]["row_count_estimate"] == 123

    @pytest.mark.asyncio
    async def test_describe_infers_column_meaning(self) -> None:
        from ds_agent.tools.schema_tools import schema_inspect

        set_warehouse_adapter("default", FakeWarehouseAdapter())

        result = await schema_inspect(action="describe", schema="analytics", table="users")
        payload = json.loads(result)

        columns = {column["name"]: column for column in payload["columns"]}
        assert columns["user_id"]["inferred_meaning"] == "identifier"
        assert columns["created_at"]["inferred_meaning"] == "timestamp"
        assert columns["email"]["inferred_meaning"] == "pii"
        assert columns["email"]["is_pii"] is True

    @pytest.mark.asyncio
    async def test_sample_uses_safe_limit(self) -> None:
        from ds_agent.tools.schema_tools import schema_inspect

        adapter = FakeWarehouseAdapter()
        set_warehouse_adapter("default", adapter)

        result = await schema_inspect(
            action="sample",
            schema="analytics",
            table="orders",
            limit=5,
        )
        payload = json.loads(result)

        assert payload["row_count"] == 2
        assert "LIMIT 5" in adapter.executed_sql[-1]
        assert payload["data"][0]["order_id"] == 1

    @pytest.mark.asyncio
    async def test_list_tables_uses_ttl_cache(self) -> None:
        from ds_agent.tools.schema_tools import schema_inspect

        adapter = FakeWarehouseAdapter()
        set_warehouse_adapter("default", adapter)

        first = json.loads(await schema_inspect(action="list_tables", schema="analytics"))
        second = json.loads(await schema_inspect(action="list_tables", schema="analytics"))

        assert first["count"] == second["count"] == 2
        assert adapter.table_calls == 1
