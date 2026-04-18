"""Glossary lookup tool backed by semantic memory."""

from __future__ import annotations

from ds_agent.tools._semantic_common import (
    get_semantic_memory_container,
    semantic_error,
    semantic_result,
)
from ds_agent.tools.registry import tool


@tool(
    name="lookup_term",
    description=(
        "Look up business glossary terms from semantic memory. Returns canonical "
        "definitions, synonyms, abbreviations, and linked metrics."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Business term, acronym, or phrase to look up.",
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "description": "Maximum number of glossary matches to return.",
            },
        },
        "required": ["query"],
    },
    prompt=(
        "Looks up approved business terminology before guessing at meaning.\n"
        "- Use for acronyms, KPI names, campaign terms, and domain phrases\n"
        "- Prefer this before inventing new terminology from raw schema names"
    ),
)
def lookup_term(query: str, limit: int = 5) -> str:
    if limit <= 0:
        return semantic_error("limit must be a positive integer", tool_name="lookup_term")

    try:
        result = get_semantic_memory_container().lookup_term.execute(query, limit=limit)
    except Exception as exc:
        return semantic_error(str(exc), tool_name="lookup_term")

    return semantic_result(
        {
            "query": result.query,
            "count": len(result.matches),
            "matches": [term.model_dump(mode="json") for term in result.matches],
        }
    )
