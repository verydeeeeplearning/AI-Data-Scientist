"""External semantic adapter for Databricks Unity Catalog metadata."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast
from urllib.request import Request, urlopen

from ds_agent.memory.semantic.application.ports import ExternalSemanticSource
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery


class UnityCatalogAdapter(ExternalSemanticSource):
    """Fetch trust metadata from a Unity Catalog-compatible endpoint."""

    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: str | None = None,
        auth_scheme: str = "Bearer",
        source_name: str = "unity_catalog",
        owner: str = "unity_catalog",
        timeout_seconds: float = 15.0,
        open_url: Callable[..., Any] | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._auth_token = auth_token
        self._auth_scheme = auth_scheme
        self._owner = owner
        self._timeout_seconds = timeout_seconds
        self._open_url = open_url or urlopen
        self.name = source_name

    def fetch_metrics(self, since: datetime | None) -> list[Metric]:
        del since
        return []

    def fetch_glossary_terms(self, since: datetime | None) -> list[GlossaryTerm]:
        del since
        return []

    def fetch_tables(self, since: datetime | None) -> list[TableTrust]:
        payload = self._request_json()
        tables: list[TableTrust] = []
        for item in _extract_table_nodes(payload):
            updated_at = _parse_datetime(item.get("updated_at") or item.get("updatedAt"))
            if since is not None and updated_at is not None and updated_at < since:
                continue
            tables.append(_build_table_trust(item, owner=self._owner))
        return tables

    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]:
        del since
        return []

    def _request_json(self) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "DS-Agent-SemanticSync/1.0",
        }
        if self._auth_token:
            headers["Authorization"] = f"{self._auth_scheme} {self._auth_token}"

        request = Request(self._endpoint, headers=headers, method="GET")
        with self._open_url(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("unity catalog response must be a JSON object")
        return payload


def _extract_table_nodes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("tables", "data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = value.get("tables")
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    raise ValueError("unity catalog response missing tables collection")


def _build_table_trust(item: dict[str, Any], *, owner: str) -> TableTrust:
    fqtn = _build_fqtn(item)
    metadata = item.get("metadata")
    metadata_dict: dict[str, Any] = metadata if isinstance(metadata, dict) else {}
    tag_map = _normalize_tag_map(item.get("tags") or metadata_dict.get("tags"))
    columns = item.get("columns")
    column_items = columns if isinstance(columns, list) else []
    lineage_complete = bool(
        item.get("lineage_complete")
        or item.get("lineageComplete")
        or metadata_dict.get("lineage_complete")
        or metadata_dict.get("lineageComplete")
    )
    explicit_grade = _resolve_grade(tag_map, item, metadata_dict)
    if explicit_grade is not None:
        grade = explicit_grade
    elif (
        lineage_complete
        and column_items
        and all(_column_has_lineage(column) for column in column_items)
    ):
        grade = "gold"
    elif lineage_complete or any(_column_has_lineage(column) for column in column_items):
        grade = "silver"
    else:
        grade = "bronze"

    refresh = (
        cast(dict[str, Any], item.get("refresh")) if isinstance(item.get("refresh"), dict) else {}
    )
    updated_at = _parse_datetime(item.get("updated_at") or item.get("updatedAt"))
    owner_name = str(item.get("owner") or metadata_dict.get("owner") or owner).strip() or owner
    description = str(
        item.get("comment")
        or item.get("description")
        or metadata_dict.get("description")
        or f"Unity Catalog table {fqtn}."
    ).strip()
    rationale_parts = [f"unity_catalog:{grade}"]
    if lineage_complete:
        rationale_parts.append("lineage_complete")
    if tag_map:
        rationale_parts.append(
            "tags=" + ",".join(f"{key}:{value}" for key, value in sorted(tag_map.items()))
        )

    return TableTrust.model_validate(
        {
            "fqtn": fqtn,
            "grade": grade,
            "owner": owner_name,
            "description": description,
            "refresh": {
                "cadence": str(refresh.get("cadence") or "daily").strip() or "daily",
                "max_staleness_minutes": int(refresh.get("max_staleness_minutes") or 1440),
                "last_refreshed_at": (updated_at.isoformat() if updated_at is not None else None),
            },
            "columns": [
                _build_column(column) for column in column_items if isinstance(column, dict)
            ],
            "approved_joins": [
                join for join in item.get("approved_joins", []) if isinstance(join, dict)
            ],
            "grade_rationale": "; ".join(rationale_parts),
            "last_audited": (
                updated_at.date().isoformat()
                if updated_at is not None
                else datetime.now(UTC).date().isoformat()
            ),
        }
    )


def _build_fqtn(item: dict[str, Any]) -> str:
    explicit = str(item.get("full_name") or item.get("fullName") or "").strip()
    if explicit:
        return explicit
    parts = [
        str(item.get("catalog") or "").strip(),
        str(item.get("schema") or "").strip(),
        str(item.get("name") or item.get("table") or "").strip(),
    ]
    fqtn = ".".join(part for part in parts if part)
    if not fqtn:
        raise ValueError("unity catalog table is missing full_name or catalog/schema/name")
    return fqtn


def _normalize_tag_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = str(key).strip().lower()
        normalized_value = str(item).strip().lower()
        if normalized_key and normalized_value:
            normalized[normalized_key] = normalized_value
    return normalized


def _resolve_grade(
    tags: dict[str, str],
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> str | None:
    for candidate in (
        item.get("grade"),
        item.get("trust_grade"),
        metadata.get("grade"),
        metadata.get("trust_grade"),
        tags.get("trust_grade"),
        tags.get("quality"),
    ):
        normalized = str(candidate or "").strip().lower()
        if normalized in {"gold", "silver", "bronze", "untrusted"}:
            return normalized
    return None


def _column_has_lineage(column: object) -> bool:
    if not isinstance(column, dict):
        return False
    lineage = column.get("lineage_upstream") or column.get("lineageUpstream") or []
    return isinstance(lineage, list) and any(str(item).strip() for item in lineage)


def _build_column(column: dict[str, Any]) -> dict[str, object]:
    pii = str(column.get("pii_class") or column.get("piiClass") or "none").strip().lower()
    if pii not in {"none", "low", "medium", "high"}:
        pii = "none"
    lineage = column.get("lineage_upstream") or column.get("lineageUpstream") or []
    nullable_ratio = column.get("nullable_ratio") or column.get("nullableRatio")
    return {
        "column": str(column.get("name") or column.get("column") or "").strip(),
        "pii_class": pii,
        "lineage_upstream": [str(item).strip() for item in lineage if str(item).strip()],
        "nullable_ratio": float(nullable_ratio) if nullable_ratio is not None else None,
        "data_type": str(column.get("type") or column.get("data_type") or "string").strip()
        or "string",
    }


def _parse_datetime(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
