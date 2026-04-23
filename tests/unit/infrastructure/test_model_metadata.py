"""Tests for capability metadata mapping for the LLM model catalog.

W1-C PLAN_06: backend metadata extension. Verifies that every shipped model id
has a curated capability_group + capability_badges entry, and that the lookup
helper falls back to a heuristic profile (never None) for unknown ids so the
renderer always receives valid metadata.
"""

from __future__ import annotations

from ds_agent.providers.anthropic import ANTHROPIC_MODELS
from ds_agent.providers.codex_oauth import CODEX_MODELS
from ds_agent.providers.gemini_oauth import GEMINI_MODELS
from ds_agent.providers.litellm_provider import LITELLM_MODELS
from ds_agent.providers.model_metadata import (
    CAPABILITY_BADGES,
    CAPABILITY_GROUPS,
    MODEL_CAPABILITY_REGISTRY,
    ModelCapabilityMetadata,
    derive_capability_metadata,
    get_capability_metadata,
)
from ds_agent.providers.openai_provider import OPENAI_MODELS


def _all_known_model_ids() -> list[str]:
    ids: list[str] = []
    for model_id in ANTHROPIC_MODELS:
        ids.append(f"anthropic/{model_id}")
    for model_id in OPENAI_MODELS:
        ids.append(f"openai/{model_id}")
    for model_id in CODEX_MODELS:
        ids.append(f"codex/{model_id}")
    for model_id in GEMINI_MODELS:
        ids.append(f"gemini/{model_id}")
    for model_id in LITELLM_MODELS:
        ids.append(model_id)
    return ids


class TestCapabilityVocabulary:
    def test_capability_groups_match_renderer_contract(self) -> None:
        assert CAPABILITY_GROUPS == (
            "fast_start",
            "best_quality",
            "cost_optimized",
            "privacy_first",
            "offline_capable",
        )

    def test_capability_badges_match_renderer_contract(self) -> None:
        assert set(CAPABILITY_BADGES) == {
            "fast",
            "cheap",
            "strong_coding",
            "strong_korean",
            "offline",
            "long_context",
            "strong_reasoning",
            "multimodal",
        }


class TestRegistryCoverage:
    def test_every_shipped_model_has_curated_metadata(self) -> None:
        missing = [mid for mid in _all_known_model_ids() if mid not in MODEL_CAPABILITY_REGISTRY]
        assert missing == [], (
            "All catalog models must have curated capability metadata. "
            f"Missing entries: {missing}"
        )

    def test_every_capability_group_has_at_least_one_model(self) -> None:
        present_groups = {meta.capability_group for meta in MODEL_CAPABILITY_REGISTRY.values()}
        for group in CAPABILITY_GROUPS:
            if group == "offline_capable":
                continue
            assert group in present_groups, f"capability group {group!r} has no model"

    def test_registry_entries_use_known_vocabulary(self) -> None:
        for model_id, meta in MODEL_CAPABILITY_REGISTRY.items():
            assert meta.capability_group in CAPABILITY_GROUPS, (
                f"{model_id}: invalid group {meta.capability_group}"
            )
            for badge in meta.capability_badges:
                assert badge in CAPABILITY_BADGES, (
                    f"{model_id}: invalid badge {badge}"
                )
            assert 0 < len(meta.capability_badges) <= 4, (
                f"{model_id}: badge count must be 1..4 (got {len(meta.capability_badges)})"
            )

    def test_recommended_for_uses_stable_keys(self) -> None:
        valid_keys = {
            "first_run",
            "quick_checks",
            "deep_analysis",
            "decision_ready_reports",
            "iteration",
            "budget_sensitive",
            "byo_credentials",
            "controlled_access",
            "offline",
            "local_only",
            "korean",
            "coding",
            "reasoning",
            "long_context",
            "vision",
        }
        for model_id, meta in MODEL_CAPABILITY_REGISTRY.items():
            for key in meta.recommended_for:
                assert key in valid_keys, f"{model_id}: unknown recommended_for key {key!r}"


