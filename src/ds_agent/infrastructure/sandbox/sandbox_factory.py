"""Infrastructure adapter implementing :class:`SandboxFactoryPort`.

The adapter is a thin indirection: it delegates to
``ds_agent.tools.sandbox.create_sandbox`` (the existing factory
function) and exposes it through the
:class:`~ds_agent.application.ports.sandbox_port.SandboxFactoryPort`
Protocol so the application layer can depend on an abstraction rather
than a concrete ``ds_agent.tools.*`` / ``ds_agent.infrastructure.*``
module.

This is the only place in the repository that bridges the application
layer to the concrete sandbox implementation; the composition root
(``ds_agent.agent.factory``) wires it to
:class:`~ds_agent.application.services.execution_router.ExecutionRouter`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ds_agent.application.ports.sandbox_port import SandboxPort
from ds_agent.domain.value_objects.execution_policy import ExecutionPolicy


class ProcessSandboxFactory:
    """Adapter that satisfies :class:`SandboxFactoryPort`.

    All keyword arguments are forwarded verbatim to
    ``ds_agent.tools.sandbox.create_sandbox`` so the behaviour is
    byte-identical to the pre-inversion direct call.
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
        # Imported lazily so this module — and therefore the application
        # layer when it type-checks against the port — stays decoupled
        # from the tools package until an adapter is actually constructed.
        from ds_agent.tools.sandbox import create_sandbox

        return create_sandbox(
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
