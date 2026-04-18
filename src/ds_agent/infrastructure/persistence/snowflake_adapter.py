"""Snowflake warehouse adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo
from ds_agent.domain.value_objects.connector import ConnectorConfig, CostEstimate, QuerySpec
from ds_agent.infrastructure.persistence.base import BaseWarehouseAdapter


class SnowflakeAdapter(BaseWarehouseAdapter):
    """Snowflake adapter using optional snowflake-connector-python."""

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        connection_factory: Callable[[ConnectorConfig], Any] | None = None,
        dependency_loader: Callable[[str], Any] | None = None,
    ) -> None:
        super().__init__(config, dependency_loader=dependency_loader)
        self._connection_factory = connection_factory

    def _execute_query_impl(self, spec: QuerySpec, *, timeout_seconds: int) -> list[dict]:
        connection = self._open_connection()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(spec.sql)
                return _cursor_to_rows(cursor)
            finally:
                _safe_close(cursor)
        finally:
            _safe_close(connection)

    def _get_schemas_impl(self) -> list[SchemaInfo]:
        rows = self._run_metadata_query("SHOW SCHEMAS")
        return [SchemaInfo(name=str(row.get("name", ""))) for row in rows if row.get("name")]

    def _get_tables_impl(self, schema: str) -> list[TableInfo]:
        rows = self._run_metadata_query(f"SHOW TABLES IN SCHEMA {schema}")
        return [
            TableInfo(
                name=str(row.get("name", "")),
                schema=schema,
                row_count_estimate=_optional_int(row.get("rows")),
            )
            for row in rows
            if row.get("name")
        ]

    def _get_columns_impl(self, schema: str, table: str) -> list[ColumnInfo]:
        rows = self._run_metadata_query(f"DESCRIBE TABLE {schema}.{table}")
        return [
            ColumnInfo(
                name=str(row.get("name", "")),
                data_type=str(row.get("type", "")),
                nullable=str(row.get("null?", "Y")).upper() != "N",
            )
            for row in rows
            if row.get("name")
        ]

    def _estimate_cost_impl(self, spec: QuerySpec) -> CostEstimate:
        return CostEstimate(
            estimated_cost_usd=0.0,
            message="Snowflake cost estimation is not yet implemented.",
        )

    def _run_metadata_query(self, sql: str) -> list[dict]:
        connection = self._open_connection()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(sql)
                return _cursor_to_rows(cursor)
            finally:
                _safe_close(cursor)
        finally:
            _safe_close(connection)

    def _open_connection(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory(self.config)

        connector = self._load_dependency("snowflake.connector")
        kwargs = self._load_json_credentials()
        if kwargs.get("kind") == "password":
            kwargs["password"] = str(kwargs.get("password", "") or "")
        kwargs.pop("kind", None)
        kwargs.setdefault("account", self.config.get_str_option("account", aliases=("host",)))
        kwargs.setdefault("warehouse", self.config.get_str_option("warehouse"))
        kwargs.setdefault("database", self.config.get_str_option("database"))
        kwargs.setdefault("schema", self.config.get_str_option("schema", default="public"))
        username = self.config.get_str_option("username")
        if username:
            kwargs.setdefault("user", username)
        role = self.config.get_str_option("role")
        if role:
            kwargs.setdefault("role", role)
        return connector.connect(**kwargs)


def _cursor_to_rows(cursor: Any) -> list[dict]:
    columns = [str(desc[0]) for desc in getattr(cursor, "description", []) or []]
    rows = cursor.fetchall()
    return [dict(zip(columns, row, strict=False)) for row in rows]


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_close(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()
