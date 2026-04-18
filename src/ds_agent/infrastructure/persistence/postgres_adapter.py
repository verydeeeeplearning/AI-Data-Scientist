"""PostgreSQL warehouse adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo
from ds_agent.domain.value_objects.connector import ConnectorConfig, CostEstimate, QuerySpec
from ds_agent.infrastructure.persistence.base import BaseWarehouseAdapter


class PostgresAdapter(BaseWarehouseAdapter):
    """PostgreSQL adapter using optional psycopg2."""

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
        connection = self._open_connection(timeout_seconds)
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(spec.sql, spec.parameters or None)
                rows = _cursor_to_rows(cursor)
            finally:
                _safe_close(cursor)
            rollback = getattr(connection, "rollback", None)
            if callable(rollback):
                rollback()
            return rows
        finally:
            _safe_close(connection)

    def _get_schemas_impl(self) -> list[SchemaInfo]:
        sql = "SELECT schema_name AS name FROM information_schema.schemata ORDER BY schema_name"
        return [SchemaInfo(name=row["name"]) for row in self._run_metadata_query(sql)]

    def _get_tables_impl(self, schema: str) -> list[TableInfo]:
        sql = (
            "SELECT table_name AS name FROM information_schema.tables "
            "WHERE table_schema = %(schema)s ORDER BY table_name"
        )
        return [
            TableInfo(name=row["name"], schema=schema)
            for row in self._run_metadata_query(sql, {"schema": schema})
        ]

    def _get_columns_impl(self, schema: str, table: str) -> list[ColumnInfo]:
        sql = (
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = %(schema)s AND table_name = %(table)s "
            "ORDER BY ordinal_position"
        )
        rows = self._run_metadata_query(sql, {"schema": schema, "table": table})
        return [
            ColumnInfo(
                name=str(row["column_name"]),
                data_type=str(row["data_type"]),
                nullable=str(row["is_nullable"]).upper() != "NO",
            )
            for row in rows
        ]

    def _estimate_cost_impl(self, spec: QuerySpec) -> CostEstimate:
        return CostEstimate(
            estimated_cost_usd=0.0,
            message="PostgreSQL cost estimation is not yet implemented.",
        )

    def _run_metadata_query(self, sql: str, params: dict[str, object] | None = None) -> list[dict]:
        connection = self._open_connection(self.config.timeout_seconds)
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(sql, params or None)
                rows = _cursor_to_rows(cursor)
            finally:
                _safe_close(cursor)
            rollback = getattr(connection, "rollback", None)
            if callable(rollback):
                rollback()
            return rows
        finally:
            _safe_close(connection)

    def _open_connection(self, timeout_seconds: int) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory(self.config)

        psycopg2 = self._load_dependency("psycopg2")
        raw_credential = self._load_credential_value().strip()
        secret_payload = self._load_secret_payload()

        dsn = ""
        if secret_payload.get("kind") == "dsn" and secret_payload.get("dsn"):
            dsn = str(secret_payload["dsn"])
        elif raw_credential and not secret_payload:
            dsn = raw_credential
        if dsn:
            return psycopg2.connect(dsn=dsn, connect_timeout=timeout_seconds)

        kwargs: dict[str, Any] = {
            "host": self.config.get_str_option("host"),
            "dbname": self.config.get_str_option("database"),
            "connect_timeout": timeout_seconds,
        }
        port = self.config.get_int_option("port")
        if port is not None:
            kwargs["port"] = port
        username = self.config.get_str_option("username")
        if username:
            kwargs["user"] = username
        password = str(secret_payload.get("password", "") or "")
        if password:
            kwargs["password"] = password
        if self.config.get_bool_option("ssl"):
            kwargs["sslmode"] = "require"
        return psycopg2.connect(**kwargs)


def _cursor_to_rows(cursor: Any) -> list[dict]:
    columns = [str(desc[0]) for desc in getattr(cursor, "description", []) or []]
    return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def _safe_close(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()
