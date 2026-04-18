"""Shared base implementation for warehouse adapters."""

from __future__ import annotations

import importlib
import json
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from ds_agent.domain.interfaces.warehouse import (
    ColumnInfo,
    SchemaInfo,
    TableInfo,
    WarehouseAdapter,
)
from ds_agent.domain.value_objects.connector import (
    ConnectorConfig,
    CostEstimate,
    QuerySpec,
    SqlValidationResult,
)
from ds_agent.infrastructure.persistence.errors import (
    ConnectorDependencyError,
    ReadOnlyViolationError,
)
from ds_agent.infrastructure.secrets.secret_storage import get_shared_secret_storage
from ds_agent.infrastructure.sql_validator import validate_read_only_sql


class BaseWarehouseAdapter(ABC, WarehouseAdapter):
    """Common read-only enforcement, timeout, and result limiting."""

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        dependency_loader: Callable[[str], Any] | None = None,
    ) -> None:
        self._config = config
        self._dependency_loader = dependency_loader or importlib.import_module

    @property
    def config(self) -> ConnectorConfig:
        return self._config

    def execute_query(self, spec: QuerySpec) -> list[dict]:
        validation = self.validate_query(spec.sql)
        if self._config.read_only and not validation.is_safe:
            reasons = "; ".join(validation.violations)
            raise ReadOnlyViolationError(f"SQL safety violation: {reasons}")

        timeout_seconds = self._resolve_timeout(spec)
        rows = self._execute_query_impl(spec, timeout_seconds=timeout_seconds)
        return self._apply_max_rows(rows)

    def get_schemas(self) -> list[SchemaInfo]:
        return self._get_schemas_impl()

    def get_tables(self, schema: str) -> list[TableInfo]:
        return self._get_tables_impl(schema)

    def get_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        return self._get_columns_impl(schema, table)

    def estimate_cost(self, spec: QuerySpec) -> CostEstimate:
        return self._estimate_cost_impl(spec)

    def validate_query(self, sql: str) -> SqlValidationResult:
        return validate_read_only_sql(sql)

    def _resolve_timeout(self, spec: QuerySpec) -> int:
        requested = spec.timeout_override or self._config.timeout_seconds
        if requested <= 0:
            return self._config.timeout_seconds
        return min(requested, self._config.timeout_seconds)

    def _apply_max_rows(self, rows: list[dict]) -> list[dict]:
        if len(rows) <= self._config.max_rows:
            return rows
        return rows[: self._config.max_rows]

    def _load_dependency(self, module_name: str) -> Any:
        try:
            return self._dependency_loader(module_name)
        except ModuleNotFoundError as exc:
            raise ConnectorDependencyError(
                f"Optional dependency '{module_name}' is not installed."
            ) from exc

    def _load_env_value(self) -> str:
        if not self._config.credential_ref:
            return ""
        return os.getenv(self._config.credential_ref, "")

    def _load_credential_value(self) -> str:
        if not self._config.credential_ref:
            return ""
        if self._config.credential_method.value == "env":
            return self._load_env_value()
        return get_shared_secret_storage().retrieve(self._config.credential_ref) or ""

    def _load_json_credentials(self) -> dict[str, Any]:
        raw = self._load_credential_value().strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _load_secret_payload(self) -> dict[str, Any]:
        payload = self._load_json_credentials()
        return payload if isinstance(payload, dict) else {}

    @abstractmethod
    def _execute_query_impl(self, spec: QuerySpec, *, timeout_seconds: int) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def _get_schemas_impl(self) -> list[SchemaInfo]:
        raise NotImplementedError

    @abstractmethod
    def _get_tables_impl(self, schema: str) -> list[TableInfo]:
        raise NotImplementedError

    @abstractmethod
    def _get_columns_impl(self, schema: str, table: str) -> list[ColumnInfo]:
        raise NotImplementedError

    @abstractmethod
    def _estimate_cost_impl(self, spec: QuerySpec) -> CostEstimate:
        raise NotImplementedError
