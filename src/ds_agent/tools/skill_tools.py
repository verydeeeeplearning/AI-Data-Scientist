"""Skill tools — list, view, and search agent skills."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ds_agent.tools.registry import tool

if TYPE_CHECKING:
    from ds_agent.skills.hub import SkillHub

# Global SkillHub instance — set by DSAgent at startup
_skill_hub: SkillHub | None = None


def set_skill_hub(hub: SkillHub) -> None:
    """Set the global SkillHub instance. Called by DSAgent."""
    global _skill_hub
    _skill_hub = hub


@tool(
    name="skill_list",
    description=(
        "List all available agent skills with descriptions. "
        "Skills contain procedural DS knowledge (methodology, best practices)."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["ds_methodology", "task_type", "best_practice", "custom"],
                "description": "Filter by skill category",
            },
        },
    },
    prompt="Lists available skills with descriptions. Use skill_view to read full content.",
)
async def skill_list(category: str | None = None) -> str:
    if _skill_hub is None:
        return json.dumps({"skills": [], "note": "SkillHub not initialized"})
    return json.dumps({"skills": _skill_hub.list_skills(category=category)})


@tool(
    name="skill_view",
    description=(
        "View the detailed content of a specific skill. "
        "Skills contain step-by-step procedures, decision guides, "
        "common pitfalls, and code patterns for DS tasks."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "Name of the skill (e.g., 'scoping', 'eda', 'modeling')",
            },
        },
        "required": ["skill_name"],
    },
    prompt=(
        "Views full skill content — procedures, decision guides, code patterns.\n"
        "- Read relevant skills BEFORE starting complex tasks\n"
        "- Skills contain domain-specific best practices that improve results"
    ),
)
async def skill_view(skill_name: str) -> str:
    if _skill_hub is None:
        return json.dumps({"error": "SkillHub not initialized"})
    result = _skill_hub.view_skill(skill_name)
    if result is None:
        return json.dumps({"error": f"Skill not found: {skill_name}"})
    return json.dumps(result)


@tool(
    name="skill_search",
    description=("Search skills by keyword. Matches against skill names, descriptions, and tags."),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "category": {
                "type": "string",
                "enum": ["ds_methodology", "task_type", "best_practice", "custom"],
                "description": "Filter by category",
            },
        },
        "required": ["query"],
    },
    prompt="Searches skills by keyword across names, descriptions, and tags.",
)
async def skill_search(query: str, category: str | None = None) -> str:
    if _skill_hub is None:
        return json.dumps({"results": [], "note": "SkillHub not initialized"})
    results = _skill_hub.search_skills(query, category=category)
    return json.dumps({"results": results, "count": len(results)})
