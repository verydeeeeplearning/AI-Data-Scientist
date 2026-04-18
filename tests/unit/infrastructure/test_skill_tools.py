"""Tests for tools/skill_tools.py — skill list, view, search via mock SkillHub."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from ds_agent.tools import skill_tools


class TestSkillToolsNoHub:
    """When SkillHub is not initialized, tools return graceful fallback."""

    @pytest.fixture(autouse=True)
    def _clear_hub(self):
        skill_tools._skill_hub = None
        yield
        skill_tools._skill_hub = None

    @pytest.mark.asyncio
    async def test_skill_list_no_hub(self):
        result = await skill_tools.skill_list()
        parsed = json.loads(result)
        assert parsed["skills"] == []
        note = parsed.get("note", "")
        assert "not initialized" in note.lower() or "SkillHub" in note

    @pytest.mark.asyncio
    async def test_skill_view_no_hub(self):
        result = await skill_tools.skill_view("eda")
        parsed = json.loads(result)
        assert "error" in parsed
        err = parsed["error"]
        assert "not initialized" in err.lower() or "SkillHub" in err

    @pytest.mark.asyncio
    async def test_skill_search_no_hub(self):
        result = await skill_tools.skill_search("modeling")
        parsed = json.loads(result)
        assert parsed["results"] == []
        note = parsed.get("note", "")
        assert "not initialized" in note.lower() or "SkillHub" in note


class TestSkillToolsWithHub:
    """When SkillHub is set, tools delegate correctly."""

    @pytest.fixture(autouse=True)
    def _setup_hub(self):
        self.mock_hub = MagicMock()
        self.mock_hub.list_skills.return_value = [
            {
                "name": "eda",
                "description": "Exploratory data analysis",
                "category": "ds_methodology",
                "tags": ["eda"],
            },
            {
                "name": "modeling",
                "description": "Model training",
                "category": "task_type",
                "tags": ["ml"],
            },
        ]
        self.mock_hub.view_skill.return_value = {
            "name": "eda",
            "description": "EDA procedures",
            "category": "ds_methodology",
            "tags": ["eda"],
            "content": "# EDA\nStep 1...",
            "token_estimate": 500,
            "version": "1.0.0",
            "related_skills": ["modeling"],
        }
        self.mock_hub.search_skills.return_value = [
            {
                "name": "eda",
                "description": "Exploratory data analysis",
                "category": "ds_methodology",
                "tags": ["eda"],
            },
        ]
        skill_tools.set_skill_hub(self.mock_hub)
        yield
        skill_tools._skill_hub = None

    @pytest.mark.asyncio
    async def test_skill_list_returns_all(self):
        result = await skill_tools.skill_list()
        parsed = json.loads(result)
        assert len(parsed["skills"]) == 2
        self.mock_hub.list_skills.assert_called_once_with(category=None)

    @pytest.mark.asyncio
    async def test_skill_list_with_category(self):
        await skill_tools.skill_list(category="ds_methodology")
        self.mock_hub.list_skills.assert_called_once_with(category="ds_methodology")

    @pytest.mark.asyncio
    async def test_skill_view_found(self):
        result = await skill_tools.skill_view("eda")
        parsed = json.loads(result)
        assert parsed["name"] == "eda"
        assert "content" in parsed
        self.mock_hub.view_skill.assert_called_once_with("eda")

    @pytest.mark.asyncio
    async def test_skill_view_not_found(self):
        self.mock_hub.view_skill.return_value = None
        result = await skill_tools.skill_view("nonexistent")
        parsed = json.loads(result)
        assert "error" in parsed
        assert "not found" in parsed["error"].lower()

    @pytest.mark.asyncio
    async def test_skill_search_returns_results(self):
        result = await skill_tools.skill_search("eda")
        parsed = json.loads(result)
        assert parsed["count"] == 1
        assert parsed["results"][0]["name"] == "eda"
        self.mock_hub.search_skills.assert_called_once_with("eda", category=None)

    @pytest.mark.asyncio
    async def test_skill_search_with_category(self):
        await skill_tools.skill_search("eda", category="ds_methodology")
        self.mock_hub.search_skills.assert_called_once_with("eda", category="ds_methodology")


class TestSetSkillHub:
    def test_set_skill_hub(self):
        mock = MagicMock()
        skill_tools.set_skill_hub(mock)
        assert skill_tools._skill_hub is mock
        skill_tools._skill_hub = None
