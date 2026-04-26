"""Backend Sentry integration with runtime-gated telemetry and redaction."""

from __future__ import annotations

import importlib.metadata
import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

import structlog

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint, SamplingContext  # type: ignore[import-not-found]

    from ds_agent.config.schema import DSAgentConfig

sentry_sdk: Any = None
FastApiIntegration: Any = None
LoggingIntegration: Any = None

try:
    import sentry_sdk as _sentry_sdk  # type: ignore[import-not-found]
    from sentry_sdk.integrations.fastapi import (
        FastApiIntegration as _FastApiIntegration,  # type: ignore[import-not-found]
    )
    from sentry_sdk.integrations.logging import (
        LoggingIntegration as _LoggingIntegration,  # type: ignore[import-not-found]
    )

    sentry_sdk = _sentry_sdk
    FastApiIntegration = _FastApiIntegration
    LoggingIntegration = _LoggingIntegration
except ImportError:  # pragma: no cover - optional dependency
    pass

logger = structlog.get_logger()

_REDACTED = "***REDACTED***"
_EMAIL_MASK = "***EMAIL***"
_PHONE_MASK = "***PHONE***"
_CARD_MASK = "***CARD***"
_MAX_REDACT_DEPTH = 8

_SECRET_FIELD_TOKENS = (
    "chat_id",
    "chatid",
    "key",
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
    # PII field-name tokens (Fix Sprint S2)
    "email",
    "phone",
    "mobile",
    "ssn",
    "credit_card",
    "card_number",
    "pan",
)

# Ordered patterns. Token patterns first so that e.g. sk-ant-* is redacted
# before a more general PII rule could otherwise partial-match.
_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "chat_id",
        re.compile(
            r"\b(chat[_-]?id|chatId)(\s*[:=]\s*['\"]?)-?\d{4,}\b(['\"]?)",
            re.IGNORECASE,
        ),
    ),
    ("token", re.compile(r"READY:(\d+):[^\s]+")),
    ("token", re.compile(r"sk-ant-[A-Za-z0-9\-_]+")),
    ("token", re.compile(r"sk-[A-Za-z0-9\-_]{20,}")),
    ("token", re.compile(r"ya29\.[A-Za-z0-9\-_]+")),
    ("token", re.compile(r"1//[A-Za-z0-9\-_]+")),
    ("token", re.compile(r"\b\d{8,}:[A-Za-z0-9\-_]{20,}\b")),
    # PII patterns (Fix Sprint S2).
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    # Phone: optional country code, then 9-14 digits separated by -, ., space
    # or inside parentheses. Anchored at word boundaries to avoid chomping
    # arbitrary long digit sequences. Requires at least one non-digit separator
    # or a leading "+" so that pure digit strings (UUID segments, hashes, ids)
    # are not captured as phone numbers.
    (
        "phone",
        re.compile(
            r"(?<![\w.])"
            r"(?:\+\d{1,3}[-.\s]\d{1,4}[-.\s]\d{3,4}[-.\s]\d{3,4}"
            r"|\+\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]\d{3,4}[-.\s]\d{3,4}"
            r"|\(?\d{3}\)?[-.\s]\d{3,4}[-.\s]\d{3,4})"
            r"(?![\w.])"
        ),
    ),
    # Credit card: 13-19 digits optionally separated by single spaces or
    # hyphens. Luhn validation is performed in _replace_secret_match so
    # random 16-digit sequences do not trigger false positives.
    ("card", re.compile(r"\b(?:\d[ -]?){12,18}\d\b")),
)

_state = {
    "initialized": False,
    "dsn": None,
    "environment": "production",
    "error_reporting_enabled": False,
    "telemetry_enabled": False,
}


def configure_backend_observability(config: DSAgentConfig) -> None:
    """Initialize or update backend Sentry settings from config."""

    observability = config.observability
    _state["dsn"] = observability.sentry_dsn
    _state["environment"] = observability.sentry_environment
    _state["error_reporting_enabled"] = observability.error_reporting_enabled
    _state["telemetry_enabled"] = observability.telemetry_enabled

    if sentry_sdk is None or not observability.sentry_dsn:
        if observability.sentry_dsn and sentry_sdk is None:
            logger.warning("backend_sentry_unavailable", reason="missing_sentry_sdk")
        return

    if cast(bool, _state["initialized"]):
        return

    logging_integration = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
    fastapi_integration = FastApiIntegration(transaction_style="endpoint")

    sentry_sdk.init(
        dsn=observability.sentry_dsn,
        environment=observability.sentry_environment,
        release=_package_version(),
        send_default_pii=False,
        traces_sampler=_backend_traces_sampler,
        profiles_sample_rate=0.05,
        before_send=redact_backend_sentry_event,
        before_send_transaction=redact_backend_sentry_transaction,
        integrations=[fastapi_integration, logging_integration],
    )
    _state["initialized"] = True
    logger.info(
        "backend_sentry_initialized",
        environment=observability.sentry_environment,
        telemetry_enabled=observability.telemetry_enabled,
        error_reporting_enabled=observability.error_reporting_enabled,
    )


