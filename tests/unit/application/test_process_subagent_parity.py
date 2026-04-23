"""Focused tests for ProcessSubagent construction parity."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import ds_agent.infrastructure.process_subagent as module
from ds_agent.domain.value_objects.budget import BudgetPolicy
from ds_agent.domain.value_objects.subagent import SubagentSpec
from ds_agent.infrastructure.process_subagent import ProcessSubagent


@pytest.mark.asyncio
async def test_process_subagent_wires_task_contract_and_verifier_runtime(monkeypatch):
    workspace_dir = str((Path.cwd() / ".tmp" / "process-subagent-parity").resolve())
    captured: dict[str, object] = {}
    task_contract_store = object()
    record_review_verdict = object()
    verifier_orchestrator = object()
    task_contract_container = SimpleNamespace(
        store=task_contract_store,
        record_review_verdict=record_review_verdict,
    )
    verifier_container = SimpleNamespace(orchestrator=verifier_orchestrator)
    certification_store = object()
    policy_store = object()
    hook_registry = object()

    class FakePromptBuilder:
        def __init__(self, **kwargs):
            captured["prompt_builder_kwargs"] = kwargs
            self._task_contract_store = kwargs.get("task_contract_store")
            self._tool_registry = kwargs.get("tool_registry")

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent_init_kwargs"] = kwargs
            self._budget = SimpleNamespace(
                get_summary=lambda: {
                    "total_cost_usd": 0.0,
                    "max_cost_usd": kwargs["budget_policy"].max_cost_usd,
                    "is_exhausted": False,
                }
            )

        def set_runtime_context(self, run_id=None, surface=None):
            captured["runtime_context"] = {
                "run_id": run_id,
                "surface": surface,
            }

        async def run(self, payload, execution_mode=None, budget_policy=None):
            captured["run_call"] = {
                "payload": payload,
                "execution_mode": execution_mode,
                "budget_policy": budget_policy,
            }
            return "subagent-complete"

    def fake_build_hook_registry(*args, **kwargs):
        captured["hook_registry_args"] = {
            "args": args,
            "kwargs": kwargs,
        }
        return hook_registry

    def fake_build_task_contract_container(workspace_dir_arg, *, llm_provider=None):
        captured["task_contract_container_args"] = {
            "workspace_dir": workspace_dir_arg,
            "llm_provider": llm_provider,
        }
        return task_contract_container

    def fake_build_verifier_container(
        workspace_dir_arg,
        *,
        llm_provider=None,
        mission_loader=None,
    ):
        captured["verifier_container_args"] = {
            "workspace_dir": workspace_dir_arg,
            "llm_provider": llm_provider,
            "mission_loader": mission_loader,
        }
        return verifier_container

    monkeypatch.setattr(module, "PromptBuilder", FakePromptBuilder)
    monkeypatch.setattr(module, "DSAgent", FakeAgent)
    monkeypatch.setattr(module, "build_hook_registry", fake_build_hook_registry)
    monkeypatch.setattr(
        module,
        "build_task_contract_container",
        fake_build_task_contract_container,
    )
    monkeypatch.setattr(
        module,
        "build_verifier_container",
        fake_build_verifier_container,
    )
    monkeypatch.setattr(
        module,
        "set_task_contract_container",
        lambda container: captured.setdefault("wired_task_contract_container", container),
    )
    monkeypatch.setattr(
        module,
        "set_verifier_container",
        lambda container: captured.setdefault("wired_verifier_container", container),
    )
    monkeypatch.setattr(
        module,
        "set_active_workspace",
        lambda path: captured.setdefault("active_workspace", path),
    )
    monkeypatch.setattr(module, "_verifier_auto_run_mode", lambda: "shadow")

    class FakeCertificationStore:
        @classmethod
        def for_workspace(cls, workspace_dir_arg=None):
            captured["certification_workspace"] = workspace_dir_arg
            return certification_store

    monkeypatch.setattr(module, "SqliteCertificationStore", FakeCertificationStore)
    monkeypatch.setattr(
        module,
        "JsonPolicyStore",
        lambda workspace_dir_arg=None: (
            captured.setdefault("policy_workspace", workspace_dir_arg),
            policy_store,
        )[1],
    )

    provider = MagicMock(name="provider")
    base_registry = MagicMock()
    base_registry.get_definitions.return_value = [
        {"function": {"name": "allowed_tool"}},
        {"function": {"name": "blocked_tool"}},
    ]
    base_registry.dispatch = AsyncMock(return_value='{"ok": true}')

    executor = ProcessSubagent(
        provider_factory=lambda model_name: provider,
        tool_registry=base_registry,
        workspace_dir=workspace_dir,
        mode="review",
        default_budget_policy=BudgetPolicy(max_iterations=7, max_cost_usd=4.0),
    )

    result = await executor.execute(
        SubagentSpec(
            role="validator",
            prompt="Validate the parent result.",
            tools=["allowed_tool"],
            budget_usd=0.25,
            model="gpt-test",
        ),
        run_id="run-123",
        context_summary="Parent context",
        parent_session_id="session-main",
    )

    assert result.status == "completed"
    assert result.output == "subagent-complete"
    assert result.model == "gpt-test"
    assert captured["task_contract_container_args"] == {
        "workspace_dir": workspace_dir,
        "llm_provider": provider,
    }
    assert captured["wired_task_contract_container"] is task_contract_container
    assert captured["wired_verifier_container"] is verifier_container
    assert captured["certification_workspace"] == workspace_dir
    assert captured["policy_workspace"] == workspace_dir
    assert captured["active_workspace"] == Path(workspace_dir).expanduser().resolve()

    prompt_builder_kwargs = captured["prompt_builder_kwargs"]
    assert prompt_builder_kwargs["task_contract_store"] is task_contract_store
    assert prompt_builder_kwargs["legacy_agent_mode"] == "review"
    assert prompt_builder_kwargs["session_id"] == "session-main:subagent:validator:run-123"

    hook_registry_kwargs = captured["hook_registry_args"]["kwargs"]
    assert hook_registry_kwargs["workspace_dir"] == workspace_dir
    assert hook_registry_kwargs["task_contract_store"] is task_contract_store
    assert hook_registry_kwargs["certification_store"] is certification_store
    assert hook_registry_kwargs["policy_store"] is policy_store
    assert hook_registry_kwargs["verifier_orchestrator"] is verifier_orchestrator
    assert hook_registry_kwargs["record_review_verdict"] is record_review_verdict
    assert hook_registry_kwargs["auto_verifier_mode"] == "shadow"
    assert (
        hook_registry_kwargs["mission_loader"]
        is captured["verifier_container_args"]["mission_loader"]
    )

    agent_init_kwargs = captured["agent_init_kwargs"]
    assert agent_init_kwargs["hook_registry"] is hook_registry
    assert agent_init_kwargs["mode"] == "review"
    assert agent_init_kwargs["session_id"] == "session-main:subagent:validator:run-123"

    scoped_tools = agent_init_kwargs["tool_registry"]
    assert scoped_tools.get_definitions() == [{"function": {"name": "allowed_tool"}}]
    denied = await scoped_tools.dispatch("blocked_tool", {})
    assert "Tool not allowed for subagent: blocked_tool" in denied
    allowed = await scoped_tools.dispatch("allowed_tool", {})
    assert allowed == '{"ok": true}'
    base_registry.dispatch.assert_awaited_once_with("allowed_tool", {})

    assert captured["runtime_context"] == {"run_id": "run-123", "surface": "subagent"}
    assert captured["run_call"]["execution_mode"] == "background"
    assert captured["run_call"]["budget_policy"].max_cost_usd == 0.25
    assert "Subagent role: validator" in captured["run_call"]["payload"]
