"""Use case tests: workspace authorization + re-auth policy."""

from __future__ import annotations

import pytest

from ds_agent.application.use_cases.resolve_deep_link_usecase import (
    DeepLinkResolveStatus,
    DefaultWorkspaceAuthorization,
    InMemoryReauthSession,
    ReauthPolicy,
    ResolveDeepLinkInput,
    ResolveDeepLinkUseCase,
)
from ds_agent.domain.value_objects.deep_link import DeepLinkParseError


def _build_use_case(
    *,
    policy: ReauthPolicy = ReauthPolicy.ONCE_PER_SESSION,
    pre_authenticated_sessions: list[str] | None = None,
) -> tuple[ResolveDeepLinkUseCase, InMemoryReauthSession]:
    auth = DefaultWorkspaceAuthorization()
    reauth = InMemoryReauthSession()
    for sid in pre_authenticated_sessions or []:
        reauth.mark_reauthenticated(session_id=sid)
    return ResolveDeepLinkUseCase(auth, reauth, policy=policy), reauth


class TestResolveDeepLinkInvalidInput:
    def test_invalid_uri_returns_parse_error(self) -> None:
        uc, _ = _build_use_case(policy=ReauthPolicy.NONE)
        out = uc.execute(
            ResolveDeepLinkInput(
                uri="http://workspace/ws-1/run/r-1",
                current_workspace_id="ws-1",
                session_id="sess-1",
            )
        )
        assert out.status is DeepLinkResolveStatus.INVALID_URI
        assert out.parse_error is DeepLinkParseError.INVALID_SCHEME
        assert out.link is None

    def test_oversized_uri_returns_parse_error(self) -> None:
        uc, _ = _build_use_case(policy=ReauthPolicy.NONE)
        big = f"ds-agent://workspace/ws-1/run/{'x' * 2200}"
        out = uc.execute(
            ResolveDeepLinkInput(
                uri=big,
                current_workspace_id="ws-1",
                session_id="sess-1",
            )
        )
        assert out.status is DeepLinkResolveStatus.INVALID_URI
        assert out.parse_error is DeepLinkParseError.TOO_LONG


class TestResolveDeepLinkAuthorization:
    def test_workspace_mismatch_blocked(self) -> None:
        uc, _ = _build_use_case(policy=ReauthPolicy.NONE)
        out = uc.execute(
            ResolveDeepLinkInput(
                uri="ds-agent://workspace/other-ws/run/r-1",
                current_workspace_id="ws-1",
                session_id="sess-1",
            )
        )
        assert out.status is DeepLinkResolveStatus.FORBIDDEN_WORKSPACE
        assert out.link is not None
        assert out.link.workspace_id == "other-ws"

    def test_workspace_match_allowed(self) -> None:
        uc, _ = _build_use_case(
            policy=ReauthPolicy.NONE,
        )
        out = uc.execute(
            ResolveDeepLinkInput(
                uri="ds-agent://workspace/ws-1/run/r-1",
                current_workspace_id="ws-1",
                session_id="sess-1",
            )
        )
        assert out.status is DeepLinkResolveStatus.OK
        assert out.link is not None

    def test_authorization_port_can_block_even_when_workspace_matches(self) -> None:
        class DenyAll:
            def is_authorized(self, *, session_id: str, workspace_id: str) -> bool:
                return False

        reauth = InMemoryReauthSession()
        uc = ResolveDeepLinkUseCase(DenyAll(), reauth, policy=ReauthPolicy.NONE)
        out = uc.execute(
            ResolveDeepLinkInput(
                uri="ds-agent://workspace/ws-1/run/r-1",
                current_workspace_id="ws-1",
                session_id="sess-1",
            )
        )
        assert out.status is DeepLinkResolveStatus.FORBIDDEN_WORKSPACE


class TestResolveDeepLinkReauthPolicy:
    def test_policy_none_skips_reauth(self) -> None:
        uc, _ = _build_use_case(policy=ReauthPolicy.NONE)
        out = uc.execute(
            ResolveDeepLinkInput(
                uri="ds-agent://workspace/ws-1/run/r-1",
                current_workspace_id="ws-1",
                session_id="sess-1",
            )
        )
        assert out.status is DeepLinkResolveStatus.OK

    def test_policy_always_requires_reauth_every_time(self) -> None:
        uc, reauth = _build_use_case(
            policy=ReauthPolicy.ALWAYS,
            pre_authenticated_sessions=["sess-1"],
        )
        request = ResolveDeepLinkInput(
            uri="ds-agent://workspace/ws-1/run/r-1",
            current_workspace_id="ws-1",
            session_id="sess-1",
        )
        first = uc.execute(request)
        assert first.status is DeepLinkResolveStatus.REAUTH_REQUIRED
        # Confirming reauth does not exempt future calls under ALWAYS.
        uc.confirm_reauth("sess-1")
        second = uc.execute(request)
        assert second.status is DeepLinkResolveStatus.REAUTH_REQUIRED
        assert "sess-1" in reauth._reauthenticated  # confirm_reauth still records

    def test_policy_once_per_session_first_call_requires_reauth(self) -> None:
        uc, _ = _build_use_case(policy=ReauthPolicy.ONCE_PER_SESSION)
        out = uc.execute(
            ResolveDeepLinkInput(
                uri="ds-agent://workspace/ws-1/run/r-1",
                current_workspace_id="ws-1",
                session_id="sess-1",
            )
        )
        assert out.status is DeepLinkResolveStatus.REAUTH_REQUIRED

    def test_policy_once_per_session_after_confirm_succeeds(self) -> None:
        uc, _ = _build_use_case(policy=ReauthPolicy.ONCE_PER_SESSION)
        uc.confirm_reauth("sess-1")
        out = uc.execute(
            ResolveDeepLinkInput(
                uri="ds-agent://workspace/ws-1/run/r-1",
                current_workspace_id="ws-1",
                session_id="sess-1",
            )
        )
        assert out.status is DeepLinkResolveStatus.OK

    def test_default_policy_is_once_per_session(self) -> None:
        # ADR D-W4-1: default is once_per_session.
        auth = DefaultWorkspaceAuthorization()
        reauth = InMemoryReauthSession()
        uc = ResolveDeepLinkUseCase(auth, reauth)  # no policy arg
        out = uc.execute(
            ResolveDeepLinkInput(
                uri="ds-agent://workspace/ws-1/run/r-1",
                current_workspace_id="ws-1",
                session_id="sess-fresh",
            )
        )
        assert out.status is DeepLinkResolveStatus.REAUTH_REQUIRED


@pytest.mark.parametrize(
    ("policy", "pre_auth", "expected"),
    [
        (ReauthPolicy.NONE, False, DeepLinkResolveStatus.OK),
        (ReauthPolicy.ONCE_PER_SESSION, False, DeepLinkResolveStatus.REAUTH_REQUIRED),
        (ReauthPolicy.ONCE_PER_SESSION, True, DeepLinkResolveStatus.OK),
        (ReauthPolicy.ALWAYS, True, DeepLinkResolveStatus.REAUTH_REQUIRED),
    ],
)
def test_policy_matrix(
    policy: ReauthPolicy, pre_auth: bool, expected: DeepLinkResolveStatus
) -> None:
    uc, _ = _build_use_case(
        policy=policy,
        pre_authenticated_sessions=["sess-x"] if pre_auth else None,
    )
    out = uc.execute(
        ResolveDeepLinkInput(
            uri="ds-agent://workspace/ws-1/run/r-1",
            current_workspace_id="ws-1",
            session_id="sess-x",
        )
    )
    assert out.status is expected
