"""Process-global sandbox policy state.

Mirrors the ``path_utils.set_active_workspace`` pattern: the composition
root publishes the active sandbox policy once at startup and every
tool-side sandbox factory reads it back without threading it through the
call stack.

Kept at module scope on purpose — ``ProcessSandbox`` and ``create_sandbox``
are invoked from many call sites (tools, distributed adapters, CLI glue)
where dependency-injection through every signature would be invasive. The
composition root in ``ds_agent.agent.factory.create_agent`` remains the
*only* caller of :func:`set_active_sandbox_config`.
"""

from __future__ import annotations

from pathlib import Path

from ds_agent.domain.entities.sandbox import SandboxPolicy

_active_config: SandboxPolicy | None = None


def set_active_sandbox_config(policy: SandboxPolicy | None) -> None:
    """Publish the active sandbox policy (called once at composition root)."""
    global _active_config
    _active_config = policy


def get_active_sandbox_config() -> SandboxPolicy | None:
    """Return the active sandbox policy, or None if not configured."""
    return _active_config


def resolve_policy(workspace_dir: Path, *, timeout: int | None = None) -> SandboxPolicy:
    """Build the effective ``SandboxPolicy`` for a given workspace.

    Preference order for each field:
    1. Value from the active ``SandboxPolicy`` published by composition root.
    2. Built-in safe defaults (120s timeout, 2GB memory, subprocess blocked,
       no approved hosts, no extra data dirs).

    ``workspace_dir`` always wins — the active config's workspace is ignored
    when a caller passes an explicit workspace (e.g. per-session workspaces).
    """
    base = _active_config
    if base is None:
        return SandboxPolicy(
            workspace_dir=workspace_dir,
            timeout_seconds=timeout or 120,
        )
    return SandboxPolicy(
        workspace_dir=workspace_dir,
        data_dirs=base.data_dirs,
        approved_hosts=base.approved_hosts,
        timeout_seconds=timeout or base.timeout_seconds,
        max_memory_mb=base.max_memory_mb,
        block_subprocess=base.block_subprocess,
    )
