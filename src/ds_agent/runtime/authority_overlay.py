"""Runtime helpers for incident/freeze authority overlays."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ds_agent.domain.value_objects.authority_mode import AuthorityMode

_INCIDENT_WINDOW = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class AuthorityOverlayState:
    """Resolved authority overlay metadata."""

    mode: AuthorityMode | None = None
    started_at: datetime | None = None
    expires_at: datetime | None = None
    expired: bool = False


def resolve_authority_overlay(
    raw_mode: str | AuthorityMode | None,
    raw_started_at: str | None,
    *,
    now: datetime | None = None,
) -> AuthorityOverlayState:
    """Resolve the currently effective authority overlay."""

    mode = _coerce_overlay_mode(raw_mode)
    if mode is None:
        return AuthorityOverlayState()

    started_at = _parse_datetime(raw_started_at)
    if mode is not AuthorityMode.INCIDENT:
        return AuthorityOverlayState(mode=mode)

    if started_at is None:
        return AuthorityOverlayState(mode=mode)

    current_time = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    expires_at = started_at + _INCIDENT_WINDOW
    if current_time >= expires_at:
        return AuthorityOverlayState(
            started_at=started_at,
            expires_at=expires_at,
            expired=True,
        )
    return AuthorityOverlayState(
        mode=mode,
        started_at=started_at,
        expires_at=expires_at,
    )


def new_incident_started_at(*, now: datetime | None = None) -> str:
    """Return a persisted UTC timestamp for a newly started incident."""

    current_time = now.astimezone(UTC) if now is not None else datetime.now(UTC)
    return current_time.isoformat()


def effective_authority_mode(
    *,
    legacy_mode: str | None,
    overlay_mode: str | AuthorityMode | None,
    overlay_started_at: str | None,
    now: datetime | None = None,
) -> AuthorityMode:
    """Resolve the effective authority mode after applying an overlay."""

    overlay = resolve_authority_overlay(overlay_mode, overlay_started_at, now=now)
    if overlay.mode is not None:
        return overlay.mode
    return AuthorityMode.from_legacy_agent_mode(legacy_mode)


def _coerce_overlay_mode(value: str | AuthorityMode | None) -> AuthorityMode | None:
    if value is None or not str(value).strip():
        return None
    try:
        resolved = AuthorityMode.coerce(value)
    except ValueError:
        return None
    if resolved not in {AuthorityMode.INCIDENT, AuthorityMode.FREEZE}:
        return None
    return resolved


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
