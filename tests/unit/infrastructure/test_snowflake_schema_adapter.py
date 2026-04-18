from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo
from ds_agent.domain.value_objects.connector import ConnectorConfig, ConnectorType
from ds_agent.memory.semantic.infrastructure.adapters import SnowflakeSchemaAdapter


class _FakeWarehouseAdapter:
    def get_schemas(self) -> list[SchemaInfo]:
        return [SchemaInfo(name="CURATED"), SchemaInfo(name="INFORMATION_SCHEMA")]

    def get_tables(self, schema: str) -> list[TableInfo]:
        if schema == "CURATED":
            return [TableInfo(name="ORDERS", schema=schema)]
        return []

    def get_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        assert schema == "CURATED"
        assert table == "ORDERS"
        return [
            ColumnInfo(name="ORDER_ID", data_type="NUMBER", nullable=False),
            ColumnInfo(name="PHONE_NUMBER", data_type="VARCHAR", nullable=True),
        ]

    def execute_query(self, spec):
        raise NotImplementedError

    def estimate_cost(self, spec):
        raise NotImplementedError

    def validate_query(self, sql: str):
        raise NotImplementedError


def test_snowflake_schema_adapter_builds_silver_table_trust() -> None:
    connector = ConnectorConfig(
        name="warehouse_sf",
        type=ConnectorType.SNOWFLAKE,
        database="ANALYTICS",
        host="account",
    )
    adapter = SnowflakeSchemaAdapter(
        connector,
        _FakeWarehouseAdapter(),
        owner="finance_analytics",
        include_schemas=["CURATED"],
        clock=lambda: datetime(2026, 4, 16, tzinfo=UTC),
    )

    tables = adapter.fetch_tables(None)

    assert len(tables) == 1
    table = tables[0]
    assert table.fqtn == "ANALYTICS.CURATED.ORDERS"
    assert table.owner == "finance_analytics"
    assert table.grade.value == "silver"
    assert table.columns[0].pii_class == "none"
    assert table.columns[1].pii_class == "low"


def test_snowflake_schema_adapter_filters_information_schema() -> None:
    connector = ConnectorConfig(
        name="warehouse_sf",
        type=ConnectorType.SNOWFLAKE,
        database="ANALYTICS",
        host="account",
        options={"include_schemas": "CURATED,INFORMATION_SCHEMA"},
    )
    adapter = SnowflakeSchemaAdapter(connector, _FakeWarehouseAdapter())

    tables = adapter.fetch_tables(None)

    assert [table.fqtn for table in tables] == ["ANALYTICS.CURATED.ORDERS"]
