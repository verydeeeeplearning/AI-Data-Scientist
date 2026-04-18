"""Sandbox domain entities — policy, violation, execution result.

These entities define *what* the sandbox must enforce. The enforcement
mechanism itself lives in the infrastructure layer.

Pure domain: no subprocess, no filesystem I/O, no framework dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal


class ViolationKind(StrEnum):
    """Types of sandbox policy violations."""

    FILESYSTEM = "filesystem"
    NETWORK = "network"
    SUBPROCESS = "subprocess"
    RESOURCE = "resource"


@dataclass(frozen=True, slots=True)
class SandboxViolation:
    """A single policy breach detected during code execution."""

    kind: ViolationKind
    detail: str
    blocked: bool = True

    def summary(self) -> str:
        state = "blocked" if self.blocked else "allowed"
        return f"[{self.kind.value}:{state}] {self.detail}"


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    """Allowlist-based policy for code execution.

    workspace_dir: read/write root. Any file I/O outside this root is blocked
        unless the path is also under a read-only data dir.
    data_dirs: read-only allowlist (uploaded datasets, shared read-only inputs).
    approved_hosts: network hosts the agent may contact without prompting.
    timeout_seconds / max_memory_mb: resource caps enforced by the executor.
    block_subprocess: when True, any subprocess.Popen/os.system/os.exec is blocked.
    """

    workspace_dir: Path
    data_dirs: tuple[Path, ...] = field(default_factory=tuple)
    approved_hosts: tuple[str, ...] = field(default_factory=tuple)
    timeout_seconds: int = 120
    max_memory_mb: int = 2048
    block_subprocess: bool = True

    def _resolve(self, p: Path) -> Path:
        return Path(p).expanduser().resolve()

    def is_path_allowed(
        self,
        path: Path | str,
        mode: Literal["read", "write", "readwrite"] = "readwrite",
    ) -> bool:
        """Return True iff `path` may be accessed in the given mode."""
        target = self._resolve(Path(path))
        workspace = self._resolve(self.workspace_dir)
        if target == workspace or _is_within(target, workspace):
            return True
        if mode == "read":
            for d in self.data_dirs:
                allowed_root = self._resolve(d)
                if target == allowed_root or _is_within(target, allowed_root):
                    return True
        return False

    def is_host_allowed(self, host: str) -> bool:
        """Return True iff an outbound request to `host` is pre-approved.

        Suffix match on hostname: "pypi.org" allows "files.pypi.org".
        """
        if not host:
            return False
        host = host.lower().rstrip(".")
        for allowed in self.approved_hosts:
            allowed = allowed.lower().rstrip(".")
            if host == allowed or host.endswith("." + allowed):
                return True
        return False


def _is_within(child: Path, parent: Path) -> bool:
    """True if `child` is strictly inside `parent`. Uses resolved absolute paths."""
    try:
        return child.is_relative_to(parent) and child != parent
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class SandboxExecutionResult:
    """Outcome of a single sandboxed code run."""

    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: int
    violations: tuple[SandboxViolation, ...] = field(default_factory=tuple)

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not any(v.blocked for v in self.violations)

    @property
    def blocked_violations(self) -> tuple[SandboxViolation, ...]:
        return tuple(v for v in self.violations if v.blocked)
