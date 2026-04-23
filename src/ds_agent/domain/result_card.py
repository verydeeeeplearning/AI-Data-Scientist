"""Validated result-card domain models."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Literal, TypeAlias

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_serializer,
    model_validator,
)

CardType = Literal["insight", "experiment", "risk", "artifact", "other"]
TrustStatus = Literal["verified", "partial", "pending", "unverified"]
RiskSeverity = Literal["low", "medium", "high"]
RiskCategory = Literal["data_leakage", "overfit", "bias", "security", "other"]
ArtifactKind = Literal["chart", "table", "notebook", "model", "report"]
QuickAction = Literal["export_report", "compare_run", "rerun", "request_review"]


class ResultCardSource(BaseModel):
    """Origin metadata for one emitted card."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")

    message_id: str = Field(alias="messageId", min_length=1)
    run_id: str = Field(alias="runId", min_length=1)
    tool_call_id: str | None = Field(default=None, alias="toolCallId")


class KeyMetric(BaseModel):
    """Summary metric for an insight card."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")

    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    delta: str | None = None


class ExperimentMetric(BaseModel):
    """Primary metric summary for an experiment card."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")

    name: str = Field(min_length=1)
    value: float
    delta_vs_baseline: float | None = Field(default=None, alias="deltaVsBaseline")


