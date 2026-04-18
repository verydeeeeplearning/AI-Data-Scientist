"""Tests for the process-global sandbox policy publisher."""

from __future__ import annotations

from pathlib import Path

import pytest

from ds_agent.domain.entities.sandbox import SandboxPolicy
from ds_agent.tools import sandbox_context


@pytest.fixture(autouse=True)
def _clear_active_policy():
    sandbox_context.set_active_sandbox_config(None)
    yield
    sandbox_context.set_active_sandbox_config(None)


def test_resolve_policy_returns_defaults_without_active_config(tmp_path: Path):
    policy = sandbox_context.resolve_policy(tmp_path)
    assert policy.workspace_dir == tmp_path
    assert policy.timeout_seconds == 120
    assert policy.block_subprocess is True
    assert policy.approved_hosts == ()
    assert policy.data_dirs == ()


def test_resolve_policy_honours_active_config(tmp_path: Path):
    data_dir = tmp_path / "data"
    active = SandboxPolicy(
        workspace_dir=tmp_path / "ignored",
        data_dirs=(data_dir,),
        approved_hosts=("pypi.org",),
        timeout_seconds=60,
        max_memory_mb=1024,
        block_subprocess=False,
    )
    sandbox_context.set_active_sandbox_config(active)

    actual_workspace = tmp_path / "actual"
    policy = sandbox_context.resolve_policy(actual_workspace)
    # workspace is overridden per-call
    assert policy.workspace_dir == actual_workspace
    # other fields come from the published policy
    assert policy.data_dirs == (data_dir,)
    assert policy.approved_hosts == ("pypi.org",)
    assert policy.timeout_seconds == 60
    assert policy.max_memory_mb == 1024
    assert policy.block_subprocess is False


def test_resolve_policy_per_call_timeout_override(tmp_path: Path):
    sandbox_context.set_active_sandbox_config(
        SandboxPolicy(workspace_dir=tmp_path, timeout_seconds=999)
    )
    policy = sandbox_context.resolve_policy(tmp_path, timeout=5)
    assert policy.timeout_seconds == 5


def test_get_and_set_roundtrip(tmp_path: Path):
    assert sandbox_context.get_active_sandbox_config() is None
    policy = SandboxPolicy(workspace_dir=tmp_path)
    sandbox_context.set_active_sandbox_config(policy)
    assert sandbox_context.get_active_sandbox_config() is policy
    sandbox_context.set_active_sandbox_config(None)
    assert sandbox_context.get_active_sandbox_config() is None
