"""Shared sandbox execution helper for DS tools.

All 8 DS tools use the same pattern: build code, run in sandbox, return stdout or error.
This module centralises that pattern to eliminate duplication.
"""

from __future__ import annotations

import json
import time
from contextlib import suppress
from dataclasses import replace

import structlog

from ds_agent.application.services.execution_router import ExecutionRouter
from ds_agent.domain.value_objects.execution_policy import ExecutionPath
from ds_agent.runtime.tool_runtime_context import get_tool_runtime_context
from ds_agent.tools.path_utils import get_active_workspace
from ds_agent.tools.sandbox import create_secure_sandbox

logger = structlog.get_logger()


async def run_ds_sandbox(
    code: str,
    *,
    tool_name: str,
    timeout: int,
    success_default: str | None = None,
) -> str:
    """Execute Python code in a secure sandbox with standardised error handling.

    Args:
        code: Python code to execute (full script or preamble + user code).
        tool_name: Identifies the caller in error payloads.
        timeout: Maximum execution time in seconds.
        success_default: Message returned when execution succeeds but stdout is empty.

    Returns:
        Stdout string on success.
        JSON ``{"error": ..., "tool": ...}`` string on failure.
    """
    runtime_context = get_tool_runtime_context()
    workspace = get_active_workspace()
    policy = ExecutionRouter().policy_for_tool(tool_name)
    skill_hub = getattr(runtime_context, "skill_hub", None)
    if skill_hub is not None and hasattr(skill_hub, "get_effective_permissions_for_tool"):
        permissions = skill_hub.get_effective_permissions_for_tool(tool_name)
        allowed_domains = tuple(permissions.get("network", []))
        if allowed_domains:
            if policy.path == ExecutionPath.NETWORK:
                policy = replace(
                    policy,
                    requires_approval=False,
                    audit_required=True,
                    allowed_domains=allowed_domains,
                )
            else:
                policy = replace(
                    policy,
                    path=ExecutionPath.NETWORK,
                    allowed_modules=("requests", "httpx"),
                    requires_approval=False,
                    audit_required=True,
                    allowed_domains=allowed_domains,
                )
    sandbox = create_secure_sandbox(
        timeout=timeout,
        working_dir=str(workspace) if workspace is not None else None,
        policy=policy,
        approval_store=getattr(runtime_context, "approval_store", None),
        session_id=getattr(runtime_context, "session_id", None),
        run_id=getattr(runtime_context, "run_id", None),
        surface=getattr(runtime_context, "surface", "cli"),
        emit_event=getattr(runtime_context, "emit_event", None),
    )
    result = await sandbox.execute(code)

    emit_event = getattr(runtime_context, "emit_event", None)
    if callable(emit_event):
        for violation in getattr(result, "violations", ()) or ():
            with suppress(Exception):
                emit_event(
                    "sandbox.violation",
                    {
                        "kind": violation.kind.value,
                        "detail": violation.detail,
                        "blocked": violation.blocked,
                        "sessionId": getattr(runtime_context, "session_id", None),
                        "runId": getattr(runtime_context, "run_id", None),
                        "tool": tool_name,
                        "timestamp": time.time(),
                    },
                )

    if result.success:
        return result.stdout or success_default or f"{tool_name} completed."

    # Log the failure so backend operators can see what the subprocess
    # actually printed to stderr — otherwise the only visibility is in the
    # JSON response streamed back to the LLM.
    stderr = result.stderr or "(no stderr)"
    try:
        logger.error(
            "ds_sandbox_failed",
            tool=tool_name,
            return_code=result.return_code,
            stderr=stderr[:2000],
        )
    except UnicodeEncodeError:
        with suppress(Exception):
            logger.error(
                "ds_sandbox_failed",
                tool=tool_name,
                return_code=result.return_code,
                stderr=stderr.encode("ascii", errors="replace").decode("ascii")[:2000],
            )

    return json.dumps({"error": stderr, "tool": tool_name})
