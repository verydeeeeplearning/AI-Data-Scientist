"""Contract tests for the Python deep_link mirror.

These tests intentionally mirror the renderer contract spec at
``electron/tests/contract/deepLinkParse.spec.ts`` 1:1 so the cross-surface
wire format cannot drift between TypeScript and Python.

If you change a case here, you MUST change the renderer spec to match
(or vice-versa) — otherwise CLI / Telegram → Electron deep links break.
"""

from __future__ import annotations

import pytest

from ds_agent.domain.value_objects.deep_link import (
    DEEP_LINK_RESOURCE_TYPES,
    DeepLink,
    DeepLinkParseError,
    DeepLinkParseFailedError,
    build_deep_link_uri,
    parse_deep_link,
    parse_deep_link_or_raise,
)


class TestParseDeepLinkHappyPath:
    @pytest.mark.parametrize("resource_type", DEEP_LINK_RESOURCE_TYPES)
    def test_every_resource_type_round_trips(self, resource_type: str) -> None:
        uri = f"ds-agent://workspace/ws-1/{resource_type}/abc-123"
        result = parse_deep_link(uri)
        assert result.ok is True, f"Expected ok for {uri}"
        assert result.value is not None
        assert result.value.workspace_id == "ws-1"
        assert result.value.resource_type == resource_type
        assert result.value.resource_id == "abc-123"
        assert result.value.action is None

    def test_action_query_param_surfaced_when_present(self) -> None:
        result = parse_deep_link("ds-agent://workspace/ws-1/run/r-9?action=compare")
        assert result.ok is True
        assert result.value is not None
        assert result.value.action == "compare"

    def test_build_then_parse_round_trip(self) -> None:
        link = DeepLink(
            workspace_id="ws-1",
            resource_type="artifact",
            resource_id="art-7",
            action="promote",
        )
        result = parse_deep_link(build_deep_link_uri(link))
        assert result.ok is True
        assert result.value is not None
        assert result.value.workspace_id == "ws-1"
        assert result.value.resource_type == "artifact"
        assert result.value.resource_id == "art-7"
        assert result.value.action == "promote"


class TestParseDeepLinkSanitization:
    def _expect_failure(self, raw: str, expected: DeepLinkParseError) -> None:
        result = parse_deep_link(raw)
        assert result.ok is False, f"Expected failure for {raw!r}"
        assert result.error == expected, (
            f"Expected error={expected.value} got={(result.error or '').value if result.error else None}"
        )

    def test_scheme_spoofing_http(self) -> None:
        self._expect_failure("http://workspace/ws-1/run/r-1", DeepLinkParseError.INVALID_SCHEME)

    def test_scheme_spoofing_javascript(self) -> None:
        self._expect_failure(
            "javascript://workspace/ws-1/run/r-1", DeepLinkParseError.INVALID_SCHEME
        )

    def test_wrong_host(self) -> None:
        self._expect_failure("ds-agent://settings/ws-1/run/r-1", DeepLinkParseError.INVALID_HOST)

    def test_path_traversal_disguise_extra_segment(self) -> None:
        self._expect_failure(
            "ds-agent://workspace/ws-1/run/r-1/extra",
            DeepLinkParseError.PATH_TRAVERSAL,
        )

    def test_path_traversal_disguise_multiple_extra_segments(self) -> None:
        self._expect_failure(
            "ds-agent://workspace/ws-1/run/r-1/extra/more",
            DeepLinkParseError.PATH_TRAVERSAL,
        )

    def test_oversized_uri(self) -> None:
        big = f"ds-agent://workspace/ws-1/run/{'x' * 2200}"
        self._expect_failure(big, DeepLinkParseError.TOO_LONG)

    def test_unknown_resource_type(self) -> None:
        self._expect_failure(
            "ds-agent://workspace/ws-1/secret/r-1",
            DeepLinkParseError.UNKNOWN_RESOURCE_TYPE,
        )

    def test_missing_workspace(self) -> None:
        self._expect_failure("ds-agent://workspace", DeepLinkParseError.MISSING_WORKSPACE)

    def test_missing_resource_type(self) -> None:
        self._expect_failure("ds-agent://workspace/ws-1", DeepLinkParseError.UNKNOWN_RESOURCE_TYPE)

    def test_missing_resource_id(self) -> None:
        self._expect_failure(
            "ds-agent://workspace/ws-1/run", DeepLinkParseError.MISSING_RESOURCE_ID
        )

    def test_invalid_workspace_with_url_encoded_space(self) -> None:
        self._expect_failure(
            "ds-agent://workspace/ws%20with%20space/run/r-1",
            DeepLinkParseError.INVALID_WORKSPACE,
        )

    def test_invalid_resource_id_with_url_encoded_space(self) -> None:
        self._expect_failure(
            "ds-agent://workspace/ws-1/run/r%20one",
            DeepLinkParseError.INVALID_RESOURCE_ID,
        )

    def test_invalid_action_with_url_encoded_space(self) -> None:
        self._expect_failure(
            "ds-agent://workspace/ws-1/run/r-1?action=do%20it",
            DeepLinkParseError.INVALID_ACTION,
        )

    def test_empty_input_rejected(self) -> None:
        self._expect_failure("", DeepLinkParseError.INVALID_SCHEME)


class TestParseDeepLinkOrRaise:
    def test_returns_value_on_success(self) -> None:
        link = parse_deep_link_or_raise("ds-agent://workspace/ws-1/run/r-1")
        assert link.workspace_id == "ws-1"
        assert link.resource_type == "run"
        assert link.resource_id == "r-1"

    def test_raises_with_structured_error_on_failure(self) -> None:
        with pytest.raises(DeepLinkParseFailedError) as exc_info:
            parse_deep_link_or_raise("http://workspace/ws-1/run/r-1")
        assert exc_info.value.error == DeepLinkParseError.INVALID_SCHEME


class TestBuildDeepLinkUri:
    def test_omits_action_query_when_absent(self) -> None:
        uri = build_deep_link_uri(
            DeepLink(
                workspace_id="ws-1",
                resource_type="run",
                resource_id="r-1",
                action=None,
            )
        )
        assert uri == "ds-agent://workspace/ws-1/run/r-1"

    def test_includes_action_query_when_present(self) -> None:
        uri = build_deep_link_uri(
            DeepLink(
                workspace_id="ws-1",
                resource_type="checkpoint",
                resource_id="cp-3",
                action="restore",
            )
        )
        assert uri == "ds-agent://workspace/ws-1/checkpoint/cp-3?action=restore"
