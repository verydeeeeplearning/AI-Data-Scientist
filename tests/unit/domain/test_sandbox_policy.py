"""Domain tests for SandboxPolicy allowlist semantics.

Pure-domain tests: no filesystem I/O, no subprocess.
Only tests path resolution and host-matching logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ds_agent.domain.entities.sandbox import (
    SandboxExecutionResult,
    SandboxPolicy,
    SandboxViolation,
    ViolationKind,
)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


class TestSandboxPolicyPaths:
    def test_workspace_root_allowed(self, workspace: Path):
        policy = SandboxPolicy(workspace_dir=workspace)
        assert policy.is_path_allowed(workspace) is True

    def test_file_inside_workspace_allowed(self, workspace: Path):
        policy = SandboxPolicy(workspace_dir=workspace)
        assert policy.is_path_allowed(workspace / "out.csv", mode="write") is True

    def test_nested_file_inside_workspace_allowed(self, workspace: Path):
        policy = SandboxPolicy(workspace_dir=workspace)
        assert policy.is_path_allowed(workspace / "sub" / "x.parquet") is True

    def test_outside_workspace_denied(self, workspace: Path, tmp_path: Path):
        policy = SandboxPolicy(workspace_dir=workspace)
        assert policy.is_path_allowed(tmp_path / "secret.docx") is False

    def test_path_traversal_blocked(self, workspace: Path, tmp_path: Path):
        policy = SandboxPolicy(workspace_dir=workspace)
        traversal = workspace / ".." / "secret.txt"
        assert policy.is_path_allowed(traversal) is False

    def test_data_dir_read_allowed(self, workspace: Path, data_dir: Path):
        policy = SandboxPolicy(workspace_dir=workspace, data_dirs=(data_dir,))
        assert policy.is_path_allowed(data_dir / "customers.csv", mode="read") is True

    def test_data_dir_write_denied(self, workspace: Path, data_dir: Path):
        policy = SandboxPolicy(workspace_dir=workspace, data_dirs=(data_dir,))
        assert policy.is_path_allowed(data_dir / "customers.csv", mode="write") is False

    def test_data_dir_readwrite_denied(self, workspace: Path, data_dir: Path):
        policy = SandboxPolicy(workspace_dir=workspace, data_dirs=(data_dir,))
        assert policy.is_path_allowed(data_dir / "x.csv", mode="readwrite") is False


class TestSandboxPolicyHosts:
    def test_empty_allowlist_denies_everything(self, workspace: Path):
        policy = SandboxPolicy(workspace_dir=workspace)
        assert policy.is_host_allowed("pypi.org") is False

    def test_exact_host_match(self, workspace: Path):
        policy = SandboxPolicy(workspace_dir=workspace, approved_hosts=("pypi.org",))
        assert policy.is_host_allowed("pypi.org") is True

    def test_subdomain_match(self, workspace: Path):
        policy = SandboxPolicy(workspace_dir=workspace, approved_hosts=("pypi.org",))
        assert policy.is_host_allowed("files.pypi.org") is True

    def test_unrelated_host_denied(self, workspace: Path):
        policy = SandboxPolicy(workspace_dir=workspace, approved_hosts=("pypi.org",))
        assert policy.is_host_allowed("evil.com") is False

    def test_substring_attack_denied(self, workspace: Path):
        # "mypypi.org" must NOT match "pypi.org"
        policy = SandboxPolicy(workspace_dir=workspace, approved_hosts=("pypi.org",))
        assert policy.is_host_allowed("evilpypi.org") is False

    def test_case_insensitive(self, workspace: Path):
        policy = SandboxPolicy(workspace_dir=workspace, approved_hosts=("PyPI.ORG",))
        assert policy.is_host_allowed("pypi.org") is True

    def test_empty_host(self, workspace: Path):
        policy = SandboxPolicy(workspace_dir=workspace, approved_hosts=("pypi.org",))
        assert policy.is_host_allowed("") is False


class TestSandboxViolation:
    def test_summary_blocked(self):
        v = SandboxViolation(
            kind=ViolationKind.FILESYSTEM,
            detail="write to /etc/passwd",
        )
        assert "blocked" in v.summary()
        assert "filesystem" in v.summary()

    def test_summary_allowed(self):
        v = SandboxViolation(
            kind=ViolationKind.NETWORK,
            detail="pypi.org request",
            blocked=False,
        )
        assert "allowed" in v.summary()


class TestSandboxExecutionResult:
    def test_success_no_violations(self):
        r = SandboxExecutionResult(
            stdout="hello",
            stderr="",
            exit_code=0,
            execution_time_ms=10,
        )
        assert r.success is True
        assert r.blocked_violations == ()

    def test_nonzero_exit_not_success(self):
        r = SandboxExecutionResult(stdout="", stderr="boom", exit_code=1, execution_time_ms=1)
        assert r.success is False

    def test_blocked_violation_not_success(self):
        r = SandboxExecutionResult(
            stdout="",
            stderr="",
            exit_code=0,
            execution_time_ms=1,
            violations=(
                SandboxViolation(kind=ViolationKind.FILESYSTEM, detail="x", blocked=True),
            ),
        )
        assert r.success is False
        assert len(r.blocked_violations) == 1

    def test_allowed_violation_still_success(self):
        r = SandboxExecutionResult(
            stdout="",
            stderr="",
            exit_code=0,
            execution_time_ms=1,
            violations=(
                SandboxViolation(kind=ViolationKind.NETWORK, detail="warn", blocked=False),
            ),
        )
        assert r.success is True
