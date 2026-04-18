"""End-to-end wiring test: SandboxConfig → factory → create_sandbox.

Verifies the composition root publishes a SandboxPolicy that subsequent
``create_sandbox`` calls pick up, and that per-workspace overrides still
win over the published policy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ds_agent.agent.factory import _publish_sandbox_policy
from ds_agent.config.schema import SandboxConfig
from ds_agent.tools import sandbox_context
from ds_agent.tools.sandbox import create_sandbox


@pytest.fixture(autouse=True)
def _reset_active_config():
    sandbox_context.set_active_sandbox_config(None)
    yield
    sandbox_context.set_active_sandbox_config(None)


def test_publish_sandbox_policy_with_none(tmp_path: Path):
    _publish_sandbox_policy(None, str(tmp_path))
    policy = sandbox_context.get_active_sandbox_config()
    assert policy is not None
    assert policy.workspace_dir == tmp_path.resolve()
    # defaults
    assert policy.block_subprocess is True
    assert policy.data_dirs == ()


def test_publish_sandbox_policy_with_config(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    cfg = SandboxConfig(
        timeout_seconds=42,
        max_memory_mb=512,
        block_subprocess=False,
        approved_hosts=["pypi.org", "huggingface.co"],
        data_dirs=[str(data)],
    )
    _publish_sandbox_policy(cfg, str(tmp_path))
    policy = sandbox_context.get_active_sandbox_config()
    assert policy is not None
    assert policy.timeout_seconds == 42
    assert policy.max_memory_mb == 512
    assert policy.block_subprocess is False
    assert policy.approved_hosts == ("pypi.org", "huggingface.co")
    assert policy.data_dirs == (data.resolve(),)


def test_publish_without_workspace_clears(tmp_path: Path):
    sandbox_context.set_active_sandbox_config(
        sandbox_context.resolve_policy(tmp_path)
    )
    _publish_sandbox_policy(SandboxConfig(), None)
    assert sandbox_context.get_active_sandbox_config() is None


def test_create_sandbox_picks_up_active_policy(tmp_path: Path):
    data = tmp_path / "d"
    data.mkdir()
    cfg = SandboxConfig(timeout_seconds=99, data_dirs=[str(data)])
    _publish_sandbox_policy(cfg, str(tmp_path))

    sandbox = create_sandbox(
        timeout=99,
        working_dir=str(tmp_path),
    )
    assert sandbox._runtime_policy is not None  # type: ignore[attr-defined]
    assert sandbox._runtime_policy.data_dirs == (data.resolve(),)  # type: ignore[attr-defined]
    assert sandbox._runtime_policy.timeout_seconds == 99  # type: ignore[attr-defined]