def shutdown_backend_observability(timeout: float = 2.0) -> None:
    """Flush and close the backend Sentry client when initialized."""

    if sentry_sdk is None or not cast(bool, _state["initialized"]):
        return

    try:
        sentry_sdk.flush(timeout=timeout)
        sentry_sdk.get_client().close(timeout=timeout)
    except Exception as exc:  # pragma: no cover - defensive shutdown path
        logger.warning("backend_sentry_shutdown_failed", error=str(exc))
    finally:
        _state["initialized"] = False


def add_backend_breadcrumb(
    category: str,
    *,
    message: str | None = None,
    data: dict[str, Any] | None = None,
    level: str = "info",
) -> None:
    """Add a redacted Sentry breadcrumb when backend observability is active."""

    if (
        sentry_sdk is None
        or not cast(bool, _state["initialized"])
        or not _state["dsn"]
        or not _backend_observability_active()
    ):
        return

    try:
        sentry_sdk.add_breadcrumb(
            category=_redact_text(category),
            message=None if message is None else _redact_text(message),
            data=cast(dict[str, Any], _deep_redact(data or {})),
            level=_redact_text(level),
        )
    except Exception as exc:  # pragma: no cover - defensive optional telemetry path
        logger.debug("backend_sentry_breadcrumb_failed", error=str(exc))


def redact_backend_sentry_event(event: Event, _hint: Hint) -> Event | None:
    """Redact secrets and gate error events by current runtime settings."""

    if not cast(bool, _state["error_reporting_enabled"]):
        return None
    return cast("Event", _deep_redact(event))


def redact_backend_sentry_transaction(
    event: Event,
    _hint: Hint,
) -> Event | None:
    """Redact secrets and gate transaction events by current runtime settings."""

    if not cast(bool, _state["telemetry_enabled"]):
        return None
    return cast("Event", _deep_redact(event))


def _backend_traces_sampler(_sampling_context: SamplingContext) -> float:
    return 0.1 if cast(bool, _state["telemetry_enabled"]) else 0.0


def _backend_observability_active() -> bool:
    return cast(bool, _state["error_reporting_enabled"]) or cast(
        bool,
        _state["telemetry_enabled"],
    )


def _deep_redact(value: Any, depth: int = 0) -> Any:
    if depth >= _MAX_REDACT_DEPTH:
        # Depth budget exhausted: stringify and scrub the serialized form so
        # unbounded nesting cannot bypass PII redaction.
        if isinstance(value, str):
            return _redact_text(value)
        return value
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [_deep_redact(item, depth + 1) for item in value]
    if isinstance(value, tuple):
        return tuple(_deep_redact(item, depth + 1) for item in value)
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if any(token in key_lower for token in _SECRET_FIELD_TOKENS):
                redacted[key] = _REDACTED
                continue
            redacted[key] = _deep_redact(item, depth + 1)
        return redacted
    return value


def _redact_text(text: str) -> str:
    sanitized = text
    for kind, pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(_make_substitutor(kind), sanitized)
    return sanitized


def _make_substitutor(kind: str) -> Callable[[re.Match[str]], str]:
    def _sub(match: re.Match[str]) -> str:
        return _replace_secret_match(match, kind)

    return _sub


def _replace_secret_match(match: re.Match[str], kind: str) -> str:
    full_match = match.group(0)
    if kind == "chat_id":
        return f"{match.group(1)}{match.group(2)}{_REDACTED}{match.group(3)}"
    if kind == "token":
        if full_match.startswith("READY:"):
            return f"READY:{match.group(1)}:{_REDACTED}"
        return _REDACTED
    if kind == "email":
        return _EMAIL_MASK
    if kind == "phone":
        return _PHONE_MASK
    if kind == "card":
        digits = re.sub(r"\D", "", full_match)
        if 13 <= len(digits) <= 19 and _luhn_valid(digits):
            return _CARD_MASK
        return full_match
    return _REDACTED


def _luhn_valid(digits: str) -> bool:
    """Return True if ``digits`` satisfies the Luhn check.

    Used to suppress false positives on arbitrary long digit sequences that
    are not valid payment-card numbers (UUID fragments, counters, hashes).
    """

    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        if not char.isdigit():
            return False
        digit = int(char)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _package_version() -> str:
    try:
        return importlib.metadata.version("ds-agent")
    except importlib.metadata.PackageNotFoundError:
        return "0.1.0"
