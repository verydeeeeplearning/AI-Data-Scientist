"""Helpers for migrating legacy run modes into autonomy control-plane axes."""

from __future__ import annotations

from dataclasses import dataclass

from ds_agent.domain.value_objects.audience_persona import AudiencePersona
from ds_agent.domain.value_objects.authority_mode import AuthorityMode


@dataclass(frozen=True, slots=True)
class LegacyModeMigrationPreview:
    """Operator-facing preview of the recommended autonomy-axis migration."""

    legacy_mode: str
    authority: AuthorityMode
    audience: AudiencePersona
    exact_match: bool
    notes: tuple[str, ...]


def build_legacy_mode_migration_preview(
    legacy_mode: str | None,
) -> LegacyModeMigrationPreview:
    """Return the recommended explicit authority/audience mapping.

    The legacy runtime mode still exists as a compatibility layer. This helper
    exposes the closest explicit control-plane settings so operators can move
    active sessions onto task-contract fields intentionally.
    """

    normalized = _normalize_legacy_mode(legacy_mode)
    authority = AuthorityMode.from_legacy_agent_mode(normalized)
    audience = AudiencePersona.from_legacy_agent_mode(normalized)

    if normalized == "auto":
        notes = (
            "Routine delegated work maps cleanly to delegate authority.",
            (
                "Add a mission pack before enabling autopilot so certification "
                "and scope stay explicit."
            ),
        )
        return LegacyModeMigrationPreview(
            legacy_mode=normalized,
            authority=authority,
            audience=audience,
            exact_match=True,
            notes=notes,
        )

    if normalized == "supervised":
        notes = (
            (
                "Sensitive or write-side actions will keep routing to approval "
                "under supervised authority."
            ),
            (
                "Promote only the sessions that need autonomy; leave audience "
                "inherit when the default peer DS tone is acceptable."
            ),
        )
        return LegacyModeMigrationPreview(
            legacy_mode=normalized,
            authority=authority,
            audience=audience,
            exact_match=True,
            notes=notes,
        )

    notes = (
        (
            "Step-by-step has no exact authority-axis equivalent; supervised "
            "is the closest authority fallback."
        ),
        (
            "Keep the legacy mode until you replace per-step approvals with "
            "explicit action-matrix overrides or a freeze/shadow guardrail."
        ),
    )
    return LegacyModeMigrationPreview(
        legacy_mode=normalized,
        authority=authority,
        audience=audience,
        exact_match=False,
        notes=notes,
    )


def _normalize_legacy_mode(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "auto"

    normalized = str(value).strip().lower().replace("_", "-")
    if normalized == "step-by-step":
        return normalized
    if normalized in {"auto", "supervised"}:
        return normalized
    raise ValueError(f"Unsupported legacy agent mode: {value}")