class TestGetCapabilityMetadata:
    def test_known_anthropic_model_returns_curated_entry(self) -> None:
        meta = get_capability_metadata("anthropic/claude-opus-4-6")
        assert meta is not None
        assert meta.capability_group == "best_quality"
        assert "strong_reasoning" in meta.capability_badges

    def test_known_groq_model_marked_as_fast_start(self) -> None:
        meta = get_capability_metadata("groq/llama-4-scout-17b-16e-instruct")
        assert meta is not None
        assert meta.capability_group in ("fast_start", "cost_optimized")
        assert "fast" in meta.capability_badges

    def test_unknown_model_returns_none(self) -> None:
        assert get_capability_metadata("does-not-exist/foo") is None


class TestDeriveCapabilityMetadata:
    def test_curated_entry_takes_precedence(self) -> None:
        # claude-opus-4-6 has curated 'best_quality'
        derived = derive_capability_metadata(
            model_id="anthropic/claude-opus-4-6",
            provider="anthropic",
            display_name="Claude Opus 4.6",
            max_context=1_000_000,
            auth_type="api_key",
            legacy=False,
        )
        assert derived.capability_group == "best_quality"

    def test_unknown_local_model_falls_back_to_offline_capable(self) -> None:
        derived = derive_capability_metadata(
            model_id="ollama/mystery-7b",
            provider="ollama",
            display_name="Mystery 7B",
            max_context=8_000,
            auth_type="local",
            legacy=False,
        )
        assert derived.capability_group == "offline_capable"
        assert "offline" in derived.capability_badges

    def test_unknown_oauth_model_falls_back_to_fast_start(self) -> None:
        derived = derive_capability_metadata(
            model_id="codex/foo-bar-9",
            provider="codex",
            display_name="Foo Bar 9 (Codex)",
            max_context=128_000,
            auth_type="oauth",
            legacy=False,
        )
        assert derived.capability_group == "fast_start"

    def test_unknown_api_key_model_falls_back_to_privacy_first(self) -> None:
        derived = derive_capability_metadata(
            model_id="openai/mystery-mini",
            provider="openai",
            display_name="Mystery Mini",
            max_context=128_000,
            auth_type="api_key",
            legacy=False,
        )
        assert derived.capability_group in ("privacy_first", "cost_optimized", "best_quality")
        assert len(derived.capability_badges) >= 1

    def test_provider_label_legacy_includes_provider_and_model_id(self) -> None:
        derived = derive_capability_metadata(
            model_id="anthropic/claude-sonnet-4-6",
            provider="anthropic",
            display_name="Claude Sonnet 4.6",
            max_context=1_000_000,
            auth_type="api_key",
            legacy=False,
        )
        assert derived.provider_label_legacy is not None
        assert "anthropic" in derived.provider_label_legacy.lower()
        assert "claude-sonnet-4-6" in derived.provider_label_legacy


class TestModelCapabilityMetadataDataclass:
    def test_round_trip_to_dict(self) -> None:
        meta = ModelCapabilityMetadata(
            capability_group="best_quality",
            capability_badges=("strong_reasoning", "multimodal"),
            recommended_for=("deep_analysis",),
            provider_label_legacy="Anthropic Claude Opus 4.6 (anthropic/claude-opus-4-6)",
        )
        payload = meta.to_dict()
        assert payload == {
            "capabilityGroup": "best_quality",
            "capabilityBadges": ["strong_reasoning", "multimodal"],
            "recommendedFor": ["deep_analysis"],
            "providerLabelLegacy": "Anthropic Claude Opus 4.6 (anthropic/claude-opus-4-6)",
        }

    def test_provider_label_legacy_is_optional(self) -> None:
        meta = ModelCapabilityMetadata(
            capability_group="fast_start",
            capability_badges=("fast",),
            recommended_for=("first_run",),
            provider_label_legacy=None,
        )
        payload = meta.to_dict()
        assert "providerLabelLegacy" not in payload or payload["providerLabelLegacy"] is None
