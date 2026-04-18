"""Tests for placeholder tools — memory_tools, web_search, user_interaction, code_execution."""

from __future__ import annotations

import json

import pytest


class TestMemorySearch:
    @pytest.mark.asyncio
    async def test_returns_empty_results(self, tmp_path):
        from ds_agent.memory.code_registry import CodeRegistry
        from ds_agent.memory.domain_kb import DomainKB
        from ds_agent.memory.experiment_log import ExperimentLog
        from ds_agent.memory.project_store import ProjectStore
        from ds_agent.runtime.memory_query_service import MemoryQueryService
        from ds_agent.tools.memory_tools import memory_search, set_memory_query_service

        set_memory_query_service(
            MemoryQueryService(
                experiment_log=ExperimentLog(str(tmp_path / "exp")),
                code_registry=CodeRegistry(str(tmp_path / "code")),
                domain_kb=DomainKB(str(tmp_path / "kb")),
                project_store=ProjectStore(str(tmp_path / "projects")),
            )
        )

        result = await memory_search("test query")
        parsed = json.loads(result)
        assert parsed["query"] == "test query"
        assert parsed["results"] == []
        assert parsed["count"] == 0


class TestMemoryStore:
    @pytest.mark.asyncio
    async def test_returns_stored_true(self, tmp_path):
        from ds_agent.memory.code_registry import CodeRegistry
        from ds_agent.memory.domain_kb import DomainKB
        from ds_agent.memory.experiment_log import ExperimentLog
        from ds_agent.memory.project_store import ProjectStore
        from ds_agent.memory.unified_store import UnifiedMemoryStore
        from ds_agent.runtime.memory_query_service import MemoryQueryService
        from ds_agent.tools.memory_tools import (
            memory_search,
            memory_store,
            set_memory_query_service,
            set_unified_memory_store,
        )

        set_memory_query_service(
            MemoryQueryService(
                experiment_log=ExperimentLog(str(tmp_path / "exp")),
                code_registry=CodeRegistry(str(tmp_path / "code")),
                domain_kb=DomainKB(str(tmp_path / "kb")),
                project_store=ProjectStore(str(tmp_path / "projects")),
            )
        )
        set_unified_memory_store(UnifiedMemoryStore(db_path=str(tmp_path / "unified_memory.db")))

        result = await memory_store("some content", "experiment", tags=["ml"])
        parsed = json.loads(result)
        assert parsed["stored"] is True
        assert parsed["type"] == "experiment"

        # "experiment" type maps to "project" in unified store
        search_result = await memory_search("some content", memory_type="project")
        search_parsed = json.loads(search_result)
        assert search_parsed["count"] == 1


class TestWebSearch:
    @pytest.mark.asyncio
    async def test_returns_empty_when_disabled(self, monkeypatch):
        from ds_agent.tools.web_search import web_search

        monkeypatch.setenv("WEB_SEARCH_DISABLED", "1")
        result = await web_search("pandas groupby")
        parsed = json.loads(result)
        assert parsed["query"] == "pandas groupby"
        assert parsed["results"] == []
        assert "disabled" in parsed["error"].lower()

    @pytest.mark.asyncio
    async def test_uses_backend_when_enabled(self, monkeypatch):
        import ds_agent.tools.web_search as ws

        monkeypatch.delenv("WEB_SEARCH_DISABLED", raising=False)
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)

        def fake_sync(query, source, max_results):
            return [
                {
                    "title": "pandas groupby",
                    "url": "https://example.test/gb",
                    "snippet": "group aggregation",
                    "source": "duckduckgo",
                }
            ]

        monkeypatch.setattr(ws, "_run_search_sync", fake_sync)

        result = await ws.web_search("pandas groupby")
        parsed = json.loads(result)
        assert parsed["count"] == 1
        assert parsed["results"][0]["url"] == "https://example.test/gb"

    @pytest.mark.asyncio
    async def test_graceful_on_network_error(self, monkeypatch):
        import urllib.error

        import ds_agent.tools.web_search as ws

        monkeypatch.delenv("WEB_SEARCH_DISABLED", raising=False)

        def boom(query, source, max_results):
            raise urllib.error.URLError("no network")

        monkeypatch.setattr(ws, "_run_search_sync", boom)

        result = await ws.web_search("anything")
        parsed = json.loads(result)
        assert parsed["results"] == []
        assert "network" in parsed["error"].lower()


class TestAskUser:
    @pytest.mark.asyncio
    async def test_returns_placeholder(self):
        from ds_agent.tools.user_interaction import ask_user

        result = await ask_user("Which model to use?", options=["A", "B"], default="A")
        parsed = json.loads(result)
        assert parsed["type"] == "user_input_required"
        assert parsed["question"] == "Which model to use?"
        assert parsed["options"] == ["A", "B"]
        assert parsed["default"] == "A"
