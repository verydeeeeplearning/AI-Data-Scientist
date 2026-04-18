"""Semantic query planner tool backed by semantic memory."""

from __future__ import annotations

from ds_agent.memory.semantic.domain.metric import Metric, MetricGrain
from ds_agent.memory.semantic.domain.org_context import CalendarEvent, NegativeKnowledge
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import QueryDialect
from ds_agent.tools._semantic_common import (
    get_semantic_memory_container,
    parse_iso_date,
    semantic_error,
    semantic_result,
)
from ds_agent.tools.registry import tool


@tool(
    name="semantic_query",
    description=(
        "Resolve a business question against semantic memory before drafting SQL. "
        "Returns the best metric match, verified SQL when available, trust policy, "
        "calendar/negative-knowledge caveats, and the recommended next action."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Business question or KPI request to resolve semantically.",
            },
            "required_grain": {
                "type": "string",
                "enum": ["hourly", "daily", "weekly", "monthly", "quarterly", "yearly"],
                "description": "Optional grain constraint for metric matching.",
            },
            "as_of_date": {
                "type": "string",
                "description": "Optional ISO date for calendar hints and query binding.",
            },
            "dialect": {
                "type": "string",
                "enum": ["postgres", "bigquery", "snowflake", "duckdb", "databricks_sql"],
                "default": "postgres",
                "description": "Preferred SQL dialect for verified queries.",
            },
            "allow_untrusted": {
                "type": "boolean",
                "default": False,
                "description": "Allow bronze/untrusted tables with warnings instead of blocking.",
            },
        },
        "required": ["question"],
    },
    prompt=(
        "Resolve metric-like requests through semantic memory before using raw SQL tools.\n"
        "- Prefer this for churn, retention, GMV, MAU, revenue, or other KPI questions\n"
        "- Use the returned next_action and caveats to decide whether execution is safe"
    ),
)
def semantic_query(
    question: str,
    required_grain: MetricGrain | None = None,
    as_of_date: str | None = None,
    dialect: QueryDialect = "postgres",
    allow_untrusted: bool = False,
) -> str:
    try:
        container = get_semantic_memory_container()
        as_of = parse_iso_date(as_of_date, tool_name="semantic_query")
        metric_result = container.resolve_metric.execute(question, grain=required_grain)
        glossary_result = container.lookup_term.execute(question, limit=5)
        matched_terms = [term.canonical_form for term in glossary_result.matches]
    except Exception as exc:
        return semantic_error(str(exc), tool_name="semantic_query")

    if metric_result.best_match is None:
        warnings = ["No approved metric matched; schema-based inference would require confirmation."]
        return semantic_result(
            {
                "kind": "inferred",
                "sql": _inferred_sql_stub(question),
                "metric": None,
                "verified_query_id": None,
                "matched_terms": matched_terms,
                "confidence": 0.0,
                "trust_report": [],
                "caveats": [],
                "warnings": warnings,
                "calendar_hints": _calendar_hints(container.org_context.list_calendar_events(as_of=as_of)),
                "negative_knowledge": [],
                "next_action": "ask_user",
                "requires_confirmation": True,
                "reasoning": "No canonical metric or verified query matched the request.",
            }
        )

    metric_match = metric_result.best_match
    metric = metric_match.metric
    calendar_hints = _calendar_hints(container.org_context.list_calendar_events(as_of=as_of))
    negative_knowledge = _negative_knowledge_hints(
        container.org_context.list_negative_knowledge(metric.metric_id)
    )

    verified_warning: str | None = None
    try:
        verified_result = container.find_verified_query.execute(
            metric.metric_id,
            dialect=dialect,
            bindings=_verified_query_bindings(as_of_date),
        )
    except ValueError as exc:
        verified_result = None
        verified_warning = str(exc)
    except Exception as exc:
        return semantic_error(str(exc), tool_name="semantic_query")

    if verified_result is not None and verified_result.query is not None:
        trust_result = container.check_table_trust.execute(
            verified_result.query.referenced_tables,
            allow_untrusted=allow_untrusted,
        )
        next_action, requires_confirmation = _next_action(trust_result.action)
        warnings = list(trust_result.warnings)
        if verified_warning is not None:
            warnings.append(verified_warning)
        return semantic_result(
            {
                "kind": "verified",
                "sql": verified_result.rendered_sql,
                "metric": metric.model_dump(mode="json"),
                "verified_query_id": verified_result.query.vq_id,
                "matched_terms": _merge_terms(matched_terms, [metric.display_name]),
                "confidence": round(min(1.0, metric_match.score + 0.02), 3),
                "trust_report": _trust_report(trust_result.tables),
                "caveats": metric.caveats,
                "warnings": warnings,
                "calendar_hints": calendar_hints,
                "negative_knowledge": negative_knowledge,
                "next_action": next_action,
                "requires_confirmation": requires_confirmation,
                "reasoning": (
                    f"Verified query matched metric '{metric.metric_id}' and trust policy "
                    f"evaluated to '{trust_result.action}'."
                ),
            }
        )

    source_tables = _metric_source_tables(metric)
    trust_result = container.check_table_trust.execute(
        source_tables,
        allow_untrusted=allow_untrusted,
    )
    next_action, requires_confirmation = _next_action(trust_result.action)
    warnings = ["No verified query found; SQL synthesized from metric definition."]
    warnings.extend(trust_result.warnings)
    if verified_warning is not None:
        warnings.append(verified_warning)
    return semantic_result(
        {
            "kind": "metric_synthesized",
            "sql": _synthesized_metric_sql(metric),
            "metric": metric.model_dump(mode="json"),
            "verified_query_id": None,
            "matched_terms": _merge_terms(matched_terms, [metric.display_name]),
            "confidence": round(min(0.89, metric_match.score), 3),
            "trust_report": _trust_report(trust_result.tables),
            "caveats": metric.caveats,
            "warnings": warnings,
            "calendar_hints": calendar_hints,
            "negative_knowledge": negative_knowledge,
            "next_action": next_action,
            "requires_confirmation": requires_confirmation,
            "reasoning": (
                f"Metric '{metric.metric_id}' matched, but no verified query was usable for "
                f"dialect '{dialect}'."
            ),
        }
    )