class ArtifactRef(BaseModel):
    """Reference to a downstream artifact."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")

    artifact_id: str = Field(alias="artifactId", min_length=1)
    ref: str = Field(min_length=1)
    kind: str | None = None


class BaseResultCard(BaseModel):
    """Shared fields for all result cards."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="forbid")

    card_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("cardId", "id"),
        serialization_alias="cardId",
    )
    result_id: str = Field(alias="resultId", min_length=1)
    type: CardType
    created_at: datetime = Field(alias="createdAt")
    source: ResultCardSource
    trust_strip: dict[str, Any] | None = Field(default=None, alias="trustStrip")
    pinned: bool = False
    archived: bool = False

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_ids(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        legacy_card_id = payload.get("cardId") or payload.get("id")
        if legacy_card_id is not None and "cardId" not in payload:
            payload["cardId"] = legacy_card_id
        if "id" in payload:
            payload.pop("id", None)
        if not payload.get("resultId") and legacy_card_id is not None:
            payload["resultId"] = legacy_card_id
        return payload

    @field_serializer("created_at", when_used="json")
    def _serialize_created_at(self, value: datetime) -> float:
        return value.timestamp()

    @property
    def id(self) -> str:
        """Compatibility alias for older code paths."""

        return self.card_id


class InsightCard(BaseResultCard):
    """A card that surfaces a substantive analytical insight."""

    type: Literal["insight"] = "insight"
    title: str = Field(min_length=1)
    key_metric: KeyMetric | None = Field(default=None, alias="keyMetric")
    evidence: list[str] = Field(default_factory=list)
    trust_status: TrustStatus = Field(default="unverified", alias="trustStatus")
    quick_actions: list[QuickAction] = Field(default_factory=list, alias="quickActions")


class ExperimentCard(BaseResultCard):
    """A card describing a concrete experiment run."""

    type: Literal["experiment"] = "experiment"
    run_id: str = Field(alias="runId", min_length=1)
    model_label: str = Field(alias="modelLabel", min_length=1)
    data_version: str = Field(alias="dataVersion", min_length=1)
    primary_metric: ExperimentMetric = Field(alias="primaryMetric")
    artifact_refs: list[ArtifactRef] = Field(default_factory=list, alias="artifactRefs")


class RiskCard(BaseResultCard):
    """A card that warns about an analytical or delivery risk."""

    type: Literal["risk"] = "risk"
    severity: RiskSeverity
    category: RiskCategory
    title: str = Field(min_length=1)
    target: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    impact: str = Field(min_length=1)


class ArtifactCard(BaseResultCard):
    """A card that references a concrete generated artifact."""

    type: Literal["artifact"] = "artifact"
    artifact_kind: ArtifactKind = Field(alias="artifactKind")
    title: str = Field(min_length=1)
    thumbnail_url: str | None = Field(default=None, alias="thumbnailUrl")
    file_ref: str = Field(alias="fileRef", min_length=1)
    generated_by_tool: str = Field(alias="generatedByTool", min_length=1)
    source_experiment_run_id: str | None = Field(
        default=None,
        alias="sourceExperimentRunId",
    )


class OtherCard(BaseResultCard):
    """Fallback card used when no typed payload can be validated."""

    type: Literal["other"] = "other"
    title: str = Field(default="Other", min_length=1)
    body: str = Field(min_length=1)


ResultCard: TypeAlias = (
    InsightCard | ExperimentCard | RiskCard | ArtifactCard | OtherCard
)
ResultCardAdapter: TypeAdapter[ResultCard] = TypeAdapter(
    Annotated[ResultCard, Field(discriminator="type")],
)

_CARD_MODEL_BY_TYPE: dict[CardType, type[BaseResultCard]] = {
    "insight": InsightCard,
    "experiment": ExperimentCard,
    "risk": RiskCard,
    "artifact": ArtifactCard,
    "other": OtherCard,
}


def _normalize_body(value: Mapping[str, Any] | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def build_other_card(
    *,
    card_id: str,
    result_id: str,
    created_at: datetime,
    source: ResultCardSource,
    body: Mapping[str, Any] | str,
    title: str | None = None,
    trust_strip: dict[str, Any] | None = None,
    pinned: bool = False,
    archived: bool = False,
) -> OtherCard:
    """Build a fallback card from raw payload."""

    title_value = title.strip() if isinstance(title, str) and title.strip() else "Other"
    body_value = _normalize_body(body)
    return OtherCard.model_validate(
        {
            "cardId": card_id,
            "resultId": result_id,
            "createdAt": created_at,
            "source": source,
            "trustStrip": trust_strip,
            "pinned": pinned,
            "archived": archived,
            "title": title_value,
            "body": body_value,
        }
    )


def validate_bool_flag(name: str, value: object) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{name} must be a boolean")


def clone_result_card(
    card: ResultCard,
    *,
    pinned: object | None = None,
    archived: object | None = None,
) -> ResultCard:
    payload = card.model_dump(mode="python", by_alias=True)
    if pinned is not None:
        payload["pinned"] = validate_bool_flag("pinned", pinned)
    if archived is not None:
        payload["archived"] = validate_bool_flag("archived", archived)
    validated: ResultCard = ResultCardAdapter.validate_python(payload)
    return validated


def coerce_result_card(
    card_type: str,
    payload: Mapping[str, Any] | str,
    *,
    card_id: str,
    result_id: str,
    created_at: datetime,
    source: ResultCardSource,
    trust_strip: dict[str, Any] | None = None,
    pinned: bool = False,
    archived: bool = False,
) -> ResultCard:
    """Validate one payload and fall back to ``OtherCard`` when needed."""

    normalized_type = card_type.strip().lower()
    payload_mapping: dict[str, Any] | None = None
    if isinstance(payload, Mapping):
        payload_mapping = dict(payload)
        if "type" in payload_mapping and str(payload_mapping["type"]).lower() != normalized_type:
            return build_other_card(
                card_id=card_id,
                result_id=result_id,
                created_at=created_at,
                source=source,
                body=payload,
                title=str(payload_mapping.get("title") or "Other"),
                trust_strip=trust_strip,
                pinned=pinned,
                archived=archived,
            )

    if normalized_type not in _CARD_MODEL_BY_TYPE:
        return build_other_card(
            card_id=card_id,
            result_id=result_id,
            created_at=created_at,
            source=source,
            body=payload,
            title=str(payload_mapping.get("title") or "Other") if payload_mapping else None,
            trust_strip=trust_strip,
            pinned=pinned,
            archived=archived,
        )

    model_cls = _CARD_MODEL_BY_TYPE[normalized_type]
    if model_cls is OtherCard:
        return build_other_card(
            card_id=card_id,
            result_id=result_id,
            created_at=created_at,
            source=source,
            body=payload,
            title=str(payload_mapping.get("title") or "Other") if payload_mapping else None,
            trust_strip=trust_strip,
            pinned=pinned,
            archived=archived,
        )

    if not isinstance(payload, Mapping):
        return build_other_card(
            card_id=card_id,
            result_id=result_id,
            created_at=created_at,
            source=source,
            body=payload,
            title=None,
            trust_strip=trust_strip,
            pinned=pinned,
            archived=archived,
        )

    base_payload: dict[str, Any] = {
        **(payload_mapping or {}),
        "cardId": card_id,
        "resultId": result_id,
        "type": normalized_type,
        "createdAt": created_at,
        "source": source,
        "trustStrip": trust_strip,
        "pinned": pinned,
        "archived": archived,
    }
    try:
        return model_cls.model_validate(base_payload)  # type: ignore[return-value]
    except ValidationError:
        fallback_title = (
            str(payload_mapping.get("title") or "Other")
            if payload_mapping
            else "Other"
        )
        return build_other_card(
            card_id=card_id,
            result_id=result_id,
            created_at=created_at,
            source=source,
            body=payload,
            title=fallback_title,
            trust_strip=trust_strip,
            pinned=pinned,
            archived=archived,
        )
