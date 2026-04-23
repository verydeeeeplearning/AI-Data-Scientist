"""Web push transport adapter (Wave 4 PLAN_06b).

Design choices
--------------
* **No new heavy dependency.** We deliberately do NOT pull in
  ``pywebpush``. Instead we layer on top of ``httpx`` (already in the
  dependency tree) plus a thin VAPID JWT signer that uses
  ``cryptography`` (also already present transitively).
* **Soft-fail.** If either library is unavailable at import time, the
  module exposes a sentinel transport that raises
  :class:`WebPushTransportUnavailableError` on first use; the use case turns
  that into ``skipped_reason="transport_unavailable"`` rather than
  crashing the wider notification pipeline.
* **Key bootstrap is environment-driven.** If
  ``DS_AGENT_VAPID_PRIVATE_KEY`` is not set the module emits one
  structured-log warning at construction and the transport becomes a
  no-op that raises :class:`WebPushTransportUnavailableError` on
  :meth:`deliver`. Production operators must provide their own VAPID key
  — this is the baseline scaffold, not a managed service.
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from ds_agent.application.use_cases.dispatch_web_push_usecase import (
    WebPushSubscription,
    WebPushSubscriptionExpiredError,
    WebPushTransportPort,
    WebPushTransportUnavailableError,
)
from ds_agent.domain.notification import Notification
from ds_agent.infrastructure.notification.aes128gcm import encrypt as encrypt_web_push_payload

# Type aliases for the transport callbacks.
PruneCallback = Callable[[str, str], None]
DeliveryRecordCallback = Callable[[str, str, bool], None]
PruneRecordCallback = Callable[[str, str, str], None]
SubjectProvider = Callable[[], str | None]

_LOG = logging.getLogger(__name__)

# -- Optional imports --------------------------------------------------------

try:  # pragma: no cover - exercised only when libs are present
    import httpx  # type: ignore[import-not-found]
except Exception:
    httpx = None  # type: ignore[assignment]

try:  # pragma: no cover - exercised only when libs are present
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import (
        decode_dss_signature,
    )

    _CRYPTOGRAPHY_AVAILABLE = True
except Exception:
    _CRYPTOGRAPHY_AVAILABLE = False


# -- Public API --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VapidClaims:
    """Minimal VAPID JWT claims envelope.

    *aud* is the push service origin (scheme://host[:port]) derived per
    request from the subscription endpoint. *sub* is the operator
    contact URI (mailto: or https:) — push services require it.
    """

    subject: str
    expiry_seconds: int = 12 * 60 * 60  # 12h max per RFC 8292.


class _NoOpVapidTransport(WebPushTransportPort):
    """Transport stand-in used when VAPID keys / libs are missing.

    Always raises :class:`WebPushTransportUnavailableError`. The use case
    interprets that as a skip with reason ``transport_unavailable``.
    """

    def __init__(self, *, reason: str) -> None:
        self._reason = reason

    def deliver(
        self,
        *,
        operator_id: str,
        subscription: WebPushSubscription,
        notification: Notification,
    ) -> str:
        raise WebPushTransportUnavailableError(self._reason)


class _HttpxVapidTransport(WebPushTransportPort):
    """Real transport — HTTP POST to the push service with VAPID auth.
    """

    def __init__(
        self,
        *,
        private_key_pem: str,
        public_key_b64url: str,
        claims: VapidClaims,
        ttl_seconds: int = 60,
        timeout_seconds: float = 10.0,
        subject_provider: SubjectProvider | None = None,
        on_delivery_recorded: DeliveryRecordCallback | None = None,
        on_subscription_expired: PruneCallback | None = None,
        on_subscription_pruned: PruneRecordCallback | None = None,
    ) -> None:
        if httpx is None or not _CRYPTOGRAPHY_AVAILABLE:  # pragma: no cover
            raise WebPushTransportUnavailableError(
                "httpx or cryptography unavailable at construction"
            )
        try:
            self._private_key = serialization.load_pem_private_key(
                private_key_pem.encode("utf-8"),
                password=None,
            )
        except Exception as exc:
            raise WebPushTransportUnavailableError(
                f"VAPID private key could not be loaded: {exc}"
            ) from exc
        if not isinstance(self._private_key, ec.EllipticCurvePrivateKey):
            raise WebPushTransportUnavailableError("VAPID private key must be an EC P-256 key")
        # Narrow for the type-checker: from here on, _ec_key is EC-only.
        self._ec_key: ec.EllipticCurvePrivateKey = self._private_key
        self._public_key_b64url = public_key_b64url
        self._claims = claims
        self._ttl_seconds = ttl_seconds
        self._timeout_seconds = timeout_seconds
        self._subject_provider = subject_provider
        self._on_delivery_recorded = on_delivery_recorded
        self._on_subscription_expired = on_subscription_expired
        self._on_subscription_pruned = on_subscription_pruned

    def deliver(
        self,
        *,
        operator_id: str,
        subscription: WebPushSubscription,
        notification: Notification,
    ) -> str:
        import time
        from urllib.parse import urlsplit

        parts = urlsplit(subscription.endpoint)
        audience = f"{parts.scheme}://{parts.netloc}"
        now = int(time.time())
        subject = self._resolve_subject()
        claims = {
            "aud": audience,
            "exp": now + self._claims.expiry_seconds,
            "sub": subject,
        }
        token = self._sign_jwt(claims)
        payload = self._build_payload(notification)
        try:
            encrypted = encrypt_web_push_payload(
                payload,
                p256dh_key=subscription.p256dh_key,
                auth_key=subscription.auth_key,
            )
        except ValueError as exc:
            raise WebPushTransportUnavailableError(
                f"push payload encryption failed: {exc}"
            ) from exc
        headers = {
            "TTL": str(self._ttl_seconds),
            "Authorization": f"vapid t={token}, k={self._public_key_b64url}",
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(encrypted)),
        }
        assert httpx is not None  # narrowed by constructor check
        response = httpx.post(
            subscription.endpoint,
            headers=headers,
            content=encrypted,
            timeout=self._timeout_seconds,
        )
        # 404 / 410 GONE → subscription is dead. Invoke the prune
        # callback so the store drops it BEFORE re-raising the typed
        # expired error so the use case can count it as a routine prune
        # (not an outage).
        if response.status_code in (404, 410):
            self._record_delivery(operator_id, subscription.endpoint, False)
            if self._on_subscription_expired is not None:
                try:
                    self._on_subscription_expired(operator_id, subscription.endpoint)
                except Exception:  # pragma: no cover - defensive
                    _LOG.exception(
                        "web_push prune callback raised; continuing",
                        extra={"endpoint_host": parts.netloc},
                    )
            if self._on_subscription_pruned is not None:
                try:
                    self._on_subscription_pruned(
                        operator_id,
                        subscription.endpoint,
                        f"http_{response.status_code}",
                    )
                except Exception:  # pragma: no cover - defensive
                    _LOG.exception(
                        "web_push prune metrics callback raised; continuing",
                        extra={"endpoint_host": parts.netloc},
                    )
            raise WebPushSubscriptionExpiredError(
                f"subscription expired: {response.status_code}"
            )
        # 201/202/204 are all "accepted" per RFC 8030.
        if response.status_code not in (200, 201, 202, 204):
            self._record_delivery(operator_id, subscription.endpoint, False)
            raise WebPushTransportUnavailableError(
                f"push service rejected: {response.status_code} {response.text[:120]}"
            )
        # Title is logged for observability but not echoed to the operator.
        _LOG.debug(
            "web_push delivered",
            extra={
                "category": notification.category.value,
                "endpoint_host": parts.netloc,
                "status": response.status_code,
            },
        )
        self._record_delivery(operator_id, subscription.endpoint, True)
        location = response.headers.get("Location") or response.headers.get(
            "location", subscription.endpoint
        )
        return str(location)

    @staticmethod
    def _build_payload(notification: Notification) -> bytes:
        payload = {
            "title": notification.title,
            "body": notification.body,
            "data": {
                "category": notification.category.value,
                "deepLink": notification.deep_link,
                "workspaceId": notification.workspace_id,
                "runId": notification.run_id,
            },
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def _resolve_subject(self) -> str:
        if self._subject_provider is not None:
            subject = self._subject_provider()
            if isinstance(subject, str) and subject.strip():
                return subject.strip()
        return self._claims.subject

    def _record_delivery(self, operator_id: str, endpoint: str, ok: bool) -> None:
        if self._on_delivery_recorded is None:
            return
        try:
            self._on_delivery_recorded(operator_id, endpoint, ok)
        except Exception:  # pragma: no cover - defensive
            _LOG.exception(
                "web_push delivery metrics callback raised; continuing",
                extra={"endpoint_host": endpoint},
            )

    # ------------------------------------------------------------------
    # JWT signing helpers
    # ------------------------------------------------------------------

    def _sign_jwt(self, claims: dict[str, object]) -> str:
        header = {"typ": "JWT", "alg": "ES256"}
        signing_input = (
            _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
            + "."
            + _b64url(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
        )
        der_signature = self._ec_key.sign(
            signing_input.encode("ascii"),
            ec.ECDSA(hashes.SHA256()),
        )
        r, s = decode_dss_signature(der_signature)
        # ES256 expects fixed 64-byte (r||s) output, not DER.
        signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return signing_input + "." + _b64url(signature)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def build_web_push_transport(
    *,
    private_key_pem: str | None,
    public_key_b64url: str | None,
    subject: str,
    subject_provider: SubjectProvider | None = None,
    on_delivery_recorded: DeliveryRecordCallback | None = None,
    on_subscription_expired: PruneCallback | None = None,
    on_subscription_pruned: PruneRecordCallback | None = None,
) -> WebPushTransportPort:
    """Composition-root helper.

    Returns a real transport when keys + libs are available, otherwise a
    no-op that the use case treats as ``transport_unavailable``.
    *on_subscription_expired* is invoked with ``(operator_id, endpoint)``
    when the push gateway returns 404 / 410 so the composition root can
    drop the dead subscription from the store.
    """
    if not private_key_pem or not public_key_b64url:
        _LOG.warning(
            "web_push transport disabled: VAPID keys missing "
            "(set DS_AGENT_VAPID_PRIVATE_KEY and DS_AGENT_VAPID_PUBLIC_KEY)",
        )
        return _NoOpVapidTransport(reason="vapid_keys_missing")
    if httpx is None or not _CRYPTOGRAPHY_AVAILABLE:
        _LOG.warning(
            "web_push transport disabled: httpx or cryptography unavailable",
        )
        return _NoOpVapidTransport(reason="dependencies_missing")
    try:
        return _HttpxVapidTransport(
            private_key_pem=private_key_pem,
            public_key_b64url=public_key_b64url,
            claims=VapidClaims(subject=subject),
            subject_provider=subject_provider,
            on_delivery_recorded=on_delivery_recorded,
            on_subscription_expired=on_subscription_expired,
            on_subscription_pruned=on_subscription_pruned,
        )
    except WebPushTransportUnavailableError as exc:
        _LOG.warning("web_push transport disabled: %s", exc)
        return _NoOpVapidTransport(reason=str(exc))


__all__ = [
    "DeliveryRecordCallback",
    "PruneCallback",
    "PruneRecordCallback",
    "SubjectProvider",
    "VapidClaims",
    "build_web_push_transport",
]
