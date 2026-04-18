"""Schema and lineage inspection tools for warehouse metadata."""

from __future__ import annotations

import json

from ds_agent.application.services.schema_cache_service import (
    get_schema_cache,
    set_schema_cache,
)
from ds_agent.application.services.warehouse_service import (
    execute_query,
    get_columns,
    get_schemas,
    get_tables,
)
from ds_agent.domain.interfaces.warehouse import ColumnInfo
from ds_agent.domain.value_objects.connector import QuerySpec
from ds_agent.tools.registry import tool

_DEFAULT_SCHEMA_CACHE_TTL_SECONDS = 24 * 60 * 60


@tool(
    name="schema_inspect",
    description=(
        "Inspect warehouse schemas, tables, columns, safe samples, and inferred "
        "column semantics such as timestamps, identifiers, and PII."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list_schemas",
                    "list_tables",
                    "describe",
                    "sample",
                    "relationships",
                ],
                "description": "Inspection action to perform.",
            },
            "connector_name": {
                "type": "string",
                "default": "default",
                "description": "Configured warehouse connector name.",
            },
            "schema": {
                "type": "string",
                "description": "Schema/namespace name.",
            },
            "table": {
                "type": "string",
                "description": "Table name for describe/sample/relationships actions.",
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "description": "Sample row limit for sample action (max 100).",
            },
            "cache_ttl_seconds": {
                "type": "integer",
                "default": _DEFAULT_SCHEMA_CACHE_TTL_SECONDS,
                "description": "TTL for metadata cache entries.",
            },
        },
        "required": ["action"],
    },
    timeout=30,
    prompt=(
        "Inspects warehouse metadata safely.\n"
        "- Use list_schemas or list_tables before querying unknown data sources\n"
        "- Use describe to inspect column types and inferred semantics\n"
        "- Use sample for a safe LIMITed preview"
    ),
)
def schema_inspect(
    action: str,
    connector_name: str = "default",
    schema: str | None = None,
    table: str | None = None,
    limit: int = 5,
    cache_ttl_seconds: int = _DEFAULT_SCHEMA_CACHE_TTL_SECONDS,
) -> str:
    try:
        if action == "list_schemas":
            payload = _list_schemas(connector_name, cache_ttl_seconds=cache_ttl_seconds)
        elif action == "list_tables":
            if not schema:
                return json.dumps({"error": "schema is required for list_tables"})
            payload = _list_tables(
                connector_name,
                schema,
                cache_ttl_seconds=cache_ttl_seconds,
            )
        elif action == "describe":
            if not table:
                return json.dumps({"error": "table is required for describe"})
            payload = _describe_table(
                connector_name,
                schema=schema,
                table=table,
                cache_ttl_seconds=cache_ttl_seconds,
            )
        elif action == "sample":
            if not table:
                return json.dumps({"error": "table is required for sample"})
            payload = _sample_table(
                connector_name,
                schema=schema,
                table=table,
                limit=limit,
            )
        elif action == "relationships":
            if not table:
                return json.dumps({"error": "table is required for relationships"})
            payload = _relationships(
                connector_name,
                schema=schema,
                table=table,
                cache_ttl_seconds=cache_ttl_seconds,
            )
        else:
            return json.dumps({"error": f"Unsupported action: {action}"})
    except Exception as exc:
        return json.dumps({"error": str(exc), "tool": "schema_inspect"})

    return json.dumps(payload, default=str)


def _list_schemas(connector_name: str, *, cache_ttl_seconds: int) -> dict[str, object]:
    cache_key = f"{connector_name}:list_schemas"
    cached = get_schema_cache(cache_key)
    if cached is not None:
        return dict(cached) if isinstance(cached, dict) else {}

    schemas = get_schemas(connector_name)
    payload = {
        "connector_name": connector_name,
        "schemas": [
            {
                "name": schema_info.name,
                "table_count": len(schema_info.tables),
            }
            for schema_info in schemas
        ],
        "count": len(schemas),
    }
    set_schema_cache(cache_key, payload, ttl_seconds=cache_ttl_seconds)
    return payload


def _list_tables(
    connector_name: str,
    schema: str,
    *,
    cache_ttl_seconds: int,
) -> dict[str, object]:
    cache_key = f"{connector_name}:list_tables:{schema}"
    cached = get_schema_cache(cache_key)
    if cached is not None:
        return dict(cached) if isinstance(cached, dict) else {}

    tables = get_tables(schema, connector_name)
    payload = {
        "connector_name": connector_name,
        "schema": schema,
        "tables": [
            {
                "name": table_info.name,
                "schema": table_info.schema,
                "row_count_estimate": table_info.row_count_estimate,
                "description": table_info.description,
            }
            for table_info in tables
        ],
        "count": len(tables),
    }
    set_schema_cache(cache_key, payload, ttl_seconds=cache_ttl_seconds)
    return payload


