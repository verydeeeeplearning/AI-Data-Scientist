"""Deep link value object — Python mirror of the renderer wire-format.

Wire format (W4-C / PLAN_03):
    ``ds-agent://workspace/<workspace_id>/<resource_type>/<resource_id>(?action=<a>)``

Parsing is **pure** and runs identically in renderer (TypeScript) and CLI / Telegram
(Python). External input MUST flow through :func:`parse_deep_link` so traversal /
scheme spoofing / oversized URIs are rejected before any side effect.

This module deliberately uses only the Python standard library so the domain
layer keeps zero external dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from urllib.parse import parse_qs, unquote, urlsplit

DEEP_LINK_SCHEME: Final[str] = "ds-agent"
DEEP_LINK_HOST: Final[str] = "workspace"
DEEP_LINK_MAX_LENGTH: Final[int] = 2048

DEEP_LINK_RESOURCE_TYPES: Final[tuple[str, ...]] = (
    "run",
    "artifact",
    "checkpoint",
    "verifier_result",
)

_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_:.\-]{1,128}$")
_ACTION_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class DeepLinkParseError(StrEnum):
    """Mirror of the TypeScript ``DeepLinkParseError`` union.

    Values match the renderer string literals byte-for-byte so cross-surface
    error reporting is consistent.
    """

    TOO_LONG = "too_long"
    INVALID_SCHEME = "invalid_scheme"
    INVALID_HOST = "invalid_host"
    MISSING_WORKSPACE = "missing_workspace"
    INVALID_WORKSPACE = "invalid_workspace"
    UNKNOWN_RESOURCE_TYPE = "unknown_resource_type"
    MISSING_RESOURCE_ID = "missing_resource_id"
    INVALID_RESOURCE_ID = "invalid_resource_id"
    PATH_TRAVERSAL = "path_traversal"
    INVALID_ACTION = "invalid_action"


class DeepLinkParseFailedError(ValueError):
    """Raised by :func:`parse_deep_link_or_raise` when parsing fails.

    ``error`` carries the structured :class:`DeepLinkParseError` so callers can
    branch on the exact failure mode without re-parsing the message.
    """

    def __init__(self, error: DeepLinkParseError, message: str | None = None) -> None:
        super().__init__(message or f"deep link parse failed: {error.value}")
        self.error = error


@dataclass(frozen=True, slots=True)
class DeepLink:
    """Parsed deep link — frozen value object."""

    workspace_id: str
    resource_type: str
    resource_id: str
    action: str | None = None


@dataclass(frozen=True, slots=True)
class DeepLinkParseResult:
    """Result-pattern wrapper. Either ``ok=True`` with ``value`` or
    ``ok=False`` with ``error``.
    """

    ok: bool
    value: DeepLink | None = None
    error: DeepLinkParseError | None = None

    @classmethod
    def success(cls, value: DeepLink) -> DeepLinkParseResult:
        return cls(ok=True, value=value, error=None)

    @classmethod
    def failure(cls, error: DeepLinkParseError) -> DeepLinkParseResult:
        return cls(ok=False, value=None, error=error)


def _contains_traversal(segment: str) -> bool:
    """Reject path traversal disguise in raw (pre-decoded) segments."""

    return ".." in segment or "//" in segment or "\\" in segment


def _decode_segment(segment: str) -> str | None:
    """Best-effort URL-unquote that mirrors ``decodeURIComponent``.

    Returns ``None`` if decoding produces an empty string. ``urllib.parse.unquote``
    silently passes invalid percent escapes through (unlike ``decodeURIComponent``
    which throws), but the downstream ``_ID_PATTERN`` check rejects any bytes
    outside the safe ID alphabet, so behaviour stays equivalent for inputs the
    contract spec covers.
    """

    decoded = unquote(segment)
    return decoded if decoded else None


def parse_deep_link(raw_input: str) -> DeepLinkParseResult:
    """Parse a deep link URI. Pure — never performs I/O."""

    if not isinstance(raw_input, str) or len(raw_input) == 0:
        return DeepLinkParseResult.failure(DeepLinkParseError.INVALID_SCHEME)
    if len(raw_input) > DEEP_LINK_MAX_LENGTH:
        return DeepLinkParseResult.failure(DeepLinkParseError.TOO_LONG)

    try:
        parts = urlsplit(raw_input)
    except ValueError:
        return DeepLinkParseResult.failure(DeepLinkParseError.INVALID_SCHEME)

    if parts.scheme != DEEP_LINK_SCHEME:
        return DeepLinkParseResult.failure(DeepLinkParseError.INVALID_SCHEME)

    # ds-agent://workspace/<id>/...  → hostname = "workspace"
    if (parts.hostname or "").lower() != DEEP_LINK_HOST:
        return DeepLinkParseResult.failure(DeepLinkParseError.INVALID_HOST)

    raw_segments = [seg for seg in parts.path.split("/") if seg]

    if not raw_segments:
        return DeepLinkParseResult.failure(DeepLinkParseError.MISSING_WORKSPACE)

    if _contains_traversal(raw_segments[0]):
        return DeepLinkParseResult.failure(DeepLinkParseError.INVALID_WORKSPACE)
    workspace_id = _decode_segment(raw_segments[0])
    if workspace_id is None or not _ID_PATTERN.match(workspace_id):
        return DeepLinkParseResult.failure(DeepLinkParseError.INVALID_WORKSPACE)

    if len(raw_segments) < 2:
        return DeepLinkParseResult.failure(DeepLinkParseError.UNKNOWN_RESOURCE_TYPE)

    resource_type = raw_segments[1]
    if resource_type not in DEEP_LINK_RESOURCE_TYPES:
        return DeepLinkParseResult.failure(DeepLinkParseError.UNKNOWN_RESOURCE_TYPE)

    if len(raw_segments) < 3:
        return DeepLinkParseResult.failure(DeepLinkParseError.MISSING_RESOURCE_ID)

    # Reject extra path segments — they make path-traversal disguise easier.
    if len(raw_segments) > 3:
        return DeepLinkParseResult.failure(DeepLinkParseError.PATH_TRAVERSAL)

    raw_resource_id = raw_segments[2]
    if _contains_traversal(raw_resource_id):
        return DeepLinkParseResult.failure(DeepLinkParseError.PATH_TRAVERSAL)
    resource_id = _decode_segment(raw_resource_id)
    if resource_id is None or not _ID_PATTERN.match(resource_id):
        return DeepLinkParseResult.failure(DeepLinkParseError.INVALID_RESOURCE_ID)

    action: str | None = None
    if parts.query:
        # Use keep_blank_values so action= is detected as invalid (empty string).
        params = parse_qs(parts.query, keep_blank_values=True)
        raw_actions = params.get("action")
        if raw_actions is not None:
            raw_action = raw_actions[0]
            if not _ACTION_PATTERN.match(raw_action):
                return DeepLinkParseResult.failure(DeepLinkParseError.INVALID_ACTION)
            action = raw_action

    return DeepLinkParseResult.success(
        DeepLink(
            workspace_id=workspace_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
        )
    )


def parse_deep_link_or_raise(raw_input: str) -> DeepLink:
    """Parse a deep link, raising :class:`DeepLinkParseFailedError` on failure."""

    result = parse_deep_link(raw_input)
    if not result.ok or result.value is None:
        # error is non-None whenever ok is False
        assert result.error is not None
        raise DeepLinkParseFailedError(result.error)
    return result.value


def _quote_id(value: str) -> str:
    """Percent-encode an ID. The validated alphabet is URL-safe so this is a
    cheap identity in practice, but using ``quote`` keeps build/parse symmetric
    with the renderer's ``encodeURIComponent``.
    """

    from urllib.parse import quote

    return quote(value, safe="")


def build_deep_link_uri(link: DeepLink) -> str:
    """Build a wire-format URI from a :class:`DeepLink`.

    The output is byte-identical to the renderer's ``buildDeepLinkUri`` for any
    valid input.
    """

    base = (
        f"{DEEP_LINK_SCHEME}://{DEEP_LINK_HOST}"
        f"/{_quote_id(link.workspace_id)}"
        f"/{link.resource_type}"
        f"/{_quote_id(link.resource_id)}"
    )
    if link.action:
        from urllib.parse import urlencode

        return f"{base}?{urlencode({'action': link.action})}"
    return base


__all__ = [
    "DEEP_LINK_HOST",
    "DEEP_LINK_MAX_LENGTH",
    "DEEP_LINK_RESOURCE_TYPES",
    "DEEP_LINK_SCHEME",
    "DeepLink",
    "DeepLinkParseError",
    "DeepLinkParseFailedError",
    "DeepLinkParseResult",
    "build_deep_link_uri",
    "parse_deep_link",
    "parse_deep_link_or_raise",
]
