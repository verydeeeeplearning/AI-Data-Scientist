from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo
from ds_agent.domain.value_objects.connector import ConnectorConfig, ConnectorType
from ds_agent.memory.semantic.infrastructure.adapters import PostgresSchemaAdapter


class _FakeWarehouseAdapter:
    def get_schemas(self) -> list[SchemaInfo]:
        return [SchemaInfo(name="growth"), SchemaInfo(name="pg_catalog")]

    def get_tables(self, schema: str) -> list[TableInfo]:
        if schema == "growth":
            return [TableInfo(name="subscription", schema="growth")]
        return []

    def get_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        assert schema == "growth"
        assert table == "subscription"
        return [
            ColumnInfo(name="subscriber_id", data_type="uuid", nullable=False),
            ColumnInfo(name="email", data_type="text", nullable=True),
        ]

    def execute_query(self, spec):
        raise NotImplementedError

    def estimate_cost(self, spec):
        raise NotImplementedError

    def validate_query(self, sql: str):
        raise NotImplementedError


def test_postgres_schema_adapter_builds_silver_table_trust() -> None:
    connector = ConnectorConfig(
        name="analytics_prod",
        type=ConnectorType.POSTGRES,
        database="prod",
        host="localhost",
        schema="growth",
    )
    adapter = PostgresSchemaAdapter(
        connector,
        _FakeWarehouseAdapter(),
        owner="data_platform",
        clock=lambda: datetime(2026, 4, 16, tzinfo=UTC),
    )

    tables = adapter.fetch_tables(None)

    assert len(tables) == 1
    table = tables[0]
    assert table.fqtn == "prod.growth.subscription"
    assert table.grade.value == "silver"
    assert table.owner == "data_platform"
    assert table.refresh.cadence == "daily"
    assert table.last_audited.isoformat() == "2026-04-16"
    assert table.columns[0].column == "subscriber_id"
    assert table.columns[0].pii_class == "none"
    assert table.columns[1].column == "email"
    assert table.columns[1].pii_class == "low"


def test_postgres_schema_adapter_respects_include_and_exclude_schema_filters() -> None:
    connector = ConnectorConfig(
        name="analytics_prod",
        type=ConnectorType.POSTGRES,
        database="prod",
        host="localhost",
        options={"include_schemas": "growth,pg_catalog", "schema": "public"},
    )
    adapter = PostgresSchemaAdapter(
        connector,
        _FakeWarehouseAdapter(),
        exclude_schemas=["pg_catalog"],
    )

    tables = adapter.fetch_tables(None)

    assert [table.fqtn for table in tables] == ["prod.growth.subscription"]
