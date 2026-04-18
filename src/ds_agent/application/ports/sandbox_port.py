"""Port: ``SandboxPort`` and ``SandboxFactoryPort`` — abstractions for the
process-isolated sandbox used by :class:`ExecutionRouter`.

The application layer depends only on these Protocols. Concrete sandbox
implementations (process-based, warehouse-runner, network-runner) live in
``ds_agent.tools`` / ``ds_agent.infrastructure`` and are wired at the
composition root.

Why the two-port split:

* :class:`SandboxPort` describes **one** running sandbox instance — its
  only observable capability is to execute code and return a result.
* :class:`SandboxFactoryPort` describes the factory that builds a
  :class:`SandboxPort` for a given :class:`ExecutionPolicy`. The router
  resolves a policy, then delegates construction to the factory.

This keeps the application layer free of any ``ds_agent.tools.*`` /
``ds_agent.infrastructure.*`` import, which is what the
``application_independence_from_infrastructure`` import-linter contract
enforces.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from ds_agent.domain.value_objects.execution_policy import ExecutionPolicy


@runtime_checkable
class SandboxPort(Protocol):
    """Contract any sandbox instance (local / warehouse / network) must honour.

    The concrete return type of :meth:`execute` is an adapter-layer value
    (``SandboxResult`` or a subclass). The application layer stays agnostic
    of that shape — callers that need the detailed fields obtain them from
    the adapter-owned value object directly.
    """

    async def execute(self, code: str, timeout: int | None = None) -> Any:
        """Run ``code`` inside the sandbox and return the adapter-level result."""


@runtime_checkable
class SandboxFactoryPort(Protocol):
    """Contract any sandbox factory must honour.

    The factory constructs a :class:`SandboxPort` suitable for ``policy``.
    It is the only dependency :class:`ExecutionRouter` needs to create a
    sandbox for a tool; no concrete infrastructure/tools import is made
    from the application layer.
    """

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
        """Return a :class:`SandboxPort` configured for ``policy``."""
