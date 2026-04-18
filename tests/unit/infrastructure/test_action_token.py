"""Tests for ds_agent.runtime.action_token."""

from __future__ import annotations

import time

from ds_agent.runtime.action_token import (
    ACTION_APPROVE,
    ACTION_REJECT,
    ACTION_STOP,
    ActionTokenStore,
    action_label,
)


class TestActionTokenStore:
    def test_create_and_resolve(self) -> None:
        store = ActionTokenStore()
        token = store.create(ACTION_APPROVE, "approval-abc-123", actor="u1", chat_id="c1")
        assert len(token.encode("utf-8")) <= 64
        ctx = store.resolve(token)
        assert ctx is not None
        assert ctx.action == ACTION_APPROVE
        assert ctx.target_id == "approval-abc-123"
        assert ctx.actor == "u1"

    def test_consume_removes_token(self) -> None:
        store = ActionTokenStore()
        token = store.create(ACTION_REJECT, "a1")
        ctx = store.consume(token)
        assert ctx is not None
        assert store.resolve(token) is None

    def test_expired_token_returns_none(self) -> None:
        store = ActionTokenStore()
        token = store.create(ACTION_STOP, "r1", ttl_seconds=0.0)
        time.sleep(0.01)
        assert store.resolve(token) is None

    def test_unknown_token_returns_none(self) -> None:
        store = ActionTokenStore()
        assert store.resolve("xx:unknown:000000") is None

    def test_token_fits_in_64_bytes(self) -> None:
        store = ActionTokenStore()
        token = store.create(ACTION_APPROVE, "a-very-long-approval-identifier-that-is-huge")
        assert len(token.encode("utf-8")) <= 64

    def test_idempotent_consume(self) -> None:
        store = ActionTokenStore()
        token = store.create(ACTION_APPROVE, "a1")
        store.consume(token)
        assert store.consume(token) is None


class TestActionLabel:
    def test_known_action(self) -> None:
        assert action_label(ACTION_APPROVE) == "Approve"

    def test_unknown_action(self) -> None:
        assert action_label("zz") == "zz"
