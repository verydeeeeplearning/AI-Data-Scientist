from datetime import UTC, datetime, timedelta

from ds_agent.domain.value_objects.authority_mode import AuthorityMode
from ds_agent.runtime.authority_overlay import (
    effective_authority_mode,
    resolve_authority_overlay,
)


class TestAuthorityOverlay:
    def test_resolve_no_overlay(self):
        overlay = resolve_authority_overlay(None, None)

        assert overlay.mode is None
        assert overlay.started_at is None
        assert overlay.expires_at is None
        assert overlay.expired is False

    def test_incident_overlay_exposes_expiry_window(self):
        now = datetime(2026, 4, 16, 12, 0, tzinfo=UTC)
        overlay = resolve_authority_overlay(
            "incident",
            "2026-04-16T09:00:00+00:00",
            now=now,
        )

        assert overlay.mode == AuthorityMode.INCIDENT
        assert overlay.started_at == datetime(2026, 4, 16, 9, 0, tzinfo=UTC)
        assert overlay.expires_at == datetime(2026, 4, 17, 9, 0, tzinfo=UTC)
        assert overlay.expired is False

    def test_expired_incident_overlay_falls_back_to_legacy_mode(self):
        started = datetime(2026, 4, 15, 8, 0, tzinfo=UTC)
        now = started + timedelta(hours=25)

        overlay = resolve_authority_overlay("incident", started.isoformat(), now=now)
        effective = effective_authority_mode(
            legacy_mode="auto",
            overlay_mode="incident",
            overlay_started_at=started.isoformat(),
            now=now,
        )

        assert overlay.mode is None
        assert overlay.expired is True
        assert effective == AuthorityMode.DELEGATE

    def test_freeze_overlay_ignores_started_at(self):
        overlay = resolve_authority_overlay(
            "freeze",
            "2026-04-16T09:00:00+00:00",
        )

        assert overlay.mode == AuthorityMode.FREEZE
        assert overlay.started_at is None
        assert overlay.expires_at is None
