"""External semantic adapter for dbt Semantic Layer / MetricFlow."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.request import Request, urlopen

from ds_agent.memory.semantic.application.ports import ExternalSemanticSource
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery

_METRICFLOW_QUERY = """
query SemanticMetrics {
  metrics {
    name
    label
    description
    type
    filter
    aggregation
    semanticModel
    model
    updatedAt
    dimensions
    metadata
    typeParams
    relatedMetrics
  }
}
""".strip()


class DbtMetricFlowAdapter(ExternalSemanticSource):
    """Fetch semantic metrics from a dbt Semantic Layer GraphQL endpoint."""

    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: str | None = None,
        auth_scheme: str = "Bearer",
        source_name: str = "dbt_metricflow",
        owner: str = "dbt_metricflow",
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
        payload = self._graphql(_METRICFLOW_QUERY)
        metrics: list[Metric] = []
        for item in _extract_metric_nodes(payload):
            updated_at = _parse_datetime(item.get("updatedAt") or item.get("updated_at"))
            if since is not None and updated_at is not None and updated_at < since:
                continue
            metrics.append(_build_metric(item, owner=self._owner))
        return metrics

    def fetch_glossary_terms(self, since: datetime | None) -> list[GlossaryTerm]:
        del since
        return []

    def fetch_tables(self, since: datetime | None) -> list[TableTrust]:
        del since
        return []

    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]:
        del since
        return []

    def _graphql(
        self,
        query: str,
        *,
        variables: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(
            {
                "query": query,
                "variables": variables or {},
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "DS-Agent-SemanticSync/1.0",
        }
        if self._auth_token:
            headers["Authorization"] = f"{self._auth_scheme} {self._auth_token}"

        request = Request(self._endpoint, headers=headers, data=body, method="POST")
        with self._open_url(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("dbt semantic layer response must be a JSON object")
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            raise ValueError(f"dbt semantic layer returned errors: {errors}")
        return payload


def _extract_metric_nodes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("dbt semantic layer response missing data payload")

    for candidate in (data, data.get("semanticLayer"), data.get("semantic_layer")):
        if not isinstance(candidate, dict):
            continue
        for key in ("metrics", "metricDefinitions", "metric_definitions"):
            value = candidate.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("dbt semantic layer response missing metrics collection")


def _build_metric(item: dict[str, Any], *, owner: str) -> Metric:
    metric_id = str(item.get("name") or "").strip()
    if not metric_id:
        raise ValueError("dbt metric is missing a name")

    label = str(item.get("label") or "").strip()
    display_name = label or metric_id.replace("_", " ").title()
    description = str(item.get("description") or "").strip()
    metric_type = str(item.get("type") or "").strip().casefold()
    metadata = item.get("metadata")
    metadata_dict: dict[str, Any] = metadata if isinstance(metadata, dict) else {}
    related_metrics = _normalize_str_list(item.get("relatedMetrics") or item.get("related_metrics"))
    dimensions = _normalize_str_list(item.get("dimensions"))
    raw_type_params = item.get("typeParams")
    type_params: dict[str, Any] = raw_type_params if isinstance(raw_type_params, dict) else {}
    semantic_model = str(
        item.get("semanticModel")
        or item.get("semantic_model")
        or item.get("model")
        or metadata_dict.get("model")
        or "dbt_metricflow"
    ).strip()
    filter_clause = str(item.get("filter") or type_params.get("filter") or "1=1").strip()
    aggregation = str(item.get("aggregation") or metric_type or "measure").strip()
    owner_name = str(metadata_dict.get("owner") or owner).strip() or owner
    caveats = _normalize_str_list(metadata_dict.get("caveats"))
    if dimensions:
        caveats.append("Available dimensions: " + ", ".join(dimensions))

    updated_at = _parse_datetime(item.get("updatedAt") or item.get("updated_at"))
    return Metric.model_validate(
        {
            "metric_id": metric_id,
            "display_name": display_name,
            "owner": owner_name,
            "definition": description or f"dbt semantic layer metric {display_name}.",
            "synonyms": _metric_synonyms(metric_id, label, metadata_dict),
            "grain": _resolve_grain(item, metadata_dict),
            "unit": _resolve_unit(metric_type, metadata_dict),
            "direction": _resolve_direction(metadata_dict),
            "calculation": {
                "numerator": {
                    "source": semantic_model,
                    "filter": filter_clause or "1=1",
                    "aggregation": aggregation or "measure",
                },
                "formula": str(type_params.get("expr") or type_params.get("formula") or "").strip()
                or None,
            },
            "related_metrics": related_metrics,
            "approved_by": [],
            "caveats": caveats,
            "verified_query_ids": [],
            "version": 1,
            "last_reviewed": None if updated_at is None else updated_at.date(),
        }
    )


def _metric_synonyms(metric_id: str, label: str, metadata: dict[str, Any]) -> list[str]:
    values = _normalize_str_list(metadata.get("synonyms"))
    normalized_label = label.strip()
    if normalized_label and normalized_label.casefold() != metric_id.casefold():
        values.append(normalized_label)
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        folded = value.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        deduped.append(value)
    return deduped


def _resolve_grain(item: dict[str, Any], metadata: dict[str, Any]) -> str:
    for candidate in (
        item.get("grain"),
        metadata.get("grain"),
        item.get("timeGranularity"),
        item.get("time_granularity"),
    ):
        normalized = str(candidate or "").strip().casefold()
        if normalized in {"hourly", "daily", "weekly", "monthly", "quarterly", "yearly"}:
            return normalized
    return "daily"


def _resolve_unit(metric_type: str, metadata: dict[str, Any]) -> str:
    explicit_unit = str(metadata.get("unit") or "").strip().casefold()
    if explicit_unit in {"ratio", "count", "amount", "duration_seconds", "percentage"}:
        return explicit_unit
    if "percent" in explicit_unit:
        return "percentage"
    if metric_type in {"ratio", "conversion", "rate"}:
        return "ratio"
    if metric_type in {"sum", "revenue", "amount"}:
        return "amount"
    return "count"


def _resolve_direction(metadata: dict[str, Any]) -> str:
    explicit = str(metadata.get("direction") or "").strip().casefold()
    if explicit in {"higher_is_better", "lower_is_better", "neutral"}:
        return explicit
    return "neutral"


def _normalize_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidate = value.strip()
        return [candidate] if candidate else []
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        candidate = str(item).strip()
        if candidate:
            normalized.append(candidate)
    return normalized


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