def _describe_table(
    connector_name: str,
    *,
    schema: str | None,
    table: str,
    cache_ttl_seconds: int,
) -> dict[str, object]:
    resolved_schema = _resolve_schema_for_table(connector_name, schema=schema, table=table)
    cache_key = f"{connector_name}:describe:{resolved_schema}:{table}"
    cached = get_schema_cache(cache_key)
    if cached is not None:
        return dict(cached) if isinstance(cached, dict) else {}

    columns = [_enrich_column(column) for column in get_columns(resolved_schema, table, connector_name)]
    payload = {
        "connector_name": connector_name,
        "schema": resolved_schema,
        "table": table,
        "columns": [_column_to_payload(column) for column in columns],
        "count": len(columns),
    }
    set_schema_cache(cache_key, payload, ttl_seconds=cache_ttl_seconds)
    return payload


def _sample_table(
    connector_name: str,
    *,
    schema: str | None,
    table: str,
    limit: int,
) -> dict[str, object]:
    resolved_schema = _resolve_schema_for_table(connector_name, schema=schema, table=table)
    safe_limit = min(max(limit, 1), 100)
    rows = execute_query(
        QuerySpec(
            sql=f"SELECT * FROM {resolved_schema}.{table} LIMIT {safe_limit}",
            connector_name=connector_name,
        )
    )
    return {
        "connector_name": connector_name,
        "schema": resolved_schema,
        "table": table,
        "limit": safe_limit,
        "row_count": len(rows),
        "data": rows,
    }


def _relationships(
    connector_name: str,
    *,
    schema: str | None,
    table: str,
    cache_ttl_seconds: int,
) -> dict[str, object]:
    description = _describe_table(
        connector_name,
        schema=schema,
        table=table,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    relationships: list[dict[str, str]] = []
    columns_value = description["columns"]
    if not isinstance(columns_value, list):
        return {"connector_name": connector_name, "schema": description["schema"], "table": table, "relationships": [], "count": 0}
    for column in columns_value:
        if not isinstance(column, dict):
            continue
        name = str(column.get("name", ""))
        if name.endswith("_id") and name != "id":
            relationships.append(
                {
                    "column": name,
                    "relationship_type": "foreign_key_candidate",
                    "target_table": f"{name[:-3]}s",
                }
            )
    return {
        "connector_name": connector_name,
        "schema": description["schema"],
        "table": table,
        "relationships": relationships,
        "count": len(relationships),
    }


def _resolve_schema_for_table(
    connector_name: str,
    *,
    schema: str | None,
    table: str,
) -> str:
    if schema:
        return schema
    schemas_payload = _list_schemas(
        connector_name,
        cache_ttl_seconds=_DEFAULT_SCHEMA_CACHE_TTL_SECONDS,
    )
    schemas_value = schemas_payload["schemas"]
    if not isinstance(schemas_value, list):
        return "public"
    for schema_entry in schemas_value:
        if not isinstance(schema_entry, dict):
            continue
        candidate = str(schema_entry.get("name", ""))
        tables_payload = _list_tables(
            connector_name,
            candidate,
            cache_ttl_seconds=_DEFAULT_SCHEMA_CACHE_TTL_SECONDS,
        )
        tables_value = tables_payload["tables"]
        if not isinstance(tables_value, list):
            continue
        for table_entry in tables_value:
            if isinstance(table_entry, dict) and table_entry.get("name") == table:
                return candidate
    return "public"


def _enrich_column(column: ColumnInfo) -> ColumnInfo:
    inferred_meaning = column.inferred_meaning or _infer_column_meaning(column.name, column.data_type)
    is_pii = column.is_pii or inferred_meaning == "pii"
    return ColumnInfo(
        name=column.name,
        data_type=column.data_type,
        nullable=column.nullable,
        description=column.description,
        inferred_meaning=inferred_meaning,
        is_pii=is_pii,
    )


def _infer_column_meaning(column_name: str, data_type: str) -> str:
    name = column_name.lower()
    type_name = data_type.lower()
    if name in {"email", "phone"} or "email" in name or "phone" in name:
        return "pii"
    if name.endswith("_id") or name == "id":
        return "identifier"
    if "timestamp" in type_name or "date" in type_name or any(
        token in name for token in ("created_at", "updated_at", "date", "time", "_ts", "_dt")
    ):
        return "timestamp"
    if any(token in name for token in ("amount", "score", "count", "revenue", "price")):
        return "metric"
    return "dimension"


def _column_to_payload(column: ColumnInfo) -> dict[str, object]:
    return {
        "name": column.name,
        "data_type": column.data_type,
        "nullable": column.nullable,
        "description": column.description,
        "inferred_meaning": column.inferred_meaning,
        "is_pii": column.is_pii,
    }
