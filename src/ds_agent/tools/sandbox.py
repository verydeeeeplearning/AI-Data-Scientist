"""Process-based code sandbox for isolated Python execution."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from ds_agent.domain.entities.sandbox import (
    SandboxPolicy,
    SandboxViolation,
)

logger = structlog.get_logger()


def _build_exec_command(script_path: str) -> list[str]:
    """Build the subprocess argv for executing ``script_path``.

    In a PyInstaller frozen bundle ``sys.executable`` is the bootloader exe,
    not a Python interpreter — running it as ``exe script.py`` fails because
    its argparse rejects positional args. The bundle instead exposes a
    self-reexec subcommand (``--mode exec SCRIPT``) that runs the script
    using the embedded Python. See RFC_2026-04_sandbox_frozen_exec.md.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--mode", "exec", script_path]
    return [sys.executable, script_path]


@dataclass
class SandboxResult:
    """Result of sandbox code execution.

    Back-compat shape: boolean success, stdout/stderr/return_code.
    New fields (``violations``, ``execution_time_ms``) surface policy
    enforcement from the runtime preamble without breaking existing callers.
    """

    success: bool
    stdout: str
    stderr: str
    return_code: int
    files_created: list[str] | None = None
    violations: tuple[SandboxViolation, ...] = field(default_factory=tuple)
    execution_time_ms: int = 0


def create_secure_sandbox(
    timeout: int = 120,
    working_dir: str | None = None,
    *,
    policy: object | None = None,
    approval_store: object | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
    surface: str = "cli",
    emit_event: Callable[[str, dict[str, Any]], None] | None = None,
    approved: bool = False,
) -> ProcessSandbox:
    """Factory: create a ProcessSandbox with CodeSecurityChecker attached (SEC-05).

    If working_dir is not provided, falls back to the active workspace set by
    set_active_workspace() (3.4 fix: all DS tools get workspace-aware cwd).
    """
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


def create_sandbox(
    *,
    policy: object | None = None,
    timeout: int = 120,
    working_dir: str | None = None,
    approval_store: object | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
    surface: str = "cli",
    emit_event: Callable[[str, dict[str, Any]], None] | None = None,
    approved: bool = False,
) -> ProcessSandbox:
    """Create a policy-aware sandbox instance for the selected execution path."""
    from ds_agent.domain.value_objects.execution_policy import ExecutionPath, ExecutionPolicy
    from ds_agent.tools.code_security import CodeSecurityChecker
    from ds_agent.tools.path_utils import get_active_workspace

    effective_working_dir = working_dir
    if effective_working_dir is None:
        workspace = get_active_workspace()
        if workspace is not None:
            effective_working_dir = str(workspace)

    resolved_policy = (
        policy
        if isinstance(policy, ExecutionPolicy)
        else ExecutionPolicy(path=ExecutionPath.LOCAL)
    )

    if resolved_policy.path == ExecutionPath.WAREHOUSE:
        from ds_agent.tools.warehouse_sandbox import WarehouseRunnerSandbox

        return WarehouseRunnerSandbox(
            timeout=timeout,
            working_dir=effective_working_dir,
            allowed_modules=resolved_policy.allowed_modules,
        )

    if resolved_policy.path == ExecutionPath.NETWORK:
        from ds_agent.tools.network_sandbox import NetworkRunnerSandbox

        return NetworkRunnerSandbox(
            timeout=timeout,
            working_dir=effective_working_dir,
            allowed_modules=resolved_policy.allowed_modules,
            approval_store=approval_store,
            session_id=session_id,
            run_id=run_id,
            surface=surface,
            emit_event=emit_event,
            approved=approved or not resolved_policy.requires_approval,
            audit_required=resolved_policy.audit_required,
            allowed_domains=resolved_policy.allowed_domains,
        )

    checker = CodeSecurityChecker(
        workspace_dir=Path(effective_working_dir) if effective_working_dir else None
    )
    runtime_policy: SandboxPolicy | None = None
    if effective_working_dir:
        from ds_agent.tools.sandbox_context import resolve_policy

        runtime_policy = resolve_policy(
            Path(effective_working_dir),
            timeout=timeout,
        )
    return ProcessSandbox(
        timeout=timeout,
        working_dir=effective_working_dir,
        security_checker=checker,
        runtime_policy=runtime_policy,
    )


class ProcessSandbox:
    """Execute Python code in an isolated subprocess.

    Provides timeout, security checking, and basic isolation.
    For production use, consider Docker-based sandboxing.
    """

    def __init__(
        self,
        timeout: int = 120,
        working_dir: str | None = None,
        security_checker: Any | None = None,
        runtime_policy: SandboxPolicy | None = None,
    ) -> None:
        self._timeout = timeout
        self._working_dir = working_dir
        self._security = security_checker
        self._runtime_policy = runtime_policy

    async def execute(self, code: str, timeout: int | None = None) -> SandboxResult:
        """Execute Python code in a subprocess."""
        effective_timeout = timeout or self._timeout

        # Security check (if checker provided)
        if self._security is not None and hasattr(self._security, "check"):
            check_result = self._security.check(code)
            if not check_result.allowed:
                blocked = "; ".join(check_result.blocked_patterns)
                return SandboxResult(
                    success=False,
                    stdout="",
                    stderr=f"Security check failed: {blocked}",
                    return_code=-2,
                )
            if check_result.warnings:
                for warning in check_result.warnings:
                    # Defensive: logging can fail on Windows when stdout is
                    # cp949-encoded and the warning contains Unicode chars
                    # (em-dash, Korean, etc). Swallow encoding errors so a
                    # harmless warning never aborts the whole tool call.
                    with suppress(UnicodeEncodeError):
                        logger.warning("code_security_warning", warning=warning)

        wrapped_code = self._wrap_with_preamble(code)

        # Write code to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(wrapped_code)
            script_path = f.name

        started = time.monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                *_build_exec_command(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._working_dir,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=effective_timeout,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return SandboxResult(
                    success=False,
                    stdout="",
                    stderr=f"Execution timed out after {effective_timeout} seconds",
                    return_code=-1,
                    execution_time_ms=int((time.monotonic() - started) * 1000),
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr_raw = stderr_bytes.decode("utf-8", errors="replace")
            return_code = process.returncode or 0

            violations: tuple[SandboxViolation, ...] = ()
            if self._runtime_policy is not None:
                from ds_agent.infrastructure.sandbox.preamble import parse_violations

                violations, stderr_raw = parse_violations(stderr_raw)

            stderr = stderr_raw.strip()

            # Translate DS errors into actionable guidance
            if return_code != 0 and stderr:
                from ds_agent.tools.ds_error_translator import translate_error

                stderr = translate_error(stderr)

            blocked_present = any(v.blocked for v in violations)
            return SandboxResult(
                success=return_code == 0 and not blocked_present,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                violations=violations,
                execution_time_ms=int((time.monotonic() - started) * 1000),
            )

        finally:
            Path(script_path).unlink(missing_ok=True)

    def _wrap_with_preamble(self, code: str) -> str:
        """Inject runtime policy enforcement in front of user code."""
        if self._runtime_policy is None:
            return code
        from ds_agent.infrastructure.sandbox.preamble import build_preamble

        return build_preamble(self._runtime_policy, code)
