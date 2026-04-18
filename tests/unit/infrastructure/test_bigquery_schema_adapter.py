from __future__ import annotations

from datetime import UTC, datetime

from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo
from ds_agent.domain.value_objects.connector import ConnectorConfig, ConnectorType
from ds_agent.memory.semantic.infrastructure.adapters import BigQuerySchemaAdapter


class _FakeWarehouseAdapter:
    def get_schemas(self) -> list[SchemaInfo]:
        return [SchemaInfo(name="analytics"), SchemaInfo(name="INFORMATION_SCHEMA")]

    def get_tables(self, schema: str) -> list[TableInfo]:
        if schema == "analytics":
            return [TableInfo(name="sessions", schema=schema)]
        return []

    def get_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        assert schema == "analytics"
        assert table == "sessions"
        return [
            ColumnInfo(name="session_id", data_type="STRING", nullable=False),
            ColumnInfo(name="user_email", data_type="STRING", nullable=True),
        ]

    def execute_query(self, spec):
        raise NotImplementedError

    def estimate_cost(self, spec):
        raise NotImplementedError

    def validate_query(self, sql: str):
        raise NotImplementedError


def test_bigquery_schema_adapter_builds_silver_table_trust() -> None:
    connector = ConnectorConfig(
        name="warehouse_bq",
        type=ConnectorType.BIGQUERY,
        database="analytics-project",
        options={"project_id": "analytics-project"},
    )
    adapter = BigQuerySchemaAdapter(
        connector,
        _FakeWarehouseAdapter(),
        owner="marketing_analytics",
        include_schemas=["analytics"],
        clock=lambda: datetime(2026, 4, 16, tzinfo=UTC),
    )

    tables = adapter.fetch_tables(None)

    assert len(tables) == 1
    table = tables[0]
    assert table.fqtn == "analytics-project.analytics.sessions"
    assert table.owner == "marketing_analytics"
    assert table.grade.value == "silver"
    assert table.columns[0].pii_class == "none"
    assert table.columns[1].pii_class == "low"


def test_bigquery_schema_adapter_filters_information_schema() -> None:
    connector = ConnectorConfig(
        name="warehouse_bq",
        type=ConnectorType.BIGQUERY,
        database="analytics-project",
        options={
            "project_id": "analytics-project",
            "include_schemas": "analytics,INFORMATION_SCHEMA",
        },
    )
    adapter = BigQuerySchemaAdapter(connector, _FakeWarehouseAdapter())

    tables = adapter.fetch_tables(None)

    assert [table.fqtn for table in tables] == ["analytics-project.analytics.sessions"]
