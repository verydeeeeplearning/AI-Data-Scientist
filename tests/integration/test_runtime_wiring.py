"""Runtime wiring contract tests — verify the agent factory produces
a correctly-wired DSAgent with all hooks, skills, and prompt sections.

These tests catch the class of bugs where components are implemented
but not connected to the runtime path (WIRE-01 through WIRE-07).
"""

from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.agent.factory import (
    build_hook_registry,
    build_prompt_builder,
    create_agent,
)
from ds_agent.application.services.warehouse_service import (
    clear_warehouse_adapters,
    get_warehouse_adapter,
)
from ds_agent.domain.entities.messages import LLMResponse, Usage
from ds_agent.domain.entities.provider_models import ModelInfo
from ds_agent.domain.value_objects.connector import ConnectorConfig, ConnectorType
from ds_agent.infrastructure.persistence.postgres_adapter import PostgresAdapter

EXPECTED_CORE_HOOKS = {
    "audit_log",
    "session_init",
    "problem_type_router",
    "permission",
    "org_policy",
    "query_cost_guard",
    "budget_guard",
    "workflow_tracker",
    "leakage_detection",
    "baseline_guard",
    "temporal_join_guard",
    "self_debug",
    "overfitting_detector",
    "backtrack_trigger",
    "model_sanity_check",
    "stage_quality",
    "profile_results",
    "experiment_design",
    "process_metrics",
    "experiment_tracker",
    "review_artifact_capture",
    "policy_approval",
    "pii_redaction",
    "semantic_read_guard",
    "semantic_trust",
    "semantic_writeback",
    "lineage_capture",
    "claim_traceability",
    "drift_detection",
    "exec_plan_save",
}


def _hook_names(hooks: list[object]) -> list[str]:
    return [hook.name for hook in hooks]


def _assert_core_hooks_present(names: list[str]) -> None:
    assert len(names) == len(set(names))
    assert EXPECTED_CORE_HOOKS.issubset(set(names))


def _mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.chat = AsyncMock(return_value=LLMResponse(content="done", usage=Usage()))
    provider.count_tokens = AsyncMock(return_value=100)
    provider.get_model_info = MagicMock(
        return_value=ModelInfo(
            model_id="test",
            provider="test",
            display_name="Test",
            max_context_tokens=128_000,
            max_output_tokens=4096,
        )
    )
    return provider


class TestHookRegistryWiring:
    """WIRE-01: Verify all hooks are registered."""

    def test_hook_registry_has_unique_expected_hooks(self):
        registry = build_hook_registry()
        names = _hook_names(registry.hooks)
        _assert_core_hooks_present(names)
        assert "auto_verifier" not in names

    def test_hooks_sorted_by_priority(self):
        registry = build_hook_registry()
        priorities = [h.priority for h in registry.hooks]
        assert priorities == sorted(priorities)

    def test_critical_hooks_present(self):
        registry = build_hook_registry()
        names = _hook_names(registry.hooks)
        _assert_core_hooks_present(names)


class TestPromptBuilderWiring:
    """WIRE-04 / GAP-04: Verify PromptBuilder is populated with skills and context."""

    def test_skill_hub_loaded(self):
        pb = build_prompt_builder()
        assert pb._skill_hub is not None

    def test_skill_names_populated(self):
        """GAP-04/5.2 fix: skill_names must be non-empty."""
        pb = build_prompt_builder()
        assert len(pb._skill_names) >= 5

    def test_tool_registry_set(self):
        pb = build_prompt_builder()
        assert pb._tool_registry is not None

    def test_system_prompt_contains_identity(self):
        pb = build_prompt_builder()
        content = pb._build_system_content()
        assert "DS Agent" in content or "data scien" in content.lower()


class TestCreateAgent:
    """Full factory integration — GAP-05: same wiring for all entrypoints."""

    def test_agent_has_hook_registry(self, monkeypatch):
        monkeypatch.delenv("DS_AGENT_VERIFIER_AUTO_RUN_V1", raising=False)
        agent = create_agent(
            provider=_mock_provider(),
            callbacks=MagicMock(),
        )
        names = _hook_names(agent._hooks.hooks)
        _assert_core_hooks_present(names)
        auto_verifier = next(hook for hook in agent._hooks.hooks if hook.name == "auto_verifier")
        assert auto_verifier.mode == "shadow"

    def test_agent_omits_auto_verifier_when_disabled(self, monkeypatch):
        monkeypatch.setenv("DS_AGENT_VERIFIER_AUTO_RUN_V1", "off")
        agent = create_agent(
            provider=_mock_provider(),
            callbacks=MagicMock(),
        )
        names = _hook_names(agent._hooks.hooks)
        _assert_core_hooks_present(names)
        assert "auto_verifier" not in names

    def test_agent_has_prompt_builder_with_skills(self):
        agent = create_agent(
            provider=_mock_provider(),
            callbacks=MagicMock(),
        )
        assert len(agent._prompt_builder._skill_names) >= 5

    def test_agent_mode_passed(self):
        agent = create_agent(
            provider=_mock_provider(),
            callbacks=MagicMock(),
            mode="supervised",
        )
        assert agent._mode == "supervised"

    def test_agent_has_goal_and_working_memory_stores(self):
        agent = create_agent(
            provider=_mock_provider(),
            callbacks=MagicMock(),
            session_id="wiring-session",
        )
        assert agent._goal_store is not None
        assert agent._working_memory_store is not None
        assert agent._approval_store is not None
        assert agent._prompt_builder._goal_store is not None
        assert agent._prompt_builder._working_memory_store is not None

    @pytest.mark.asyncio
    async def test_session_init_injects_rules(self):
        """WIRE-02: Session init hooks inject DS methodology rules."""
        agent = create_agent(
            provider=_mock_provider(),
            callbacks=MagicMock(),
        )
        # Simulate what run() does: call session init
        from ds_agent.agent.hooks import HookContext

        ctx = HookContext(emit=lambda e, p: None)
        injections = await agent._hooks.run_session_init(ctx)
        assert len(injections) >= 1
        # SessionInitHook should inject DS methodology rules
        combined = "\n".join(injections)
        assert "baseline" in combined.lower() or "methodology" in combined.lower()

    def test_create_agent_initializes_configured_connectors(self):
        clear_warehouse_adapters()

        create_agent(
            provider=_mock_provider(),
            callbacks=MagicMock(),
            connector_configs={
                "warehouse": ConnectorConfig(
                    type=ConnectorType.POSTGRES,
                    host="localhost",
                    database="analytics",
                )
            },
        )

        assert isinstance(get_warehouse_adapter("warehouse"), PostgresAdapter)

    def test_create_agent_wires_provider_backed_verifier_container(self, tmp_path):
        verifier_tool_module = importlib.import_module("ds_agent.tools.verifier_tool")

        create_agent(
            provider=_mock_provider(),
            callbacks=MagicMock(),
            workspace_dir=str(tmp_path),
        )

        assert verifier_tool_module._container is not None
        assert verifier_tool_module._container.orchestrator._narrative._judge is not None
