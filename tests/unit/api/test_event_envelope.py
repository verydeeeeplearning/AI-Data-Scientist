"""Round-trip and validation tests for the WS event envelope."""

from __future__ import annotations

import json

import pytest

from ds_agent.api.event_envelope import (
    ENVELOPE_MAJOR,
    ENVELOPE_VERSION,
    HandshakeAck,
    HandshakeRequest,
    WsEnvelopeError,
    negotiate,
    parse_envelope,
    wrap_event,
)


class TestWrapEvent:
    def test_wraps_payload_with_canonical_envelope(self) -> None:
        env = wrap_event("mission.context.updated", {"goal": "churn"})
        assert env.type == "mission.context.updated"
        assert env.version == ENVELOPE_VERSION
        assert env.payload == {"goal": "churn"}
        assert env.source is None
        assert env.correlation_id is None

    def test_includes_optional_metadata(self) -> None:
        env = wrap_event(
            "card.created",
            {"id": "card-1"},
            source="agent-runner",
            correlation_id="req-42",
        )
        assert env.source == "agent-runner"
        assert env.correlation_id == "req-42"

    def test_rejects_empty_event_type(self) -> None:
        with pytest.raises(WsEnvelopeError) as ei:
            wrap_event("", {})
        assert ei.value.code == "wrong-type"

    def test_to_wire_camelcases_correlation_id(self) -> None:
        env = wrap_event("x", {}, correlation_id="c")
        wire = env.to_wire()
        assert "correlationId" in wire
        assert "correlation_id" not in wire


class TestParseEnvelope:
    def test_accepts_minimal_well_formed(self) -> None:
        env = parse_envelope(
            {"type": "x", "version": "1.0", "ts": 1.0, "payload": {}},
        )
        assert env.type == "x"

    def test_accepts_optional_source_and_correlation(self) -> None:
        env = parse_envelope(
            {
                "type": "x",
                "version": "1.0",
                "ts": 1.0,
                "payload": {},
                "source": "test",
                "correlationId": "c-1",
            },
        )
        assert env.source == "test"
        assert env.correlation_id == "c-1"

    @pytest.mark.parametrize(
        "raw",
        [
            {},
            {"type": "x"},
            {"type": "x", "version": "1.0"},
            {"type": "x", "version": "1.0", "ts": 0},
        ],
    )
    def test_rejects_missing_required_fields(self, raw: dict) -> None:
        with pytest.raises(WsEnvelopeError) as ei:
            parse_envelope(raw)
        assert ei.value.code == "missing-field"

    def test_rejects_non_dict(self) -> None:
        with pytest.raises(WsEnvelopeError) as ei:
            parse_envelope("not a dict")
        assert ei.value.code == "wrong-type"

    def test_rejects_empty_type(self) -> None:
        with pytest.raises(WsEnvelopeError) as ei:
            parse_envelope({"type": "", "version": "1.0", "ts": 1.0, "payload": {}})
        assert ei.value.code == "wrong-type"

    def test_rejects_malformed_version(self) -> None:
        with pytest.raises(WsEnvelopeError) as ei:
            parse_envelope({"type": "x", "version": "v1", "ts": 1.0, "payload": {}})
        assert ei.value.code == "malformed-version"

    def test_rejects_major_mismatch(self) -> None:
        with pytest.raises(WsEnvelopeError) as ei:
            parse_envelope({"type": "x", "version": "99.0", "ts": 1.0, "payload": {}})
        assert ei.value.code == "major-mismatch"

    def test_accepts_higher_minor_within_same_major(self) -> None:
        env = parse_envelope(
            {"type": "x", "version": f"{ENVELOPE_MAJOR}.99", "ts": 1.0, "payload": {}},
        )
        assert env.version == f"{ENVELOPE_MAJOR}.99"


class TestRoundTrip:
    """Wrap + JSON serialize + JSON parse + parse_envelope is a no-op identity."""

    def test_wrap_then_parse_recovers_envelope(self) -> None:
        original = wrap_event(
            "reasoning.emitted",
            {"hypothesis": "data leak", "decision": "investigate"},
            source="agent-runner",
            correlation_id="r-1",
            ts=1_700_000_000.5,
        )
        wire = original.to_wire()
        decoded = parse_envelope(json.loads(json.dumps(wire)))
        assert decoded.type == original.type
        assert decoded.version == original.version
        assert decoded.ts == original.ts
        assert decoded.source == original.source
        assert decoded.correlation_id == original.correlation_id
        assert decoded.payload == original.payload

    def test_round_trip_without_optional_fields(self) -> None:
        original = wrap_event("file.created", {"path": "a.csv", "size": 100})
        decoded = parse_envelope(json.loads(json.dumps(original.to_wire())))
        assert decoded.payload == {"path": "a.csv", "size": 100}
        assert decoded.source is None
        assert decoded.correlation_id is None


class TestNegotiate:
    def test_picks_server_version_when_supported(self) -> None:
        ack = negotiate(HandshakeRequest(supported_versions=("1.0", "0.9")))
        assert isinstance(ack, HandshakeAck)
        assert ack.selected_version == ENVELOPE_VERSION

    def test_falls_back_to_same_major_minor(self) -> None:
        ack = negotiate(HandshakeRequest(supported_versions=(f"{ENVELOPE_MAJOR}.5",)))
        assert ack.selected_version == f"{ENVELOPE_MAJOR}.5"

    def test_raises_when_no_compatible_major(self) -> None:
        with pytest.raises(WsEnvelopeError) as ei:
            negotiate(HandshakeRequest(supported_versions=("99.0", "100.0")))
        assert ei.value.code == "major-mismatch"

    def test_raises_when_supported_versions_empty(self) -> None:
        with pytest.raises(WsEnvelopeError):
            negotiate(HandshakeRequest(supported_versions=()))


class TestCrossLanguageInterop:
    """Envelope shape MUST match the TypeScript validator (1:1 wire compat)."""

    def test_wire_format_uses_camelcase_correlation_id(self) -> None:
        env = wrap_event("x", {}, correlation_id="c-1")
        wire = env.to_wire()
        assert wire["correlationId"] == "c-1"

    def test_wire_format_omits_unset_optional_fields(self) -> None:
        env = wrap_event("x", {})
        wire = env.to_wire()
        assert "source" not in wire
        assert "correlationId" not in wire

    def test_wire_format_keys_match_typescript_envelope(self) -> None:
        env = wrap_event("x", {"k": 1}, source="s", correlation_id="c")
        wire = env.to_wire()
        # TypeScript WsEventEnvelope keys: type, version, ts, source?, correlationId?, payload
        assert set(wire.keys()) == {"type", "version", "ts", "source", "correlationId", "payload"}
