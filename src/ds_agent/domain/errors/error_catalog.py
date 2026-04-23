"""DS Agent user-facing error code catalog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCode:
    """Stable user-facing error metadata."""

    code: str
    user_message: str
    support_message: str
    recovery_hint: str


ERROR_CATALOG: dict[str, ErrorCode] = {
    "DSA-AUTH-001": ErrorCode(
        code="DSA-AUTH-001",
        user_message="The configured API key was rejected.",
        support_message="Provider API key validation failed or returned 401/403.",
        recovery_hint="Check the API key in Settings and try again.",
    ),
    "DSA-AUTH-002": ErrorCode(
        code="DSA-AUTH-002",
        user_message="The saved sign-in or connector credentials were rejected.",
        support_message="OAuth or connector credential refresh/login failed.",
        recovery_hint="Reconnect the account or update the saved secret, then retry.",
    ),
    "DSA-TOOL-001": ErrorCode(
        code="DSA-TOOL-001",
        user_message="A tool failed while running your request.",
        support_message="A registered tool raised an exception during execution.",
        recovery_hint="Retry with a simpler request or ask the agent to use another approach.",
    ),
    "DSA-SAND-001": ErrorCode(
        code="DSA-SAND-001",
        user_message="The requested action was blocked by the sandbox policy.",
        support_message="Sandbox or workspace-boundary enforcement blocked the action.",
        recovery_hint="Keep file access inside the workspace or request an allowed path.",
    ),
    "DSA-FILE-001": ErrorCode(
        code="DSA-FILE-001",
        user_message="A file could not be read or parsed.",
        support_message="File load/preview/read failed due to path, format, or encoding issues.",
        recovery_hint="Check the file path, format, and encoding, then retry.",
    ),
    "DSA-FILE-002": ErrorCode(
        code="DSA-FILE-002",
        user_message="A file could not be written or exported.",
        support_message="File save/export failed.",
        recovery_hint="Choose a valid output path and try the export again.",
    ),
    "DSA-LLM-001": ErrorCode(
        code="DSA-LLM-001",
        user_message="The AI service is temporarily unavailable.",
        support_message="LLM provider returned a timeout, 5xx, or transient network failure.",
        recovery_hint="Wait a moment and retry, or switch to another model.",
    ),
    "DSA-LLM-002": ErrorCode(
        code="DSA-LLM-002",
        user_message="The AI service quota or rate limit was reached.",
        support_message="LLM provider returned rate-limit or quota errors.",
        recovery_hint="Wait for the limit window to reset or use another provider.",
    ),
    "DSA-SYS-001": ErrorCode(
        code="DSA-SYS-001",
        user_message="An unexpected internal error occurred.",
        support_message="Unhandled application exception.",
        recovery_hint="Retry the action. If it keeps failing, export a support bundle.",
    ),
    "DSA-SYS-002": ErrorCode(
        code="DSA-SYS-002",
        user_message="The request parameters were invalid.",
        support_message="Client-supplied parameters failed validation.",
        recovery_hint="Review the field values and try again.",
    ),
    "DSA-SYS-003": ErrorCode(
        code="DSA-SYS-003",
        user_message="The external service did not respond in time.",
        support_message="Timeout while calling an external dependency.",
        recovery_hint="Retry after a short delay or verify the remote service is reachable.",
    ),
    "DSA-SYS-004": ErrorCode(
        code="DSA-SYS-004",
        user_message="The external service connection failed.",
        support_message=(
            "External dependency connection failed before a valid response was received."
        ),
        recovery_hint="Verify the remote host, credentials, and network access, then retry.",
    ),
}

_DEFAULT_ERROR_CODE = ERROR_CATALOG["DSA-SYS-001"]


def get_error_code(code: str) -> ErrorCode:
    """Return catalog metadata for a stable error code."""

    return ERROR_CATALOG.get(code, _DEFAULT_ERROR_CODE)


def format_error_message(
    code: str,
    *,
    override_message: str | None = None,
    include_hint: bool = True,
) -> str:
    """Render a user-facing message that always includes the stable code."""

    error = get_error_code(code)
    message = override_message or error.user_message
    rendered = f"{message} [{error.code}]"
    if include_hint and error.recovery_hint:
        rendered = f"{rendered} {error.recovery_hint}"
    return rendered
