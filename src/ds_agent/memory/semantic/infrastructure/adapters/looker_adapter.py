"""External semantic adapter for Looker semantic metadata."""

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


class LookerAdapter(ExternalSemanticSource):
    """Fetch metrics, glossary terms, and verified SQL from a Looker export endpoint."""

    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: str | None = None,
        auth_scheme: str = "token",
        source_name: str = "looker",
        owner: str = "looker",
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
        payload = self._request_json()
        metrics: list[Metric] = []
        for field, view in _iter_fields(payload):
            updated_at = _resolve_updated_at(field, view)
            if since is not None and updated_at is not None and updated_at < since:
                continue
            if str(field.get("type") or "").strip().lower() != "measure":
                continue
            metrics.append(_build_metric(field, view, owner=self._owner))
        return metrics

    def fetch_glossary_terms(self, since: datetime | None) -> list[GlossaryTerm]:
        payload = self._request_json()
        glossary: list[GlossaryTerm] = []
        for field, view in _iter_fields(payload):
            updated_at = _resolve_updated_at(field, view)
            if since is not None and updated_at is not None and updated_at < since:
                continue
            glossary.append(_build_glossary(field, view, owner=self._owner))
        return glossary

    def fetch_tables(self, since: datetime | None) -> list[TableTrust]:
        del since
        return []

    def fetch_verified_queries(self, since: datetime | None) -> list[VerifiedQuery]:
        payload = self._request_json()
        queries: list[VerifiedQuery] = []
        for look in _extract_looks(payload):
            updated_at = _parse_datetime(look.get("updated_at") or look.get("updatedAt"))
            if since is not None and updated_at is not None and updated_at < since:
                continue
            queries.append(_build_verified_query(look, owner=self._owner))
        return queries

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
            raise ValueError("looker response must be a JSON object")
        return payload


def _iter_fields(payload: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    views = payload.get("views")
    if not isinstance(views, list):
        raise ValueError("looker response missing views collection")
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for view in views:
        if not isinstance(view, dict):
            continue
        fields = view.get("fields")
        if not isinstance(fields, list):
            continue
        for field in fields:
            if isinstance(field, dict):
                pairs.append((field, view))
    return pairs


def _extract_looks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    looks = payload.get("looks")
    if not isinstance(looks, list):
        return []
    return [item for item in looks if isinstance(item, dict)]


def _build_metric(field: dict[str, Any], view: dict[str, Any], *, owner: str) -> Metric:
    metric_id = str(field.get("name") or "").strip()
    if not metric_id:
        raise ValueError("looker measure is missing a name")
    label = str(field.get("label") or "").strip()
    display_name = label or metric_id.replace("_", " ").title()
    source = str(
        field.get("source") or view.get("sql_table_name") or view.get("name") or "looker"
    ).strip()
    metadata = (
        cast(dict[str, Any], field.get("metadata"))
        if isinstance(field.get("metadata"), dict)
        else {}
    )
    updated_at = _resolve_updated_at(field, view)
    return Metric.model_validate(
        {
            "metric_id": metric_id,
            "display_name": display_name,
            "owner": str(field.get("owner") or view.get("owner") or owner).strip() or owner,
            "definition": str(
                field.get("description") or view.get("description") or display_name
            ).strip(),
            "synonyms": _normalize_list(field.get("synonyms")) + ([label] if label else []),
            "grain": str(field.get("grain") or metadata.get("grain") or "daily").strip().lower()
            or "daily",
            "unit": str(field.get("unit") or metadata.get("unit") or "count").strip().lower()
            or "count",
            "direction": (
                str(field.get("direction") or metadata.get("direction") or "neutral")
                .strip()
                .lower()
                or "neutral"
            ),
            "calculation": {
                "numerator": {
                    "source": source,
                    "filter": str(field.get("filter") or "1=1").strip() or "1=1",
                    "aggregation": str(
                        field.get("aggregation") or field.get("sql") or "measure"
                    ).strip()
                    or "measure",
                }
            },
            "related_metrics": _normalize_list(field.get("related_metrics")),
            "approved_by": [],
            "caveats": _normalize_list(field.get("caveats")),
            "verified_query_ids": [],
            "version": 1,
            "last_reviewed": None if updated_at is None else updated_at.date(),
        }
    )


def _build_glossary(field: dict[str, Any], view: dict[str, Any], *, owner: str) -> GlossaryTerm:
    field_name = str(field.get("name") or "").strip()
    if not field_name:
        raise ValueError("looker field is missing a name")
    label = str(field.get("label") or "").strip()
    canonical_form = label or field_name.replace("_", " ")
    field_type = str(field.get("type") or "").strip().lower()
    category = "metric" if field_type == "measure" else "dimension"
    linked_metrics = (
        [field_name] if category == "metric" else _normalize_list(field.get("linked_metric_ids"))
    )
    return GlossaryTerm.model_validate(
        {
            "term_id": str(field.get("term_id") or f"term.{field_name}").strip(),
            "canonical_form": canonical_form,
            "definition": str(
                field.get("description") or view.get("description") or canonical_form
            ).strip(),
            "synonyms": _normalize_list(field.get("synonyms")),
            "abbreviations": _normalize_list(field.get("abbreviations")),
            "translations": (
                field.get("translations") if isinstance(field.get("translations"), dict) else {}
            ),
            "linked_metric_ids": linked_metrics,
            "category": category if category in {"metric", "dimension"} else "other",
            "owner": str(field.get("owner") or view.get("owner") or owner).strip() or owner,
        }
    )


def _build_verified_query(look: dict[str, Any], *, owner: str) -> VerifiedQuery:
    look_id = str(look.get("id") or "").strip()
    if not look_id:
        raise ValueError("looker look is missing an id")
    sql = str(look.get("sql") or "").strip()
    if not sql:
        raise ValueError(f"looker look '{look_id}' is missing sql")
    updated_at = _parse_datetime(look.get("updated_at") or look.get("updatedAt"))
    return VerifiedQuery.model_validate(
        {
            "vq_id": f"look-{look_id}",
            "metric_id": str(look.get("metric_id") or "").strip() or None,
            "dialect": str(look.get("dialect") or "bigquery").strip().lower() or "bigquery",
            "description": str(
                look.get("title") or look.get("description") or f"Looker look {look_id}"
            ).strip(),
            "sql_template": sql,
            "parameters": [],
            "referenced_tables": _normalize_list(look.get("tables")),
            "verified_by": str(look.get("owner") or owner).strip() or owner,
            "last_verified": (
                updated_at.date().isoformat()
                if updated_at is not None
                else datetime.now(UTC).date().isoformat()
            ),
            "verification_evidence": str(
                look.get("verification_evidence") or look.get("url") or f"Looker look {look_id}"
            ).strip(),
            "failure_modes": _normalize_list(look.get("failure_modes")),
            "tags": [*_normalize_list(look.get("tags")), "looker"],
        }
    )


def _resolve_updated_at(field: dict[str, Any], view: dict[str, Any]) -> datetime | None:
    return _parse_datetime(
        field.get("updated_at")
        or field.get("updatedAt")
        or view.get("updated_at")
        or view.get("updatedAt")
    )


def _normalize_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidate = value.strip()
        return [candidate] if candidate else []
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        candidate = str(item).strip()
        if not candidate:
            continue
        folded = candidate.casefold()
        if folded in seen:
            continue
        seen.add(folded)
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
