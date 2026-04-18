"""Isolated subagent executor backed by a dedicated DSAgent instance."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable

from ds_agent.agent.callbacks import NullCallbacks
from ds_agent.agent.core import DSAgent
from ds_agent.agent.factory import build_hook_registry
from ds_agent.agent.prompt_builder import PromptBuilder
from ds_agent.application.services.subagent_orchestrator import SubagentResult
from ds_agent.domain.interfaces.llm_provider import AgentCallbacks, LLMProvider
from ds_agent.domain.interfaces.tool_registry import ToolRegistry
from ds_agent.domain.value_objects.budget import BudgetPolicy
from ds_agent.domain.value_objects.subagent import SubagentSpec


class ProcessSubagent:
    """Execute one subagent with isolated budget, timeout, and tool scope."""

    def __init__(
        self,
        *,
        provider_factory: Callable[[str | None], LLMProvider],
        tool_registry: ToolRegistry,
        workspace_dir: str | None = None,
        mode: str = "auto",
        default_budget_policy: BudgetPolicy | None = None,
        callbacks_factory: Callable[[SubagentSpec], AgentCallbacks] | None = None,
    ) -> None:
        self._provider_factory = provider_factory
        self._tool_registry = tool_registry
        self._workspace_dir = workspace_dir
        self._mode = mode
        self._default_budget_policy = default_budget_policy or BudgetPolicy()
        self._callbacks_factory = callbacks_factory

    async def execute(
        self,
        spec: SubagentSpec,
        *,
        run_id: str,
        context_summary: str | None = None,
        parent_session_id: str | None = None,
        parent_model: str | None = None,
    ) -> SubagentResult:
        """Execute one isolated subagent run."""
        started_at = time.time()
        requested_model = spec.model or parent_model
        provider = self._provider_factory(requested_model)
        session_id = self._resolve_session_id(
            spec,
            run_id=run_id,
            parent_session_id=parent_session_id,
        )
        callbacks = self._callbacks_factory(spec) if self._callbacks_factory else NullCallbacks()
        budget_policy = spec.build_budget_policy(self._default_budget_policy)
        scoped_tools = _ScopedToolRegistry(self._tool_registry, spec.tools)
        model_name = self._resolve_model_name(provider, requested_model)
        agent = DSAgent(
            provider=provider,
            tool_registry=scoped_tools,
            budget_policy=budget_policy,
            callbacks=callbacks,
            prompt_builder=PromptBuilder(
                tool_registry=scoped_tools,
                model_name=model_name,
                workspace_dir=self._workspace_dir,
                session_id=session_id,
            ),
            hook_registry=build_hook_registry(max_cost_usd=budget_policy.max_cost_usd),
            mode=self._mode,
            session_id=session_id,
        )
        agent.set_runtime_context(run_id=run_id, surface="subagent")
        payload = spec.build_prompt(context_summary=context_summary)

        try:
            output = await asyncio.wait_for(
                agent.run(
                    payload,
                    execution_mode="background",
                    budget_policy=budget_policy,
                ),
                timeout=spec.timeout_seconds,
            )
            status = "completed"
            error = None
        except TimeoutError:
            output = "Subagent execution timed out."
            status = "timed_out"
            error = "timeout"
        except Exception as exc:
            output = ""
            status = "failed"
            error = str(exc)

        completed_at = time.time()
        budget_summary = agent._budget.get_summary()
        return SubagentResult(
            run_id=run_id,
            spec=spec,
            status=status,  # type: ignore[arg-type]
            output=output,
            session_id=session_id,
            model=model_name,
            started_at=started_at,
            completed_at=completed_at,
            budget_summary=budget_summary,
            error=error,
        )

    @staticmethod
    def _resolve_session_id(
        spec: SubagentSpec,
        *,
        run_id: str,
        parent_session_id: str | None,
    ) -> str:
        if spec.session_target in {"main", "current"} and parent_session_id:
            return parent_session_id
        base = parent_session_id or "subagent"
        return f"{base}:subagent:{spec.role}:{run_id}"

    @staticmethod
    def _resolve_model_name(provider: LLMProvider, requested_model: str | None) -> str:
        if requested_model:
            return requested_model
        try:
            return provider.get_model_info().model_id
        except Exception:
            return "unknown"


class _ScopedToolRegistry:
    """Restrict tool visibility for one subagent run."""

    def __init__(self, base_registry: ToolRegistry, allowed_tools: list[str] | None) -> None:
        self._base_registry = base_registry
        self._allowed_tools = None if allowed_tools is None else set(allowed_tools)

    def get_definitions(self) -> list[dict]:
        definitions = self._base_registry.get_definitions()
        if self._allowed_tools is None:
            return definitions
        filtered: list[dict] = []
        for item in definitions:
            function = item.get("function", {})
            name = function.get("name")
            if isinstance(name, str) and name in self._allowed_tools:
                filtered.append(item)
        return filtered

    async def dispatch(self, name: str, arguments: dict) -> str:
        if self._allowed_tools is not None and name not in self._allowed_tools:
            return json.dumps(
                {
                    "error": f"Tool not allowed for subagent: {name}",
                    "allowed_tools": sorted(self._allowed_tools),
                }
            )
        return await self._base_registry.dispatch(name, arguments)
