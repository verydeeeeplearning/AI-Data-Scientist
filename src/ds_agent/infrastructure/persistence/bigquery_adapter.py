"""BigQuery warehouse adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from ds_agent.domain.interfaces.warehouse import ColumnInfo, SchemaInfo, TableInfo
from ds_agent.domain.value_objects.connector import ConnectorConfig, CostEstimate, QuerySpec
from ds_agent.infrastructure.persistence.base import BaseWarehouseAdapter

_BIGQUERY_COST_PER_TB_USD = 5.0


class BigQueryAdapter(BaseWarehouseAdapter):
    """BigQuery adapter using optional google-cloud-bigquery."""

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        client_factory: Callable[[ConnectorConfig], Any] | None = None,
        dependency_loader: Callable[[str], Any] | None = None,
    ) -> None:
        super().__init__(config, dependency_loader=dependency_loader)
        self._client_factory = client_factory

    def _execute_query_impl(self, spec: QuerySpec, *, timeout_seconds: int) -> list[dict]:
        client = self._get_client()
        query_job = client.query(spec.sql)
        rows = query_job.result(timeout=timeout_seconds)
        return [_row_to_dict(row) for row in rows]

    def _get_schemas_impl(self) -> list[SchemaInfo]:
        client = self._get_client()
        datasets = client.list_datasets(project=self.config.get_str_option("project_id"))
        return [SchemaInfo(name=str(dataset.dataset_id)) for dataset in datasets]

    def _get_tables_impl(self, schema: str) -> list[TableInfo]:
        client = self._get_client()
        dataset_ref = _dataset_ref(client, self.config.get_str_option("project_id"), schema)
        tables = client.list_tables(dataset_ref)
        return [
            TableInfo(
                name=str(table.table_id),
                schema=schema,
            )
            for table in tables
        ]

    def _get_columns_impl(self, schema: str, table: str) -> list[ColumnInfo]:
        client = self._get_client()
        project_id = self.config.get_str_option("project_id")
        table_obj = client.get_table(f"{project_id}.{schema}.{table}")
        return [
            ColumnInfo(
                name=str(field.name),
                data_type=str(field.field_type),
                nullable=str(getattr(field, "mode", "NULLABLE")).upper() != "REQUIRED",
                description=str(getattr(field, "description", "") or ""),
            )
            for field in getattr(table_obj, "schema", [])
        ]

    def _estimate_cost_impl(self, spec: QuerySpec) -> CostEstimate:
        client = self._get_client()
        bigquery = self._load_dependency("google.cloud.bigquery")
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        job = client.query(spec.sql, job_config=job_config)
        bytes_processed = int(getattr(job, "total_bytes_processed", 0) or 0)
        cost_usd = (bytes_processed / 1_000_000_000_000) * _BIGQUERY_COST_PER_TB_USD
        return CostEstimate(
            estimated_bytes=bytes_processed,
            estimated_cost_usd=cost_usd,
            message="Estimated from BigQuery dry-run bytes processed.",
        )

    def _get_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory(self.config)

        bigquery = self._load_dependency("google.cloud.bigquery")
        kwargs: dict[str, Any] = {}
        project_id = self.config.get_str_option("project_id")
        billing_project = self.config.get_str_option("billing_project")
        kwargs["project"] = billing_project or project_id

        location = self.config.get_str_option("location")
        if location:
            kwargs["location"] = location

        credentials = self._build_credentials()
        if credentials is not None:
            kwargs["credentials"] = credentials
        return bigquery.Client(**kwargs)

    def _build_credentials(self) -> Any | None:
        payload = self._load_json_credentials()
        if not payload:
            return None

        kind = str(payload.get("kind", "") or "")
        if kind == "oauth_ref":
            return None

        info: dict[str, Any] | None = None
        if kind == "service_account_json":
            info = _parse_service_account_payload(payload)
        elif _looks_like_service_account_info(payload):
            info = payload

        if info is None:
            return None

        service_account = self._load_dependency("google.oauth2.service_account")
        credentials_cls = getattr(service_account, "Credentials", None)
        if credentials_cls is None:
            raise ValueError("google.oauth2.service_account.Credentials is unavailable")
        return credentials_cls.from_service_account_info(info)


def _row_to_dict(row: Any) -> dict:
    if isinstance(row, dict):
        return row
    items = getattr(row, "items", None)
    if callable(items):
        return dict(items())
    return dict(row)


def _dataset_ref(client: Any, project: str, schema: str) -> Any:
    dataset = getattr(client, "dataset", None)
    if callable(dataset):
        return dataset(schema, project=project)
    return f"{project}.{schema}"


def _parse_service_account_payload(payload: dict[str, Any]) -> dict[str, Any]:
    json_text = payload.get("json")
    if isinstance(json_text, str) and json_text.strip():
        parsed = json.loads(json_text)
        if not isinstance(parsed, dict):
            raise ValueError("BigQuery service account JSON must decode to an object")
        return parsed
    info = payload.get("info")
    if isinstance(info, dict) and info:
        return info
    raise ValueError("BigQuery service account payload requires json or info")


def _looks_like_service_account_info(payload: dict[str, Any]) -> bool:
    return all(key in payload for key in ("client_email", "private_key", "token_uri"))
