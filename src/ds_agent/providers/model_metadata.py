"""Capability metadata for the LLM model catalog.

Phase 1 PLAN_06 (Model Capability Labels). Provides a curated mapping from
catalog model id to user-facing capability metadata (group, badges, recommended
use cases) plus a deterministic heuristic fallback for unknown ids so the
renderer never has to guess.

This module is metadata-only and does not change provider routing or
LLMRegistry behavior. Consumed by ``api/ws_handler.py::_provider_models()`` to
enrich the ``provider.models`` RPC response so the renderer can stop relying
solely on its own heuristic profiling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

CapabilityGroup = Literal[
    "fast_start",
    "best_quality",
    "cost_optimized",
    "privacy_first",
    "offline_capable",
]

CapabilityBadge = Literal[
    "fast",
    "cheap",
    "strong_coding",
    "strong_korean",
    "offline",
    "long_context",
    "strong_reasoning",
    "multimodal",
]

AuthType = Literal["api_key", "oauth", "free_api_key", "local"]


CAPABILITY_GROUPS: Final[tuple[CapabilityGroup, ...]] = (
    "fast_start",
    "best_quality",
    "cost_optimized",
    "privacy_first",
    "offline_capable",
)

CAPABILITY_BADGES: Final[tuple[CapabilityBadge, ...]] = (
    "fast",
    "cheap",
    "strong_coding",
    "strong_korean",
    "offline",
    "long_context",
    "strong_reasoning",
    "multimodal",
)


@dataclass(frozen=True)
class ModelCapabilityMetadata:
    capability_group: CapabilityGroup
    capability_badges: tuple[CapabilityBadge, ...]
    recommended_for: tuple[str, ...]
    provider_label_legacy: str | None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "capabilityGroup": self.capability_group,
            "capabilityBadges": list(self.capability_badges),
            "recommendedFor": list(self.recommended_for),
        }
        if self.provider_label_legacy is not None:
            payload["providerLabelLegacy"] = self.provider_label_legacy
        return payload


_CuratedEntry = tuple[
    CapabilityGroup,
    tuple[CapabilityBadge, ...],
    tuple[str, ...],
]


_PROVIDER_DISPLAY: Final[dict[str, str]] = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "codex": "OpenAI Codex (ChatGPT)",
    "gemini": "Google Gemini",
    "deepseek": "DeepSeek",
    "minimax": "MiniMax",
    "qwen": "Alibaba Qwen",
    "zhipu": "Zhipu GLM",
    "moonshot": "Moonshot Kimi",
    "groq": "Groq",
    "ollama": "Ollama (Local)",
    "litellm": "LiteLLM",
}


# Curated capability metadata for every model id known to ship with the
# product. Keys MUST match the ids surfaced by ``_provider_models()``.
_CURATED: Final[dict[str, _CuratedEntry]] = {
    # === Anthropic ===
    "anthropic/claude-opus-4-6": (
        "best_quality",
        ("strong_reasoning", "long_context", "multimodal", "strong_coding"),
        ("deep_analysis", "decision_ready_reports", "reasoning", "long_context"),
    ),
    "anthropic/claude-sonnet-4-6": (
        "best_quality",
        ("strong_reasoning", "long_context", "strong_coding", "multimodal"),
        ("deep_analysis", "coding", "long_context"),
    ),
    "anthropic/claude-haiku-4-5": (
        "fast_start",
        ("fast", "cheap", "multimodal", "strong_coding"),
        ("first_run", "quick_checks", "iteration"),
    ),
    "anthropic/claude-opus-4": (
        "best_quality",
        ("strong_reasoning", "multimodal"),
        ("deep_analysis", "reasoning"),
    ),
    "anthropic/claude-sonnet-4": (
        "best_quality",
        ("strong_reasoning", "multimodal"),
        ("deep_analysis",),
    ),
    "anthropic/claude-haiku-3.5": (
        "cost_optimized",
        ("fast", "cheap", "multimodal"),
        ("iteration", "budget_sensitive"),
    ),
    # === OpenAI native ===
    "openai/gpt-5.4": (
        "best_quality",
        ("strong_reasoning", "long_context", "multimodal"),
        ("deep_analysis", "decision_ready_reports", "reasoning"),
    ),
    "openai/gpt-5.4-mini": (
        "cost_optimized",
        ("fast", "cheap", "multimodal"),
        ("iteration", "budget_sensitive"),
    ),
    "openai/gpt-5.4-nano": (
        "cost_optimized",
        ("fast", "cheap"),
        ("iteration", "budget_sensitive"),
    ),
    "openai/gpt-4.1": (
        "best_quality",
        ("strong_reasoning", "long_context"),
        ("deep_analysis", "long_context"),
    ),
    "openai/gpt-4.1-mini": (
        "cost_optimized",
        ("fast", "cheap", "long_context"),
        ("iteration", "budget_sensitive"),
    ),
    "openai/gpt-4.1-nano": (
        "cost_optimized",
        ("fast", "cheap"),
        ("iteration", "budget_sensitive"),
    ),
    "openai/o1": (
        "best_quality",
        ("strong_reasoning",),
        ("reasoning", "deep_analysis"),
    ),
    "openai/o3": (
        "best_quality",
        ("strong_reasoning",),
        ("reasoning", "deep_analysis"),
    ),
    "openai/o3-mini": (
        "cost_optimized",
        ("strong_reasoning", "cheap"),
        ("reasoning", "budget_sensitive"),
    ),
    "openai/o4-mini": (
        "cost_optimized",
        ("strong_reasoning", "cheap"),
        ("reasoning", "budget_sensitive"),
    ),
    "openai/gpt-4o": (
        "best_quality",
        ("multimodal", "strong_reasoning"),
        ("deep_analysis", "vision"),
    ),
    # === Codex OAuth ===
    "codex/gpt-5.4": (
        "fast_start",
        ("fast", "strong_reasoning", "long_context"),
        ("first_run", "deep_analysis"),
    ),
    "codex/gpt-5.3-codex": (
        "fast_start",
        ("strong_coding", "long_context", "fast"),
        ("first_run", "coding"),
    ),
    "codex/gpt-5.3-codex-spark": (
        "fast_start",
        ("strong_coding", "fast"),
        ("first_run", "coding"),
    ),
    "codex/gpt-5.2-codex": (
        "fast_start",
        ("strong_coding", "long_context"),
        ("coding",),
    ),
    "codex/gpt-5.1-codex": (
        "fast_start",
        ("strong_coding", "long_context"),
        ("coding",),
    ),
    "codex/gpt-5.1-codex-mini": (
        "fast_start",
        ("strong_coding", "fast"),
        ("coding",),
    ),
    # === Gemini OAuth / API ===
    "gemini/gemini-3-pro-preview": (
        "best_quality",
        ("strong_reasoning", "long_context", "multimodal"),
        ("deep_analysis", "long_context"),
    ),
    "gemini/gemini-3-flash-preview": (
        "fast_start",
        ("fast", "long_context", "multimodal"),
        ("first_run", "quick_checks"),
    ),
    "gemini/gemini-3.1-pro-preview": (
        "best_quality",
        ("strong_reasoning", "long_context", "multimodal"),
        ("deep_analysis", "long_context"),
    ),
    "gemini/gemini-3.1-flash-lite-preview": (
        "cost_optimized",
        ("fast", "cheap", "long_context"),
        ("iteration", "budget_sensitive"),
    ),
    "gemini/gemini-2.5-pro": (
        "best_quality",
        ("strong_reasoning", "long_context", "multimodal"),
        ("deep_analysis", "long_context"),
    ),
    "gemini/gemini-2.5-flash": (
        "fast_start",
        ("fast", "long_context", "multimodal"),
        ("first_run", "quick_checks"),
    ),
    "gemini/gemini-2.5-flash-lite": (
        "cost_optimized",
        ("fast", "cheap", "long_context"),
        ("iteration", "budget_sensitive"),
    ),
    # === LiteLLM-routed (Chinese providers, Groq) ===
    "deepseek/deepseek-chat": (
        "cost_optimized",
        ("cheap", "strong_coding"),
        ("iteration", "budget_sensitive", "coding"),
    ),
    "deepseek/deepseek-reasoner": (
        "cost_optimized",
        ("strong_reasoning", "cheap"),
        ("reasoning", "budget_sensitive"),
    ),
    "minimax/MiniMax-M2.5": (
        "privacy_first",
        ("long_context", "cheap"),
        ("byo_credentials", "long_context"),
    ),
    "qwen/qwen3.6-plus-preview": (
        "cost_optimized",
        ("cheap", "long_context", "strong_korean"),
        ("budget_sensitive", "long_context", "korean"),
    ),
    "qwen/qwen3.5-plus": (
        "privacy_first",
        ("long_context", "strong_korean"),
        ("byo_credentials", "long_context", "korean"),
    ),
    "zhipu/glm-5": (
        "privacy_first",
        ("strong_reasoning", "long_context"),
        ("byo_credentials", "reasoning"),
    ),
    "moonshot/kimi-k2.5": (
        "privacy_first",
        ("long_context", "strong_reasoning"),
        ("byo_credentials", "long_context", "reasoning"),
    ),
    "groq/llama-4-scout-17b-16e-instruct": (
        "fast_start",
        ("fast", "cheap"),
        ("first_run", "quick_checks", "budget_sensitive"),
    ),
    "groq/qwen3-32b": (
        "fast_start",
        ("fast", "cheap"),
        ("first_run", "quick_checks", "budget_sensitive"),
    ),
    "groq/llama-3.3-70b-versatile": (
        "fast_start",
        ("fast", "cheap"),
        ("first_run", "quick_checks", "budget_sensitive"),
    ),
}


def _build_provider_label_legacy(
    *, provider: str, display_name: str, model_id: str
) -> str:
    provider_label = _PROVIDER_DISPLAY.get(provider, provider.title())
    return f"Previously: {provider_label} {display_name} ({model_id})"


MODEL_CAPABILITY_REGISTRY: Final[dict[str, ModelCapabilityMetadata]] = {
    model_id: ModelCapabilityMetadata(
        capability_group=group,
        capability_badges=badges,
        recommended_for=recommended,
        # provider_label_legacy is generated lazily in derive_capability_metadata
        # so we have access to display_name; keep it None in the static registry.
        provider_label_legacy=None,
    )
    for model_id, (group, badges, recommended) in _CURATED.items()
}


def get_capability_metadata(model_id: str) -> ModelCapabilityMetadata | None:
    """Return curated capability metadata for ``model_id`` or None if unknown."""
    return MODEL_CAPABILITY_REGISTRY.get(model_id)


_FAST_TOKENS: Final[tuple[str, ...]] = (
    "flash",
    "haiku",
    "mini",
    "nano",
    "spark",
    "scout",
)
_CHEAP_TOKENS: Final[tuple[str, ...]] = (
    "haiku",
    "mini",
    "nano",
    "flash-lite",
    "deepseek-chat",
    "scout",
)
_REASONING_TOKENS: Final[tuple[str, ...]] = (
    "opus",
    "sonnet",
    "reasoner",
    "r1",
    "gpt-5",
    "gpt-4.1",
    "pro",
    "glm-5",
    "kimi-k2.5",
    "o1",
    "o3",
    "o4",
)
_CODING_TOKENS: Final[tuple[str, ...]] = ("codex", "claude", "gpt", "qwen", "deepseek")
_KOREAN_PROVIDERS: Final[frozenset[str]] = frozenset(
    {"anthropic", "openai", "codex", "gemini", "deepseek", "qwen", "zhipu", "moonshot"}
)
_MULTIMODAL_PROVIDERS: Final[frozenset[str]] = frozenset(
    {"anthropic", "openai", "codex", "gemini"}
)
_HIGH_END_TOKENS: Final[tuple[str, ...]] = (
    "claude-opus",
    "claude-sonnet",
    "gemini-3-pro",
    "gemini-3.1-pro",
    "gemini-2.5-pro",
    "glm-5",
    "kimi-k2.5",
)


def _heuristic_group(
    *, model_id: str, provider: str, auth_type: AuthType, max_context: int
) -> CapabilityGroup:
    text = f"{model_id} ".lower()

    if auth_type == "local" or provider == "ollama":
        return "offline_capable"

    if any(token in text for token in _HIGH_END_TOKENS):
        return "best_quality"

    if auth_type == "oauth":
        return "fast_start"

    if auth_type == "free_api_key":
        return "fast_start"

    if any(token in text for token in _CHEAP_TOKENS):
        return "cost_optimized"

    if max_context >= 500_000:
        return "best_quality"

    return "privacy_first"


def _heuristic_badges(
    *,
    model_id: str,
    provider: str,
    auth_type: AuthType,
    max_context: int,
    capability_group: CapabilityGroup,
) -> tuple[CapabilityBadge, ...]:
    text = f"{model_id} ".lower()
    badges: list[CapabilityBadge] = []

    def _add(badge: CapabilityBadge, condition: bool) -> None:
        if condition and badge not in badges:
            badges.append(badge)

    _add("offline", capability_group == "offline_capable")
    _add(
        "fast",
        auth_type == "oauth" or any(token in text for token in _FAST_TOKENS),
    )
    _add(
        "cheap",
        auth_type == "free_api_key" or any(token in text for token in _CHEAP_TOKENS),
    )
    _add("strong_coding", any(token in text for token in _CODING_TOKENS))
    _add("strong_korean", provider in _KOREAN_PROVIDERS)
    _add("long_context", max_context >= 500_000)
    _add("strong_reasoning", any(token in text for token in _REASONING_TOKENS))
    _add("multimodal", provider in _MULTIMODAL_PROVIDERS)

    if not badges:
        # Always emit at least one badge so the renderer has something to show.
        badges.append("fast" if auth_type in ("oauth", "free_api_key") else "cheap")

    return tuple(badges[:4])


def _heuristic_recommended_for(
    *, capability_group: CapabilityGroup, badges: tuple[CapabilityBadge, ...]
) -> tuple[str, ...]:
    suggestions: list[str] = []

    group_defaults: dict[CapabilityGroup, tuple[str, ...]] = {
        "fast_start": ("first_run", "quick_checks"),
        "best_quality": ("deep_analysis", "decision_ready_reports"),
        "cost_optimized": ("iteration", "budget_sensitive"),
        "privacy_first": ("byo_credentials", "controlled_access"),
        "offline_capable": ("offline", "local_only"),
    }
    suggestions.extend(group_defaults[capability_group])

    if "strong_korean" in badges:
        suggestions.append("korean")
    if "strong_coding" in badges:
        suggestions.append("coding")
    if "strong_reasoning" in badges:
        suggestions.append("reasoning")
    if "long_context" in badges:
        suggestions.append("long_context")

    seen: set[str] = set()
    deduped: list[str] = []
    for item in suggestions:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return tuple(deduped)


def derive_capability_metadata(
    *,
    model_id: str,
    provider: str,
    display_name: str,
    max_context: int,
    auth_type: AuthType,
    legacy: bool,
) -> ModelCapabilityMetadata:
    """Return capability metadata for ``model_id``.

    Curated registry entries take precedence; otherwise a deterministic
    heuristic groups + badges the model by provider, auth type, and id tokens.
    The returned object always carries a ``provider_label_legacy`` string so the
    renderer can show a 4-week migration tooltip (MIGRATION-2026-05-17) that
    bridges old provider-centric naming to the new capability-centric labels.
    The heuristic branch never returns None and always emits at least one badge.
    """
    _ = legacy  # legacy flag does not affect grouping right now; kept for future tuning
    curated = MODEL_CAPABILITY_REGISTRY.get(model_id)
    legacy_label = _build_provider_label_legacy(
        provider=provider, display_name=display_name, model_id=model_id
    )
    if curated is not None:
        return ModelCapabilityMetadata(
            capability_group=curated.capability_group,
            capability_badges=curated.capability_badges,
            recommended_for=curated.recommended_for,
            provider_label_legacy=legacy_label,
        )

    capability_group = _heuristic_group(
        model_id=model_id,
        provider=provider,
        auth_type=auth_type,
        max_context=max_context,
    )
    badges = _heuristic_badges(
        model_id=model_id,
        provider=provider,
        auth_type=auth_type,
        max_context=max_context,
        capability_group=capability_group,
    )
    recommended = _heuristic_recommended_for(
        capability_group=capability_group, badges=badges
    )
    return ModelCapabilityMetadata(
        capability_group=capability_group,
        capability_badges=badges,
        recommended_for=recommended,
        provider_label_legacy=legacy_label,
    )
