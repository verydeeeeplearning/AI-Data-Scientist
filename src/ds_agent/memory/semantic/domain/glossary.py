"""Business glossary domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ds_agent.memory.semantic.domain._normalization import normalize_string_list

GlossaryCategory = Literal["metric", "entity", "event", "dimension", "other"]


class GlossaryTerm(BaseModel):
    """Canonical business term and its variants."""

    model_config = ConfigDict(frozen=True)

    term_id: str = Field(min_length=1)
    canonical_form: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    synonyms: list[str] = Field(default_factory=list)
    abbreviations: list[str] = Field(default_factory=list)
    translations: dict[str, str] = Field(default_factory=dict)
    linked_metric_ids: list[str] = Field(default_factory=list)
    category: GlossaryCategory
    owner: str | None = Field(default=None, min_length=1)

    @field_validator("synonyms", "abbreviations", "linked_metric_ids", mode="before")
    @classmethod
    def _normalize_lists(cls, value: object) -> list[str]:
        return normalize_string_list(value)

    @field_validator("translations", mode="before")
    @classmethod
    def _normalize_translations(cls, value: object) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("translations must be a mapping")

        normalized: dict[str, str] = {}
        for key, item in value.items():
            normalized_key = str(key).strip()
            normalized_value = str(item).strip()
            if not normalized_key or not normalized_value:
                continue
            normalized[normalized_key] = normalized_value
        return normalized

