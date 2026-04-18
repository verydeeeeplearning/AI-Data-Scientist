"""Semantic pack loading tool backed by the semantic-memory container."""

from __future__ import annotations

import json

from ds_agent.memory.semantic.infrastructure.pack_paths import resolve_semantic_pack_dir
from ds_agent.tools._semantic_common import get_semantic_memory_container, semantic_error
from ds_agent.tools.path_utils import get_active_workspace
from ds_agent.tools.registry import tool


@tool(
    name="load_semantic_pack",
    description=(
        "Dry-run or apply a semantic pack from a workspace path or a built-in "
        "domain skill directory. Use this when organization-specific metrics, "
        "glossary terms, trust metadata, or verified queries need to be imported "
        "into semantic memory before analysis."
    ),
    category="governance",
    parameters={
        "type": "object",
        "properties": {
            "pack_dir": {
                "type": "string",
                "description": "Workspace-relative or absolute path to a semantic pack root.",
            },
            "skill_name": {
                "type": "string",
                "description": "Built-in semantic pack skill directory name to load.",
            },
            "dry_run": {
                "type": "boolean",
                "default": True,
                "description": "When true, only return the diff without writing metrics.",
            },
            "allow_definition_updates": {
                "type": "boolean",
                "default": False,
                "description": "Allow metric definition changes to overwrite existing metrics.",
            },
        },
    },
    prompt=(
        "Loads semantic packs into the canonical semantic-memory store.\n"
        "- Use dry_run=true first to inspect adds, updates, and conflicts\n"
        "- Apply only after the diff is acceptable"
    ),
)
def load_semantic_pack(
    pack_dir: str | None = None,
    skill_name: str | None = None,
    dry_run: bool = True,
    allow_definition_updates: bool = False,
) -> str:
    try:
        resolved_pack_dir, source = resolve_semantic_pack_dir(
            pack_dir=pack_dir,
            skill_name=skill_name,
            workspace_dir=get_active_workspace(),
        )
        result = get_semantic_memory_container().load_semantic_pack.execute(
            str(resolved_pack_dir),
            dry_run=dry_run,
            allow_definition_updates=allow_definition_updates,
        )
    except Exception as exc:
        return semantic_error(str(exc), tool_name="load_semantic_pack")

    payload = result.model_dump(mode="json")
    payload["resolved_pack_dir"] = str(resolved_pack_dir)
    payload["source"] = source
    if skill_name is not None:
        payload["skill_name"] = skill_name
    return json.dumps(payload, ensure_ascii=False)
