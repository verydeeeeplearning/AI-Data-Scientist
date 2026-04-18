"""ExecutionRouter tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from ds_agent.application.ports.sandbox_port import SandboxPort
from ds_agent.domain.value_objects.execution_policy import ExecutionPath, ExecutionPolicy
from ds_agent.tools.network_sandbox import NetworkRunnerSandbox
from ds_agent.tools.sandbox import ProcessSandbox
from ds_agent.tools.warehouse_sandbox import WarehouseRunnerSandbox


class _SpyFactory:
    """Minimal SandboxFactoryPort implementation for injection tests."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create_sandbox(
        self,
        *,
        policy: ExecutionPolicy,
        timeout: int = 120,
        working_dir: str | None = None,
        approval_store: object | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        surface: str = "cli",
        emit_event: Callable[[str, dict[str, Any]], None] | None = None,
        approved: bool = False,
    ) -> SandboxPort:
        self.calls.append(
            {
                "policy": policy,
                "timeout": timeout,
                "working_dir": working_dir,
            }
        )

        class _Stub:
            async def execute(self, code: str, timeout: int | None = None) -> Any:
                return None

        return _Stub()


class TestExecutionRouter:
    def test_maps_tool_names_to_expected_paths(self) -> None:
        from ds_agent.application.services.execution_router import ExecutionRouter

        router = ExecutionRouter()

        assert router.policy_for_tool("execute_code").path == ExecutionPath.LOCAL
        assert router.policy_for_tool("sql_query").path == ExecutionPath.WAREHOUSE
        assert router.policy_for_tool("web_search").path == ExecutionPath.NETWORK

    def test_creates_expected_sandbox_for_tool(self) -> None:
        """Router delegates construction to the injected SandboxFactoryPort."""
        from ds_agent.application.services.execution_router import ExecutionRouter
        from ds_agent.infrastructure.sandbox.sandbox_factory import ProcessSandboxFactory

        router = ExecutionRouter(sandbox_factory=ProcessSandboxFactory())

        local_sandbox = router.create_sandbox_for_tool("execute_code", timeout=5)
        warehouse_sandbox = router.create_sandbox_for_tool("sql_query", timeout=5)
        network_sandbox = router.create_sandbox_for_tool("web_search", timeout=5)

        assert isinstance(local_sandbox, ProcessSandbox)
        assert not isinstance(local_sandbox, WarehouseRunnerSandbox | NetworkRunnerSandbox)
        assert isinstance(warehouse_sandbox, WarehouseRunnerSandbox)
        assert isinstance(network_sandbox, NetworkRunnerSandbox)

    def test_router_accepts_any_sandbox_factory_port_implementation(self) -> None:
        """Dependency-injection contract: any object satisfying SandboxFactoryPort works."""
        from ds_agent.application.services.execution_router import ExecutionRouter

        factory = _SpyFactory()
        router = ExecutionRouter(sandbox_factory=factory)

        sandbox = router.create_sandbox_for_tool("sql_query", timeout=7, working_dir="/tmp")

        assert len(factory.calls) == 1
        call = factory.calls[0]
        assert call["policy"].path == ExecutionPath.WAREHOUSE
        assert call["timeout"] == 7
        assert call["working_dir"] == "/tmp"
        # The returned object is the opaque SandboxPort the factory produced,
        # not a concrete tools/infrastructure class referenced by the router.
        assert hasattr(sandbox, "execute")

    def test_router_raises_when_factory_missing_on_sandbox_call(self) -> None:
        """policy_for_tool works without a factory; create_sandbox_for_tool requires one."""
        from ds_agent.application.services.execution_router import ExecutionRouter

        router = ExecutionRouter()  # no factory injected

        # Pure policy resolution still works — no sandbox needed.
        assert router.policy_for_tool("execute_code").path == ExecutionPath.LOCAL

        # But asking for a sandbox without a factory is an explicit programming error.
        with pytest.raises(RuntimeError, match="SandboxFactoryPort"):
            router.create_sandbox_for_tool("execute_code", timeout=5)
