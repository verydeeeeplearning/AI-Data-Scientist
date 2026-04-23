"""CLI subcommand tests: ``ds-agent open`` / ``ds-agent share`` (PLAN_03 sp3.3)."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from ds_agent.cli.commands import run_open_command, run_share_command


def _console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, force_terminal=False, width=200), buf


class TestRunOpenCommand:
    def test_rejects_missing_uri(self) -> None:
        console, _ = _console()
        rc = run_open_command([], console=console)
        assert rc == 2

    def test_rejects_invalid_uri_without_calling_launcher(self) -> None:
        called: list[str] = []

        def launcher(uri: str) -> int:
            called.append(uri)
            return 0

        console, buf = _console()
        rc = run_open_command(
            ["http://workspace/ws-1/run/r-1"], console=console, launcher=launcher
        )
        assert rc == 1
        assert called == [], "launcher must not be invoked for invalid URIs"
        assert "Invalid deep link" in buf.getvalue()

    def test_invokes_launcher_for_valid_uri(self) -> None:
        seen: list[str] = []

        def launcher(uri: str) -> int:
            seen.append(uri)
            return 0

        console, buf = _console()
        rc = run_open_command(
            ["ds-agent://workspace/ws-1/run/r-1"], console=console, launcher=launcher
        )
        assert rc == 0
        assert seen == ["ds-agent://workspace/ws-1/run/r-1"]
        assert "Opened" in buf.getvalue()

    def test_propagates_nonzero_launcher_rc(self) -> None:
        console, _ = _console()
        rc = run_open_command(
            ["ds-agent://workspace/ws-1/run/r-1"],
            console=console,
            launcher=lambda _u: 7,
        )
        assert rc == 7


class TestRunShareCommand:
    def test_requires_two_positional_args(self) -> None:
        console, _ = _console()
        assert run_share_command([], console=console) == 2
        assert run_share_command(["run"], console=console) == 2

    def test_builds_uri_with_default_workspace(self) -> None:
        copied: list[str] = []

        def fake_clipboard(text: str) -> bool:
            copied.append(text)
            return True

        console, buf = _console()
        rc = run_share_command(
            ["run", "r-1"],
            console=console,
            default_workspace_id="ws-default",
            clipboard=fake_clipboard,
        )
        assert rc == 0
        assert copied == ["ds-agent://workspace/ws-default/run/r-1"]
        assert "ds-agent://workspace/ws-default/run/r-1" in buf.getvalue()

    def test_workspace_and_action_flags_overridable(self) -> None:
        copied: list[str] = []
        console, buf = _console()
        rc = run_share_command(
            [
                "artifact",
                "art-7",
                "--workspace",
                "ws-1",
                "--action",
                "promote",
            ],
            console=console,
            clipboard=lambda t: copied.append(t) or True,
        )
        assert rc == 0
        expected = "ds-agent://workspace/ws-1/artifact/art-7?action=promote"
        assert copied == [expected]
        assert expected in buf.getvalue()

    def test_rejects_unknown_resource_type(self) -> None:
        console, buf = _console()
        rc = run_share_command(
            ["secret", "r-1", "--workspace", "ws-1"], console=console
        )
        assert rc == 1
        assert "Refusing to share" in buf.getvalue()

    def test_rejects_invalid_action_chars(self) -> None:
        console, buf = _console()
        rc = run_share_command(
            ["run", "r-1", "--workspace", "ws-1", "--action", "do it"],
            console=console,
        )
        assert rc == 1
        assert "Refusing to share" in buf.getvalue()

    def test_clipboard_failure_falls_back_to_print_only(self) -> None:
        console, buf = _console()
        rc = run_share_command(
            ["run", "r-1", "--workspace", "ws-1"],
            console=console,
            clipboard=lambda _t: False,
        )
        assert rc == 0
        out = buf.getvalue()
        assert "ds-agent://workspace/ws-1/run/r-1" in out
        assert "clipboard unavailable" in out

    @pytest.mark.parametrize("flag", ["--workspace", "--action"])
    def test_dangling_flag_is_rejected(self, flag: str) -> None:
        console, _ = _console()
        rc = run_share_command(["run", "r-1", flag], console=console)
        assert rc == 2
