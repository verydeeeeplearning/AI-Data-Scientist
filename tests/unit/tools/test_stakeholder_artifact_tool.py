from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

from ds_agent.tools.registry import ToolRegistry


@pytest.fixture
def artifact_tool_module():
    ToolRegistry.reset()
    module_name = "ds_agent.tools.artifact_tools"
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


@pytest.mark.asyncio
async def test_render_stakeholder_artifact_tool_writes_markdown(
    artifact_tool_module, tmp_path: Path
) -> None:
    del artifact_tool_module
    result = await ToolRegistry.dispatch(
        "render_stakeholder_artifact",
        {
            "artifact": {
                "artifact_id": "art-pm",
                "type": "pm_action_memo",
                "audience": "pm",
                "format": "markdown",
                "content_policy": {
                    "structure": ["summary", "next_actions"],
                    "tone": "actionable",
                },
                "template_ref": "tpl/pm_memo/v2",
            },
            "analysis": {
                "summary": "Churn increased in new premium cohorts.",
                "next_actions": ["Create retention experiment", "Define owner"],
            },
            "output_dir": str(tmp_path),
            "pack_context": {"pack_id": "DP-1", "task_id": "TC-2026-001"},
        },
    )
    payload = json.loads(result)

    assert payload["format"] == "markdown"
    assert Path(payload["output_path"]).exists()
