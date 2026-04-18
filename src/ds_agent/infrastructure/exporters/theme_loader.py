"""Filesystem-backed theme resolution for stakeholder delivery artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ds_agent.domain.entities.delivery_pack import DeliveryPack, DesignTheme

DEFAULT_THEME = DesignTheme(
    theme_id="default_v1",
    primary_color="#1F3A5F",
    secondary_color="#6C7F99",
    font_heading="Aptos Display",
    font_body="Aptos",
    chart_palette=["#1F3A5F", "#6C7F99", "#B5C3D6"],
)


@dataclass(frozen=True, slots=True)
class ThemeSettings:
    """Static tenant-to-theme defaults loaded from YAML."""

    default_theme: str = DEFAULT_THEME.theme_id
    tenant_defaults: dict[str, str] = field(default_factory=dict)


class FileSystemThemeLoader:
    """Resolve delivery themes from checked-in theme assets and YAML defaults."""

    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        themes_root: str | Path | None = None,
        fallback_theme: DesignTheme | None = None,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        self._config_path = (
            Path(config_path)
            if config_path is not None
            else repo_root / "config" / "themes.yaml"
        )
        self._themes_root = (
            Path(themes_root)
            if themes_root is not None
            else repo_root / "assets" / "themes"
        )
        self._fallback_theme = fallback_theme or DEFAULT_THEME

    def resolve(self, *, pack: DeliveryPack | None = None) -> DesignTheme:
        explicit_theme_id = self._explicit_theme_id(pack)
        if explicit_theme_id is not None:
            return self._safe_load(explicit_theme_id)

        settings = self._load_settings()
        if pack is not None and pack.tenant:
            tenant_theme = settings.tenant_defaults.get(pack.tenant)
            if tenant_theme:
                return self._safe_load(tenant_theme)
        return self._safe_load(settings.default_theme)

    def load(self, theme_id: str) -> DesignTheme:
        candidate = self._themes_root / str(theme_id) / "theme.json"
        if not candidate.exists():
            raise FileNotFoundError(f"Theme asset not found: {theme_id}")
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        return DesignTheme.model_validate(payload)

    def _safe_load(self, theme_id: str) -> DesignTheme:
        try:
            return self.load(theme_id)
        except Exception:
            return self._fallback_theme

    def _load_settings(self) -> ThemeSettings:
        if not self._config_path.exists():
            return ThemeSettings(
                default_theme=self._fallback_theme.theme_id,
                tenant_defaults={"default": self._fallback_theme.theme_id},
            )
        raw = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            return ThemeSettings(default_theme=self._fallback_theme.theme_id)
        default_theme = raw.get("default_theme") or self._fallback_theme.theme_id
        tenant_defaults = raw.get("tenant_defaults") or {}
        if not isinstance(tenant_defaults, dict):
            tenant_defaults = {}
        return ThemeSettings(
            default_theme=str(default_theme),
            tenant_defaults={str(key): str(value) for key, value in tenant_defaults.items()},
        )

    @staticmethod
    def _explicit_theme_id(pack: DeliveryPack | None) -> str | None:
        if pack is None:
            return None
        raw = pack.global_context.get("theme_id")
        if raw is None:
            return None
        normalized = str(raw).strip()
        return normalized or None
