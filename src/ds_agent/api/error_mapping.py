"""User-facing error mapping for RPC and connector surfaces."""

from __future__ import annotations

from dataclasses import dataclass

from ds_agent.domain.errors import format_error_message, get_error_code


@dataclass(frozen=True)
class ErrorPresentation:
    """Resolved user-facing error content for one failure."""

    catalog_code: str
    message: str
    support_message: str
    recovery_hint: str
    technical_message: str | None = None

    @property
    def warnings(self) -> list[str]:
        return [self.recovery_hint] if self.recovery_hint else []


def present_invalid_params_error(raw_message: str) -> ErrorPresentation:
    """Preserve validation detail while attaching a stable DSA code."""

    catalog_code = "DSA-SYS-002"
    catalog = get_error_code(catalog_code)
    return ErrorPresentation(
        catalog_code=catalog_code,
        message=format_error_message(
            catalog_code,
            override_message=raw_message,
            include_hint=False,
        ),
        support_message=catalog.support_message,
        recovery_hint=catalog.recovery_hint,
        technical_message=raw_message,
    )


def present_rpc_exception(method: str, exc: BaseException) -> ErrorPresentation:
    """Map an exception to a stable DSA catalog code and message."""

    technical_message = str(exc).strip() or exc.__class__.__name__
    catalog_code = _classify_catalog_code(method, technical_message.lower())
    catalog = get_error_code(catalog_code)
    return ErrorPresentation(
        catalog_code=catalog_code,
        message=format_error_message(catalog_code),
        support_message=catalog.support_message,
        recovery_hint=catalog.recovery_hint,
        technical_message=technical_message,
    )


def _classify_catalog_code(method: str, message: str) -> str:
    if any(token in message for token in ("rate limit", "quota", "too many requests", "429")):
        return "DSA-LLM-002"

    if any(
        token in message
        for token in (
            "sandbox",
            "workspace boundary",
            "outside workspace",
            "not allowed to access",
            "blocked by policy",
        )
    ):
        return "DSA-SAND-001"

    if method.startswith("files.export"):
        return "DSA-FILE-002"

    if method.startswith("files.") and any(
        token in message
        for token in (
            "encoding",
            "codec",
            "csv",
            "excel",
            "parquet",
            "sheet",
            "file not found",
            "no such file",
            "cannot read",
            "failed to read",
        )
    ):
        return "DSA-FILE-001"

    if method.startswith("connector.") and any(
        token in message
        for token in (
            "auth",
            "password",
            "login",
            "credential",
            "unauthorized",
            "forbidden",
            "access denied",
            "expired token",
        )
    ):
        return "DSA-AUTH-002"

    if method.startswith(("chat.", "provider.")) and any(
        token in message
        for token in (
            "401",
            "403",
            "api key",
            "invalid api key",
            "authentication",
            "unauthorized",
        )
    ):
        return "DSA-AUTH-001"

    if "timeout" in message or "timed out" in message:
        return "DSA-SYS-003" if method.startswith("connector.") else "DSA-LLM-001"

    if method.startswith("connector."):
        return "DSA-SYS-004"

    if method.startswith("files."):
        return "DSA-FILE-001"

    if method.startswith(("chat.", "provider.")):
        return "DSA-LLM-001"

    return "DSA-SYS-001"
