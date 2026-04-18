"""Port: CodeExecutorPort — abstraction for sandboxed code execution.

The application layer depends only on this interface. Concrete implementations
(subprocess, Docker, Pyodide, …) live in infrastructure and are injected at
the composition root.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ds_agent.domain.entities.sandbox import SandboxExecutionResult, SandboxPolicy


class CodeExecutorPort(ABC):
    """Contract any sandboxed Python executor must honour."""

    @property
    @abstractmethod
    def policy(self) -> SandboxPolicy:
        """The policy this executor enforces."""

    @abstractmethod
    async def execute(
        self,
        code: str,
        *,
        timeout: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> SandboxExecutionResult:
        """Run `code` under the executor's policy.

        Implementations MUST:
        - Never raise on user-code errors; report them via the result object.
        - Enforce timeout and resource caps from the policy (or `timeout` override).
        - Collect policy violations in result.violations.
        """
