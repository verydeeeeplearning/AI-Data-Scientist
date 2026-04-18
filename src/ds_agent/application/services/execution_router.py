"""Execution router for mapping tools to isolated runner policies.

This service lives strictly in the application layer: it resolves an
:class:`ExecutionPolicy` for a tool name and — when the caller asks for a
concrete sandbox instance — delegates construction to an injected
:class:`SandboxFactoryPort`. The router itself never imports any
``ds_agent.tools.*`` or ``ds_agent.infrastructure.*`` module.

Composition-root binding (``agent/factory.py``, tests) wires the concrete
factory adapter (``ds_agent.infrastructure.sandbox.sandbox_factory``) to
the router.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ds_agent.application.ports.sandbox_port import SandboxFactoryPort, SandboxPort
from ds_agent.domain.value_objects.execution_policy import ExecutionPath, ExecutionPolicy

_WAREHOUSE_ALLOWED_MODULES = (
    "snowflake.connector",
    "google.cloud.bigquery",
    "psycopg2",
    "pandas",
    "numpy",
)

_NETWORK_ALLOWED_MODULES = (
    "requests",
    "httpx",
)

_LOCAL_TOOLS = frozenset(
    {
        "execute_code",
        "data_loader",
        "data_profiler",
        "run_eda",
        "feature_engineer",
        "train_model",
        "evaluate_model",
        "generate_report",
        "generate_deployment",
        "read_file",
        "write_file",
        "list_files",
        "memory_search",
        "memory_store",
        "skill_list",
        "skill_view",
        "skill_search",
        "load_semantic_pack",
        "drift_monitor",
        "ab_test",
        "ask_user",
        "distributed_exec",
    }
)

_WAREHOUSE_TOOLS = frozenset({"sql_query", "schema_inspect", "data_catalog_search"})
_NETWORK_TOOLS = frozenset({"web_search"})


class ExecutionRouter:
    """Resolve execution policy and create sandboxes for a tool.

    The router depends only on :class:`SandboxFactoryPort` (a Protocol in
    the application layer). The concrete adapter is supplied at the
    composition root, preserving the Dependency Rule.
    """

    def __init__(self, sandbox_factory: SandboxFactoryPort | None = None) -> None:
        self._sandbox_factory = sandbox_factory

    def policy_for_tool(self, tool_name: str) -> ExecutionPolicy:
        if tool_name in _WAREHOUSE_TOOLS:
            return ExecutionPolicy(
                path=ExecutionPath.WAREHOUSE,
                allowed_modules=_WAREHOUSE_ALLOWED_MODULES,
            )
        if tool_name in _NETWORK_TOOLS:
            return ExecutionPolicy(
                path=ExecutionPath.NETWORK,
                allowed_modules=_NETWORK_ALLOWED_MODULES,
                requires_approval=True,
                audit_required=True,
            )
        if tool_name in _LOCAL_TOOLS:
            return ExecutionPolicy(path=ExecutionPath.LOCAL)
        return ExecutionPolicy(path=ExecutionPath.LOCAL)

    def create_sandbox_for_tool(
        self,
        tool_name: str,
        *,
        timeout: int = 120,
        working_dir: str | None = None,
        approval_store: object | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        surface: str = "cli",
        emit_event: Callable[[str, dict[str, Any]], None] | None = None,
        approved: bool = False,
    ) -> SandboxPort:
        if self._sandbox_factory is None:
            raise RuntimeError(
                "ExecutionRouter cannot create a sandbox without a SandboxFactoryPort. "
                "Inject one at construction time (see agent/factory.py for the "
                "composition-root wiring)."
            )
        policy = self.policy_for_tool(tool_name)
        return self._sandbox_factory.create_sandbox(
            policy=policy,
            timeout=timeout,
            working_dir=working_dir,
            approval_store=approval_store,
            session_id=session_id,
            run_id=run_id,
            surface=surface,
            emit_event=emit_event,
            approved=approved,
        )
