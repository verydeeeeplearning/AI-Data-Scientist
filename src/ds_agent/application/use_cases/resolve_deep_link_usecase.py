"""Application use case: resolve a parsed deep link into an authorized target.

Responsibilities (Clean Architecture — application layer):

1. Parse / validate the URI via the pure :mod:`deep_link` domain module.
2. Enforce workspace authorization (sole-user today, hook for multi-user later).
3. Apply the configured re-authentication policy
   (D-W4-1 ADR default = ``once-per-session``).

The use case depends only on **port interfaces** (``Protocol``); concrete
adapters (Electron IPC, CLI, Telegram bot) wire implementations at the
composition root.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from ds_agent.domain.value_objects.deep_link import (
    DeepLink,
    DeepLinkParseError,
    parse_deep_link,
)


class ReauthPolicy(StrEnum):
    """Re-authentication policy applied when entering via a deep link.

    Defaults to ``ONCE_PER_SESSION`` per ADR D-W4-1 (PLAN_03 §9 open question).
    """

    NONE = "none"
    ONCE_PER_SESSION = "once_per_session"
    ALWAYS = "always"


class DeepLinkResolveStatus(StrEnum):
    """Outcome of resolving a deep link."""

    OK = "ok"
    INVALID_URI = "invalid_uri"
    FORBIDDEN_WORKSPACE = "forbidden_workspace"
    REAUTH_REQUIRED = "reauth_required"


@dataclass(frozen=True, slots=True)
class ResolveDeepLinkInput:
    """Input DTO accepted at the application boundary."""

    uri: str
    current_workspace_id: str
    session_id: str


@dataclass(frozen=True, slots=True)
class ResolveDeepLinkOutput:
    """Output DTO returned to the calling adapter (CLI / IPC / Telegram)."""

    status: DeepLinkResolveStatus
    link: DeepLink | None = None
    parse_error: DeepLinkParseError | None = None


class WorkspaceAuthorizationPort(Protocol):
    """Hook for workspace-level authorization.

    Today (sole operator) the default implementation just compares
    ``current_workspace_id == link.workspace_id``. The port stays so a future
    multi-user backend can plug in role-based / token-based checks without
    touching the use case.
    """

    def is_authorized(self, *, session_id: str, workspace_id: str) -> bool: ...


class ReauthSessionPort(Protocol):
    """Track whether the current session has already been re-authenticated.

    The port lets the use case stay free of any concrete session store. The CLI
    adapter can back this with an in-memory dict; the Electron main process can
    back it with the existing token store.
    """

    def is_reauthenticated(self, *, session_id: str) -> bool: ...

    def mark_reauthenticated(self, *, session_id: str) -> None: ...


class DefaultWorkspaceAuthorization:
    """Sole-user default: any session may access the matching workspace."""

    def is_authorized(self, *, session_id: str, workspace_id: str) -> bool:
        return bool(session_id) and bool(workspace_id)


class InMemoryReauthSession:
    """In-memory reauth tracker. Suitable for the CLI process lifetime."""

    def __init__(self) -> None:
        self._reauthenticated: set[str] = set()

    def is_reauthenticated(self, *, session_id: str) -> bool:
        return session_id in self._reauthenticated

    def mark_reauthenticated(self, *, session_id: str) -> None:
        self._reauthenticated.add(session_id)


class ResolveDeepLinkUseCase:
    """Validate, authorize, and gate-keep a deep link.

    Parameters
    ----------
    authorization
        Port that decides whether the caller may access the workspace.
    reauth_session
        Port that records / queries per-session re-authentication state.
    policy
        Re-authentication policy. Defaults to ``ONCE_PER_SESSION``
        (ADR D-W4-1).
    """

    def __init__(
        self,
        authorization: WorkspaceAuthorizationPort,
        reauth_session: ReauthSessionPort,
        policy: ReauthPolicy = ReauthPolicy.ONCE_PER_SESSION,
    ) -> None:
        self._authorization = authorization
        self._reauth_session = reauth_session
        self._policy = policy

    def execute(self, request: ResolveDeepLinkInput) -> ResolveDeepLinkOutput:
        parse_result = parse_deep_link(request.uri)
        if not parse_result.ok or parse_result.value is None:
            return ResolveDeepLinkOutput(
                status=DeepLinkResolveStatus.INVALID_URI,
                parse_error=parse_result.error,
            )

        link = parse_result.value

        # Workspace match — sole-user environment defaults to strict equality.
        if link.workspace_id != request.current_workspace_id.strip():
            return ResolveDeepLinkOutput(
                status=DeepLinkResolveStatus.FORBIDDEN_WORKSPACE,
                link=link,
            )

        if not self._authorization.is_authorized(
            session_id=request.session_id, workspace_id=link.workspace_id
        ):
            return ResolveDeepLinkOutput(
                status=DeepLinkResolveStatus.FORBIDDEN_WORKSPACE,
                link=link,
            )

        if self._needs_reauth(request.session_id):
            return ResolveDeepLinkOutput(
                status=DeepLinkResolveStatus.REAUTH_REQUIRED,
                link=link,
            )

        return ResolveDeepLinkOutput(status=DeepLinkResolveStatus.OK, link=link)

    def confirm_reauth(self, session_id: str) -> None:
        """Adapter hook: call after the operator successfully re-authenticates."""

        self._reauth_session.mark_reauthenticated(session_id=session_id)

    def _needs_reauth(self, session_id: str) -> bool:
        if self._policy is ReauthPolicy.NONE:
            return False
        if self._policy is ReauthPolicy.ALWAYS:
            return True
        # ONCE_PER_SESSION
        return not self._reauth_session.is_reauthenticated(session_id=session_id)


__all__ = [
    "DeepLinkResolveStatus",
    "DefaultWorkspaceAuthorization",
    "InMemoryReauthSession",
    "ReauthPolicy",
    "ReauthSessionPort",
    "ResolveDeepLinkInput",
    "ResolveDeepLinkOutput",
    "ResolveDeepLinkUseCase",
    "WorkspaceAuthorizationPort",
]
