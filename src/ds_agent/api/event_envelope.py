"""WebSocket event envelope (cross_cutting/PLAN_03).

All WS events emitted by the gateway MUST flow through ``wrap_event``. The
envelope adds versioning + correlation metadata to every payload so the
client can degrade gracefully when the server adds new event types or fields.

Schema: ``{type, version, ts, source?, correlationId?, payload}`` — matches
``electron/src/renderer/infrastructure/ws/eventEnvelope.ts``.

ADR-0007 documents the design choice (lightweight dataclass, no pydantic v2
extra schema lib for round-trip validation).
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

ENVELOPE_VERSION = "1.0"
ENVELOPE_MAJOR = 1

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")


class WsEnvelopeError(ValueError):
    """Raised when an inbound or outbound envelope fails schema validation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WsEventEnvelope:
    """Versioned WebSocket event envelope."""

    type: str
    version: str
    ts: float
    payload: Any
    source: str | None = None
    correlation_id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_wire(self) -> dict[str, Any]:
        """Serialize to wire format (camelCase keys for JS interop)."""
        out: dict[str, Any] = {
            "type": self.type,
            "version": self.version,
            "ts": self.ts,
            "payload": self.payload,
        }
        if self.source is not None:
            out["source"] = self.source
        if self.correlation_id is not None:
            out["correlationId"] = self.correlation_id
        return out


def wrap_event(
    event_type: str,
    payload: Any,
    *,
    source: str | None = None,
    correlation_id: str | None = None,
    ts: float | None = None,
) -> WsEventEnvelope:
    """Wrap a payload in the canonical envelope."""
    if not isinstance(event_type, str) or not event_type:
        raise WsEnvelopeError("wrong-type", "event_type must be a non-empty string")
    return WsEventEnvelope(
        type=event_type,
        version=ENVELOPE_VERSION,
        ts=ts if ts is not None else time.time(),
        payload=payload,
        source=source,
        correlation_id=correlation_id,
    )


def parse_envelope(raw: Any) -> WsEventEnvelope:
    """Parse + validate an envelope received from a peer (e.g. handshake)."""
    if not isinstance(raw, dict):
        raise WsEnvelopeError("wrong-type", "envelope must be an object")

    if "type" not in raw:
        raise WsEnvelopeError("missing-field", "envelope.type is required")
    event_type = raw["type"]
    if not isinstance(event_type, str) or not event_type:
        raise WsEnvelopeError("wrong-type", "envelope.type must be a non-empty string")

    if "version" not in raw:
        raise WsEnvelopeError("missing-field", "envelope.version is required")
    version = raw["version"]
    if not isinstance(version, str):
        raise WsEnvelopeError("wrong-type", "envelope.version must be a string")
    match = _VERSION_RE.match(version)
    if not match:
        raise WsEnvelopeError(
            "malformed-version",
            f'version "{version}" must match major.minor',
        )
    major = int(match.group(1))
    if major != ENVELOPE_MAJOR:
        raise WsEnvelopeError(
            "major-mismatch",
            f"envelope major {major} mismatches server major {ENVELOPE_MAJOR}",
        )

    if "ts" not in raw:
        raise WsEnvelopeError("missing-field", "envelope.ts is required")
    ts_value = raw["ts"]
    if not isinstance(ts_value, int | float):
        raise WsEnvelopeError("wrong-type", "envelope.ts must be a number")

    if "payload" not in raw:
        raise WsEnvelopeError("missing-field", "envelope.payload is required")

    source = raw.get("source")
    if source is not None and not isinstance(source, str):
        raise WsEnvelopeError("wrong-type", "envelope.source must be a string when present")
    correlation_id = raw.get("correlationId")
    if correlation_id is not None and not isinstance(correlation_id, str):
        raise WsEnvelopeError(
            "wrong-type",
            "envelope.correlationId must be a string when present",
        )

    return WsEventEnvelope(
        type=event_type,
        version=version,
        ts=float(ts_value),
        payload=raw["payload"],
        source=source,
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Handshake (PLAN_03 §4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HandshakeRequest:
    """Client → server handshake payload (sent on connect)."""

    supported_versions: tuple[str, ...]


@dataclass(frozen=True)
class HandshakeAck:
    """Server → client handshake response."""

    selected_version: str
    server_version: str = ENVELOPE_VERSION


def negotiate(request: HandshakeRequest) -> HandshakeAck:
    """Pick a mutually supported envelope version, preferring server's current."""
    if ENVELOPE_VERSION in request.supported_versions:
        return HandshakeAck(selected_version=ENVELOPE_VERSION)
    # Fallback: any same-major version the client supports
    for client_version in request.supported_versions:
        match = _VERSION_RE.match(client_version)
        if match and int(match.group(1)) == ENVELOPE_MAJOR:
            return HandshakeAck(selected_version=client_version)
    raise WsEnvelopeError(
        "major-mismatch",
        (
            f"no compatible major version: client={list(request.supported_versions)} "
            f"server={ENVELOPE_VERSION}"
        ),
    )


__all__ = [
    "ENVELOPE_MAJOR",
    "ENVELOPE_VERSION",
    "HandshakeAck",
    "HandshakeRequest",
    "WsEnvelopeError",
    "WsEventEnvelope",
    "asdict",
    "negotiate",
    "parse_envelope",
    "wrap_event",
]
