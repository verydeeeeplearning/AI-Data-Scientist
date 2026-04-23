"""Tests for ``ds-agent web-push`` CLI subcommands (W4-06b close)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ds_agent.cli.web_push_cli import run_web_push_command
from ds_agent.infrastructure.persistence.web_push_subscription_store import (
    JsonWebPushSubscriptionStore,
    WebPushSubscription,
)


def test_generate_vapid_keys_emits_two_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = run_web_push_command(["generate-vapid-keys"])
    assert rc == 0
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 2, f"expected private+public lines, got {lines!r}"
    private_line, public_line = lines
    # Both lines are base64url so they should not contain '+' or '/'.
    assert "+" not in private_line and "/" not in private_line
    assert "+" not in public_line and "/" not in public_line
    # Public key uncompressed point: 65 raw bytes → 87 b64url chars (no pad).
    assert 80 < len(public_line) < 100


def test_print_public_key_reads_env(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DS_AGENT_VAPID_PUBLIC_KEY", "BFakeKey123")
    rc = run_web_push_command(["print-public-key"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "BFakeKey123"


def test_print_public_key_returns_error_when_unset(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DS_AGENT_VAPID_PUBLIC_KEY", raising=False)
    rc = run_web_push_command(["print-public-key"])
    assert rc == 1


def test_subscribers_lists_per_operator_entries(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Seed via the same workspace_dir the CLI uses, so both write/read
    # land in the same `.ds-agent/runtime/web-push-subscriptions/` dir.
    store = JsonWebPushSubscriptionStore(str(tmp_path))
    store.register(
        "op-A",
        WebPushSubscription(
            endpoint="https://push.example/a1",
            p256dh_key="p",
            auth_key="a",
            created_at=datetime(2026, 4, 20, tzinfo=UTC),
        ),
    )
    store.register(
        "op-B",
        WebPushSubscription(
            endpoint="https://push.example/b1",
            p256dh_key="p",
            auth_key="a",
            created_at=datetime(2026, 4, 20, tzinfo=UTC),
        ),
    )
    store.register(
        "op-B",
        WebPushSubscription(
            endpoint="https://push.example/b2",
            p256dh_key="p",
            auth_key="a",
            created_at=datetime(2026, 4, 20, tzinfo=UTC),
        ),
    )

    rc = run_web_push_command(
        ["subscribers", "--workspace-dir", str(tmp_path)],
    )
    assert rc == 0
    captured = capsys.readouterr()

    assert "op-A" in captured.out
    assert "op-B" in captured.out
    assert "https://push.example/a1" in captured.out
    assert "https://push.example/b1" in captured.out
    assert "https://push.example/b2" in captured.out
    assert "total: 3" in captured.out
