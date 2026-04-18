"""Memory tools — query and store persistent knowledge.

Backed by UnifiedMemoryStore (SQLite + FTS5) for full-text search
and cross-session persistence, with fallback to MemoryQueryService
for legacy experiment/code_pattern/domain_knowledge stores.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ds_agent.domain.entities.memory import MemoryEntry, MemoryType
from ds_agent.tools.registry import tool

if TYPE_CHECKING:
    from ds_agent.memory.unified_store import UnifiedMemoryStore
    from ds_agent.runtime.memory_query_service import MemoryQueryService

_memory_query_service: MemoryQueryService | None = None
_unified_store: UnifiedMemoryStore | None = None

# Type mapping from tool parameters to MemoryType
_TYPE_MAP: dict[str, MemoryType] = {
    "session": MemoryType.SESSION,
    "project": MemoryType.PROJECT,
    "domain": MemoryType.DOMAIN,
    "domain_knowledge": MemoryType.DOMAIN,
    "global": MemoryType.GLOBAL,
    "experiment": MemoryType.PROJECT,
    "code_pattern": MemoryType.GLOBAL,
}


def set_memory_query_service(service: MemoryQueryService) -> None:
    """Set the global memory query service. Called by the agent factory."""
    global _memory_query_service
    _memory_query_service = service


def set_unified_memory_store(store: UnifiedMemoryStore) -> None:
    """Set the global unified memory store. Called by the agent factory."""
    global _unified_store
    _unified_store = store


def _get_memory_query_service() -> MemoryQueryService:
    global _memory_query_service
    if _memory_query_service is not None:
        return _memory_query_service

    from ds_agent.runtime.memory_query_service import MemoryQueryService
    from ds_agent.tools.path_utils import get_active_workspace

    workspace = get_active_workspace()
    workspace_dir = str(workspace) if workspace is not None else None
    _memory_query_service = MemoryQueryService.from_workspace(workspace_dir)
    return _memory_query_service


def _get_unified_store() -> UnifiedMemoryStore:
    global _unified_store
    if _unified_store is not None:
        return _unified_store

    from ds_agent.memory.unified_store import UnifiedMemoryStore

    _unified_store = UnifiedMemoryStore()
    return _unified_store


@tool(
    name="memory_search",
    description=(
        "Search the agent's persistent memory for relevant past experience. "
        "Queries experiment logs, code patterns, domain knowledge, and "
        "project-level insights using full-text search."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for memory",
            },
            "memory_type": {
                "type": "string",
                "enum": [
                    "all",
                    "session",
                    "project",
                    "domain",
                    "global",
                    "experiments",
                    "code_patterns",
                    "domain_knowledge",
                    "projects",
                ],
                "default": "all",
                "description": "Type of memory to search",
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "description": "Maximum results to return",
            },
        },
        "required": ["query"],
    },
    prompt=(
        "Searches persistent memory for past experiments, code patterns, "
        "and domain knowledge.\n"
        "- Use before starting analysis to check relevant past experience\n"
        "- Filter by memory_type for targeted search\n"
        "- Types: session, project, domain, global (unified store)\n"
        "- Legacy types: experiments, code_patterns, domain_knowledge, projects"
    ),
)
async def memory_search(query: str, memory_type: str = "all", max_results: int = 5) -> str:
    # Use unified store for new memory types
    if memory_type in ("session", "project", "domain", "global"):
        store = _get_unified_store()
        mt = _TYPE_MAP[memory_type]
        entries = store.search(query=query, memory_type=mt, max_results=max_results)
        results = [
            {
                "type": e.type.value,
                "id": e.id,
                "key": e.key,
                "content": e.content,
                "tags": e.tags,
                "confidence": round(e.effective_confidence, 3),
            }
            for e in entries
        ]
        return json.dumps(
            {"query": query, "type": memory_type, "results": results, "count": len(results)}
        )

    if memory_type == "all":
        # Search both unified store and legacy service
        combined: list[dict] = []

        # Unified store search (all types)
        store = _get_unified_store()
        for entry in store.search(query=query, max_results=max_results):
            combined.append(
                {
                    "type": entry.type.value,
                    "id": entry.id,
                    "key": entry.key,
                    "content": entry.content,
                    "tags": entry.tags,
                    "confidence": round(entry.effective_confidence, 3),
                }
            )

        # Legacy service search
        service = _get_memory_query_service()
        for item in service.search(query=query, memory_type="all", max_results=max_results):
            combined.append(item)

        return json.dumps(
            {
                "query": query,
                "type": "all",
                "results": combined[:max_results],
                "count": len(combined[:max_results]),
            }
        )

    # Legacy types: experiments, code_patterns, domain_knowledge, projects
    service = _get_memory_query_service()
    results = service.search(query=query, memory_type=memory_type, max_results=max_results)
    return json.dumps(
        {"query": query, "type": memory_type, "results": results, "count": len(results)}
    )


@tool(
    name="search_sessions",
    description=(
        "Search the agent's session-scoped memory. Returns entries stored "
        "under MemoryType.SESSION, optionally filtered by source_session_id."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": ("Search query. Use '*' to list most recent session entries."),
            },
            "session_id": {
                "type": "string",
                "description": "Optional session ID to restrict results to.",
            },
            "max_results": {
                "type": "integer",
                "default": 10,
                "description": "Maximum results to return",
            },
        },
        "required": ["query"],
    },
    prompt=(
        "Searches across prior session memory — useful for recalling what "
        "happened in a specific or recent session. Pass 'session_id' to "
        "scope to one session, or omit to search all sessions."
    ),
)
async def search_sessions(
    query: str,
    session_id: str | None = None,
    max_results: int = 10,
) -> str:
    store = _get_unified_store()
    entries = store.search_sessions(query=query, session_id=session_id, max_results=max_results)
    results = [
        {
            "id": e.id,
            "key": e.key,
            "content": e.content,
            "tags": e.tags,
            "session_id": e.source_session_id,
            "updated_at": e.updated_at,
            "confidence": round(e.effective_confidence, 3),
        }
        for e in entries
    ]
    return json.dumps(
        {
            "query": query,
            "session_id": session_id,
            "results": results,
            "count": len(results),
        }
    )


@tool(
    name="memory_store",
    description=(
        "Store a piece of knowledge in the agent's persistent memory. "
        "Use for saving experiment results, code patterns, domain insights, "
        "or any knowledge worth retaining across sessions."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Content to store",
            },
            "memory_type": {
                "type": "string",
                "enum": [
                    "session",
                    "project",
                    "domain",
                    "global",
                    "experiment",
                    "code_pattern",
                    "domain_knowledge",
                ],
                "description": "Type of memory to store",
            },
            "key": {
                "type": "string",
                "description": "Short identifier key (e.g., 'churn_definition'). "
                "Same key+type will update existing entry.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags for categorization and retrieval",
            },
        },
        "required": ["content", "memory_type"],
    },
    prompt=(
        "Stores knowledge in persistent memory for future sessions.\n"
        "- session: temporary within current session\n"
        "- project: per-project knowledge (experiment results, configs)\n"
        "- domain: cross-project domain knowledge (business rules)\n"
        "- global: organization-wide knowledge (code patterns)\n"
        "- Providing a 'key' allows updating existing entries"
    ),
)
async def memory_store(
    content: str,
    memory_type: str,
    key: str | None = None,
    tags: list[str] | None = None,
) -> str:
    # New unified memory types
    if memory_type in _TYPE_MAP:
        store = _get_unified_store()
        mt = _TYPE_MAP[memory_type]
        entry = MemoryEntry(
            type=mt,
            key=key or content[:50].replace(" ", "_").lower(),
            content=content,
            tags=tags or [],
        )
        entry_id = store.store(entry)
        return json.dumps(
            {
                "stored": True,
                "type": memory_type,
                "id": entry_id,
                "key": entry.key,
                "tags": entry.tags,
            }
        )

    # Legacy fallback
    service = _get_memory_query_service()
    return json.dumps(service.store(content=content, memory_type=memory_type, tags=tags))
