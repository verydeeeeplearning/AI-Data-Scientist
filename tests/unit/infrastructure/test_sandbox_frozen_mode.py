"""Verify ProcessSandbox detects PyInstaller frozen mode and invokes the
self-reexec subcommand instead of trying to run ``sys.executable script.py``
(which is broken in frozen mode — the bootloader's argparse rejects
positional args).

RFC: Docs/rfc/RFC_2026-04_sandbox_frozen_exec.md
"""

from __future__ import annotations

import sys

from ds_agent.tools.sandbox import _build_exec_command


def test_non_frozen_returns_direct_invocation(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    cmd = _build_exec_command("/tmp/probe.py")
    assert cmd == [sys.executable, "/tmp/probe.py"]


def test_frozen_returns_self_reexec_subcommand(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    cmd = _build_exec_command("/tmp/probe.py")
    assert cmd == [sys.executable, "--mode", "exec", "/tmp/probe.py"]


def test_frozen_with_attribute_false_is_non_frozen(monkeypatch) -> None:
    # Setting sys.frozen = False should behave like source mode
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    cmd = _build_exec_command("X.py")
    assert "--mode" not in cmd


def test_frozen_absent_attr_is_non_frozen(monkeypatch) -> None:
    # Source mode — sys.frozen is typically not set
    monkeypatch.delattr(sys, "frozen", raising=False)
    cmd = _build_exec_command("X.py")
    assert "--mode" not in cmd
