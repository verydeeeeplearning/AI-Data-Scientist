"""Tests for agent/factory.py — build helpers for memory hints and project context."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from ds_agent.agent.callbacks import NullCallbacks
from ds_agent.agent.factory import (
    _build_memory_hints,
    _build_project_context,
    _verifier_auto_run_mode,
    create_agent,
    import_all_tools,
)
from ds_agent.tools.registry import ToolRegistry


class TestBuildMemoryHints:
    def test_returns_empty_on_error(self):
        """If DomainKB raises, returns empty string gracefully."""
        with patch("ds_agent.memory.domain_kb.DomainKB", side_effect=Exception("db error")):
            result = _build_memory_hints("/nonexistent")
        assert result == ""

    def test_returns_hints_on_success(self):
        """If DomainKB + MemoryHintBuilder work, returns hints string."""
        mock_kb = MagicMock()
        mock_builder = MagicMock()
        mock_builder.build_hints.return_value = "Use LightGBM for tabular data"
        mock_semantic_builder = MagicMock()
        mock_semantic_builder.build_hints.return_value = ""

        with (
            patch("ds_agent.memory.domain_kb.DomainKB", return_value=mock_kb),
            patch(
                "ds_agent.self_improve.memory_hints.MemoryHintBuilder",
                return_value=mock_builder,
            ),
            patch(
                "ds_agent.memory.semantic.prompt_hints.SemanticMemoryHintBuilder",
                return_value=mock_semantic_builder,
            ),
        ):
            result = _build_memory_hints("/workspace")

        assert result == "Use LightGBM for tabular data"

    def test_appends_semantic_hints_when_available(self):
        mock_kb = MagicMock()
        mock_builder = MagicMock()
        mock_builder.build_hints.return_value = "Legacy memory hint"
        mock_semantic_builder = MagicMock()
        mock_semantic_builder.build_hints.return_value = "## Semantic Context\n- Metrics: churn"

        with (
            patch("ds_agent.memory.domain_kb.DomainKB", return_value=mock_kb),
            patch(
                "ds_agent.self_improve.memory_hints.MemoryHintBuilder",
                return_value=mock_builder,
            ),
            patch(
                "ds_agent.memory.semantic.prompt_hints.SemanticMemoryHintBuilder",
                return_value=mock_semantic_builder,
            ),
        ):
            result = _build_memory_hints("/workspace")

        assert "Legacy memory hint" in result
        assert "## Semantic Context" in result


class TestBuildProjectContext:
    def test_no_workspace_returns_empty(self):
        result = _build_project_context(None, "proj1")
        assert result == ""

    def test_no_project_id_returns_empty(self):
        result = _build_project_context("/workspace", None)
        assert result == ""

    def test_project_not_found_returns_empty(self):
        mock_store = MagicMock()
        mock_store.get_project.return_value = None

        with patch("ds_agent.memory.project_store.ProjectStore", return_value=mock_store):
            result = _build_project_context("/workspace", "proj1")

        assert result == ""

    def test_project_found_returns_context(self):
        mock_store = MagicMock()
        mock_store.get_project.return_value = {
            "name": "Churn Analysis",
            "task_type": "binary_classification",
            "artifacts": ["model.pkl", "report.md"],
        }

        with patch("ds_agent.memory.project_store.ProjectStore", return_value=mock_store):
            result = _build_project_context("/workspace", "proj1")

        assert "Churn Analysis" in result
        assert "binary_classification" in result
        assert "2" in result  # artifact count

    def test_error_returns_empty(self):
        with patch(
            "ds_agent.memory.project_store.ProjectStore",
            side_effect=Exception("store error"),
        ):
            result = _build_project_context("/workspace", "proj1")

        assert result == ""


def test_import_all_tools_registers_learning_tools():
    original_tools = dict(ToolRegistry._tools)
    try:
        ToolRegistry.reset()
        sys.modules.pop("ds_agent.tools.learning_tools", None)

        import_all_tools()

        names = set(ToolRegistry.list_tools())
        assert {
            "list_learning_inbox",
            "review_learning_item",
            "get_learning_item",
            "list_promotions",
            "list_deprecations",
            "rollback_promotion",
            "run_gc_loop",
            "get_gc_report",
        }.issubset(names)
    finally:
        ToolRegistry._tools = original_tools


def test_create_agent_disables_post_learning_when_governance_flag_off(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1", raising=False)

    agent = create_agent(
        provider=MagicMock(),
        callbacks=NullCallbacks(),
        workspace_dir=str(tmp_path),
    )

    assert agent._post_learner is None


def test_create_agent_enables_post_learning_when_governance_flag_on(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1", "true")

    agent = create_agent(
        provider=MagicMock(),
        callbacks=NullCallbacks(),
        workspace_dir=str(tmp_path),
    )

    assert agent._post_learner is not None


def test_verifier_auto_run_mode_defaults_to_shadow(monkeypatch):
    monkeypatch.delenv("DS_AGENT_VERIFIER_AUTO_RUN_V1", raising=False)

    assert _verifier_auto_run_mode() == "shadow"


def test_create_agent_registers_auto_verifier_by_default(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("DS_AGENT_VERIFIER_AUTO_RUN_V1", raising=False)

    agent = create_agent(
        provider=MagicMock(),
        callbacks=NullCallbacks(),
        workspace_dir=str(tmp_path),
    )

    hook = next(hook for hook in agent._hooks.hooks if hook.name == "auto_verifier")
    assert hook.priority == 59
    assert hook.mode == "shadow"


def test_create_agent_respects_explicit_auto_verifier_off_override(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("DS_AGENT_VERIFIER_AUTO_RUN_V1", "off")

    agent = create_agent(
        provider=MagicMock(),
        callbacks=NullCallbacks(),
        workspace_dir=str(tmp_path),
    )

    assert all(hook.name != "auto_verifier" for hook in agent._hooks.hooks)