def _verified_query_bindings(as_of_date: str | None) -> dict[str, object] | None:
    if as_of_date is None:
        return None
    return {"as_of_date": as_of_date}


def _next_action(action: str) -> tuple[str, bool]:
    if action == "allow":
        return "execute", False
    if action == "caveat":
        return "execute_with_warning", False
    if action == "confirm":
        return "ask_user", True
    return "block", True


def _merge_terms(primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for term in [*primary, *secondary]:
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(term)
    return merged


def _calendar_hints(events: list[CalendarEvent]) -> list[str]:
    return [
        f"{event.name}: {event.impact_hint or event.description}"
        for event in events
    ]


def _negative_knowledge_hints(entries: list[NegativeKnowledge]) -> list[str]:
    return [
        f"{entry.wrong_approach} -> {entry.correct_approach} ({entry.why_wrong})"
        for entry in entries
    ]


def _trust_report(tables: list[TableTrust]) -> list[dict[str, object]]:
    return [table.model_dump(mode="json") for table in tables]


def _metric_source_tables(metric: Metric) -> list[str]:
    tables = [metric.calculation.numerator.source]
    if metric.calculation.denominator is not None:
        tables.append(metric.calculation.denominator.source)
    return tables


def _inferred_sql_stub(question: str) -> str:
    return (
        "-- No canonical metric matched this request.\n"
        f"-- Question: {question}\n"
        "-- Confirm the business definition before writing fallback SQL."
    )


def _synthesized_metric_sql(metric: Metric) -> str:
    numerator = metric.calculation.numerator
    denominator = metric.calculation.denominator
    if denominator is None:
        return (
            "SELECT\n"
            f"  {numerator.aggregation} AS {metric.metric_id}\n"
            f"FROM {numerator.source}\n"
            f"WHERE {numerator.filter};"
        )

    return (
        "WITH numerator AS (\n"
        "    SELECT\n"
        f"      {numerator.aggregation} AS value\n"
        f"    FROM {numerator.source}\n"
        f"    WHERE {numerator.filter}\n"
        "),\n"
        "denominator AS (\n"
        "    SELECT\n"
        f"      {denominator.aggregation} AS value\n"
        f"    FROM {denominator.source}\n"
        f"    WHERE {denominator.filter}\n"
        ")\n"
        "SELECT\n"
        f"  1.0 * numerator.value / NULLIF(denominator.value, 0) AS {metric.metric_id}\n"
        "FROM numerator\n"
        "CROSS JOIN denominator;"
    )
