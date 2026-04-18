"""Quality preset helpers for end-user model abstraction UX."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class QualityPreset(StrEnum):
    """User-facing AI quality presets."""

    BEST_QUALITY = "best_quality"
    BALANCED = "balanced"
    FAST = "fast"
    LOCAL = "local"
    CUSTOM = "custom"


@dataclass(frozen=True)
class QualityPresetConfig:
    """Resolved model configuration for one preset."""

    primary: str
    fallback: tuple[str, ...]
    label: str
    description: str


PRESET_MODEL_MAP: dict[QualityPreset, QualityPresetConfig] = {
    QualityPreset.BEST_QUALITY: QualityPresetConfig(
        primary="anthropic/claude-opus-4-6",
        fallback=("openai/gpt-4.1",),
        label="Best Quality",
        description="Best for deeper analysis and richer reports.",
    ),
    QualityPreset.BALANCED: QualityPresetConfig(
        primary="anthropic/claude-sonnet-4-6",
        fallback=("openai/gpt-4.1-mini",),
        label="Balanced",
        description="Recommended for most data science work.",
    ),
    QualityPreset.FAST: QualityPresetConfig(
        primary="anthropic/claude-haiku-4-5",
        fallback=("openai/gpt-4.1-mini",),
        label="Fast",
        description="Best for lighter questions and quick checks.",
    ),
    QualityPreset.LOCAL: QualityPresetConfig(
        primary="ollama/llama3.2",
        fallback=(),
        label="Local",
        description="Runs on this computer without a cloud account.",
    ),
}

SIMPLE_QUALITY_PRESETS: tuple[QualityPreset, ...] = (
    QualityPreset.BEST_QUALITY,
    QualityPreset.BALANCED,
    QualityPreset.FAST,
    QualityPreset.LOCAL,
)


def coerce_quality_preset(value: QualityPreset | str) -> QualityPreset:
    """Normalize a persisted or UI-provided preset value."""

    if isinstance(value, QualityPreset):
        return value
    return QualityPreset(str(value).strip().lower())


def get_quality_preset_config(preset: QualityPreset | str) -> QualityPresetConfig:
    """Return the concrete model configuration for a simple preset."""

    resolved = coerce_quality_preset(preset)
    if resolved == QualityPreset.CUSTOM:
        raise ValueError("Custom preset does not map to a fixed model configuration.")
    return PRESET_MODEL_MAP[resolved]


def detect_quality_preset(
    default_model: str,
    fallback_models: list[str] | tuple[str, ...] | None,
) -> QualityPreset:
    """Infer which preset matches the current model/fallback tuple."""

    normalized_fallbacks = tuple(fallback_models or ())
    for preset in SIMPLE_QUALITY_PRESETS:
        config = PRESET_MODEL_MAP[preset]
        if default_model != config.primary:
            continue
        if not normalized_fallbacks or normalized_fallbacks == config.fallback:
            return preset
    return QualityPreset.CUSTOM
