"""410 GONE / 404 auto-prune contract for the web push transport (W4-06b)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from ds_agent.application.use_cases.dispatch_web_push_usecase import (
    DispatchWebPushUseCase,
    WebPushSubscriptionExpiredError,
    WebPushSubscriptionStorePort,
    WebPushTransportUnavailableError,
)
from ds_agent.domain.notification import Notification, NotificationCategory
from ds_agent.infrastructure.persistence.web_push_subscription_store import (
    WebPushSubscription,
)

# Skip if cryptography / httpx are not importable in this environment;
# the transport itself raises at construction in that case.
try:
    import httpx  # noqa: F401

    from ds_agent.infrastructure.notification.web_push_transport import (
        VapidClaims,
        _HttpxVapidTransport,
    )

    _IMPORTS_OK = True
except Exception:  # pragma: no cover - exercised only when libs missing
    _IMPORTS_OK = False

pytestmark = pytest.mark.skipif(
    not _IMPORTS_OK,
    reason="httpx / cryptography unavailable; transport tests skipped",
)


# A real-looking PEM is needed because the constructor parses it. Generate
# one at module import time so we do not ship a static private key in source.
def _fresh_private_key_pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


class _StubResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = ""
        self.headers: dict[str, str] = {}


class _FixedSubscriptionStore(WebPushSubscriptionStorePort):
    def __init__(self, subs: list[WebPushSubscription]) -> None:
        self._subs = subs

    def list_for(self, operator_id: str):  # type: ignore[override]
        return list(self._subs)


def _make_subscription(endpoint: str = "https://push.example/abc") -> WebPushSubscription:
    return WebPushSubscription(
        endpoint=endpoint,
        p256dh_key=(
            "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
        ),
        auth_key="BTBZMqHH6r4Tts7J_aSIgg",
        created_at=datetime(2026, 4, 20, tzinfo=UTC),
    )


def _approval() -> Notification:
    return Notification(
        category=NotificationCategory.APPROVAL,
        title="approve deploy",
        body="risk: medium",
    )


def _build_transport(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response_status: int,
    prune_calls: list[tuple[str, str]],
) -> _HttpxVapidTransport:
    def _fake_post(
        url: str,
        *,
        headers: dict[str, str],
        content: bytes,
        timeout: float,
    ) -> _StubResponse:
        return _StubResponse(response_status)

    # Patch httpx.post used inside the deliver method.
    import ds_agent.infrastructure.notification.web_push_transport as wpt

    monkeypatch.setattr(wpt.httpx, "post", _fake_post)

    def _on_prune(operator_id: str, endpoint: str) -> None:
        prune_calls.append((operator_id, endpoint))

    transport = _HttpxVapidTransport(
        private_key_pem=_fresh_private_key_pem(),
        public_key_b64url="BFakePublicKey",
        claims=VapidClaims(subject="mailto:op@example.com"),
        on_subscription_expired=_on_prune,
    )
    return transport


def test_410_invokes_prune_callback_and_use_case_reports_pruned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prune_calls: list[tuple[str, str]] = []
    transport = _build_transport(
        monkeypatch, response_status=410, prune_calls=prune_calls,
    )
    sub = _make_subscription("https://push.example/abc")
    store = _FixedSubscriptionStore([sub])
    uc = DispatchWebPushUseCase(transport=transport, subscription_store=store)

    result = uc.execute(operator_id="op-1", notification=_approval())

    assert result.delivered_count == 0
    assert result.pruned_count == 1
    assert result.skipped_reason is None
    assert prune_calls == [("op-1", "https://push.example/abc")]


def test_404_invokes_prune_callback_same_as_410(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prune_calls: list[tuple[str, str]] = []
    transport = _build_transport(
        monkeypatch, response_status=404, prune_calls=prune_calls,
    )
    sub = _make_subscription("https://push.example/dead")
    store = _FixedSubscriptionStore([sub])
    uc = DispatchWebPushUseCase(transport=transport, subscription_store=store)

    result = uc.execute(operator_id="op-2", notification=_approval())

    assert result.pruned_count == 1
    assert prune_calls == [("op-2", "https://push.example/dead")]


def test_200_does_not_invoke_prune_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prune_calls: list[tuple[str, str]] = []
    transport = _build_transport(
        monkeypatch, response_status=201, prune_calls=prune_calls,
    )
    sub = _make_subscription("https://push.example/live")
    store = _FixedSubscriptionStore([sub])
    uc = DispatchWebPushUseCase(transport=transport, subscription_store=store)

    result = uc.execute(operator_id="op-3", notification=_approval())

    assert result.delivered_count == 1
    assert result.pruned_count == 0
    assert prune_calls == []


def test_transport_raises_typed_expired_error_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct .deliver() call must surface the typed exception."""
    prune_calls: list[tuple[str, str]] = []
    transport = _build_transport(
        monkeypatch, response_status=410, prune_calls=prune_calls,
    )
    sub = _make_subscription("https://push.example/exp")

    with pytest.raises(WebPushSubscriptionExpiredError):
        transport.deliver(
            operator_id="op-X",
            subscription=sub,
            notification=_approval(),
        )
    assert prune_calls == [("op-X", "https://push.example/exp")]


def test_transport_posts_encrypted_payload_and_aes128gcm_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _fake_post(
        url: str,
        *,
        headers: dict[str, str],
        content: bytes,
        timeout: float,
    ) -> _StubResponse:
        captured["url"] = url
        captured["headers"] = headers
        captured["content"] = content
        captured["timeout"] = timeout
        return _StubResponse(201)

    import ds_agent.infrastructure.notification.web_push_transport as wpt

    monkeypatch.setattr(wpt.httpx, "post", _fake_post)
    monkeypatch.setattr(wpt, "encrypt_web_push_payload", lambda *args, **kwargs: b"\x01\x02cipher")

    transport = _HttpxVapidTransport(
        private_key_pem=_fresh_private_key_pem(),
        public_key_b64url="BFakePublicKey",
        claims=VapidClaims(subject="mailto:op@example.com"),
    )
    sub = _make_subscription("https://push.example/live")

    transport.deliver(
        operator_id="op-enc",
        subscription=sub,
        notification=_approval(),
    )

    assert captured["url"] == "https://push.example/live"
    assert captured["headers"]["Content-Encoding"] == "aes128gcm"
    assert captured["headers"]["Content-Type"] == "application/octet-stream"
    assert captured["headers"]["Content-Length"] == str(len(b"\x01\x02cipher"))
    assert captured["content"] == b"\x01\x02cipher"


def test_transport_surfaces_payload_encryption_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = _HttpxVapidTransport(
        private_key_pem=_fresh_private_key_pem(),
        public_key_b64url="BFakePublicKey",
        claims=VapidClaims(subject="mailto:op@example.com"),
    )
    invalid = WebPushSubscription(
        endpoint="https://push.example/bad",
        p256dh_key="not-a-real-key",
        auth_key="bad-auth",
        created_at=datetime(2026, 4, 20, tzinfo=UTC),
    )

    with pytest.raises(WebPushTransportUnavailableError, match="encryption failed"):
        transport.deliver(
            operator_id="op-bad",
            subscription=invalid,
            notification=_approval(),
        )


def _untouched(_: Any) -> None:
    """Placeholder so test discovery does not flag unused import."""
    return None
