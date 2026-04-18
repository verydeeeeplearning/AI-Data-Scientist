"""Delivery pack entity for task contracts and stakeholder artifacts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ds_agent.domain.entities._id_patterns import DELIVERY_PACK_ID_PATTERN


class AudienceKind(StrEnum):
    """Supported audience slices for rendered artifacts."""

    EXECUTIVE = "executive"
    PM = "pm"
    DS_PEER = "ds_peer"
    ML_ENGINEER = "ml_engineer"
    AUDITOR = "auditor"
    JUNIOR_MENTEE = "junior_mentee"
    SENIOR_STAFF = "senior_staff"
    OPS = "ops"
    CUSTOMER = "customer"


class ArtifactType(StrEnum):
    """Typed stakeholder artifact families."""

    EXEC_BRIEF = "exec_brief"
    PM_ACTION_MEMO = "pm_action_memo"
    DS_EXPERIMENT_NOTE = "ds_experiment_note"
    ML_HANDOFF_SPEC = "ml_handoff_spec"
    AUDIT_TRAIL = "audit_trail"
    DS_APPENDIX = "ds_appendix"
    ACTION_PROPOSALS = "action_proposals"
    DASHBOARD = "dashboard"
    NOTEBOOK = "notebook"
    EMAIL = "email"
    SLACK_THREAD = "slack_thread"


class ArtifactFormat(StrEnum):
    """Output file formats supported by the delivery engine."""

    PPTX = "pptx"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    IPYNB = "ipynb"
    MARKDOWN = "markdown"
    HTML = "html"


class DeliveryChannel(StrEnum):
    """Dispatch channels for one rendered artifact."""

    EMAIL = "email"
    SLACK_DM = "slack_dm"
    SLACK_CHANNEL = "slack_channel"
    NOTION_PAGE = "notion_page"
    CONFLUENCE = "confluence"
    JIRA_TICKET = "jira_ticket"
    GIT_PR = "git_pr"
    COMPLIANCE_SYSTEM = "compliance_system"


class DeliveryDispatchMode(StrEnum):
    """Dispatch mode and gating policy."""

    AUTO = "auto"
    AUTO_WITH_SIGNATURE = "auto_with_signature"
    MANUAL_REVIEW = "manual_review"


class DeliveryPackStatus(StrEnum):
    """Lifecycle state for the rendered pack."""

    DRAFT = "draft"
    RENDERED = "rendered"
    DISPATCHED = "dispatched"
    REJECTED = "rejected"


class SpeculativeClaimsPolicy(StrEnum):
    """How verifier speculative-claim findings should be treated."""

    ALLOWED = "allowed"
    FLAGGED = "flagged"
    FORBIDDEN = "forbidden"


class ContentPolicy(BaseModel):
    """Audience-specific content shaping rules."""

    model_config = ConfigDict(frozen=True)

    structure: list[str] = Field(min_length=1)
    max_pages: int | None = Field(default=None, gt=0)
    chart_count_range: tuple[int, int] | None = None
    technical_detail: Literal["minimal", "balanced", "deep"] = "balanced"
    tone: Literal["decisive", "actionable", "precise", "neutral", "mentoring"] = "precise"
    include_code: bool = False
    include_verifier_results: bool = False
    include_jira_links: bool = False
    include_feature_registry_refs: bool = False
    speculative_claims: SpeculativeClaimsPolicy = SpeculativeClaimsPolicy.FLAGGED

    @model_validator(mode="after")
    def _validate_chart_count_range(self) -> ContentPolicy:
        if self.chart_count_range is None:
            return self
        lower, upper = self.chart_count_range
        if lower < 0 or upper < 0 or lower > upper:
            raise ValueError("chart_count_range must be an increasing non-negative tuple")
        return self


class DeliveryReceiver(BaseModel):
    """Resolved or deferred receiver metadata."""

    model_config = ConfigDict(frozen=True)

    role: str = Field(min_length=1)
    resolver: Literal["org_directory", "static_list", "task_contract"] = "task_contract"
    static_addresses: list[str] = Field(default_factory=list)


class ChartSpec(BaseModel):
    """Requested chart placeholder emitted by the narrative generator."""

    model_config = ConfigDict(frozen=True)

    chart_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    chart_type: Literal["bar", "line", "table", "kpi"] = "bar"
    data_points: list[tuple[str, float]] = Field(default_factory=list)


class NarrativeBlock(BaseModel):
    """Structured block returned by the audience renderer."""

    model_config = ConfigDict(frozen=True)

    section: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body_md: str = Field(min_length=1)
    chart_specs: list[ChartSpec] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class NarrativeBlocks(BaseModel):
    """Top-level structured narrative payload."""

    model_config = ConfigDict(frozen=True)

    blocks: list[NarrativeBlock] = Field(default_factory=list)
    overall_tone: str = Field(min_length=1)
    flagged_claims: list[str] = Field(default_factory=list)


class RenderedChart(BaseModel):
    """Rendered chart file metadata."""

    model_config = ConfigDict(frozen=True)

    chart_id: str = Field(min_length=1)
    image_path: str = Field(min_length=1)


class NarrativeVerification(BaseModel):
    """Verifier result attached to one rendered artifact."""

    model_config = ConfigDict(frozen=True)

    report_id: str | None = None
    flagged_claims: list[str] = Field(default_factory=list)
    rejected: bool = False
    notes: list[str] = Field(default_factory=list)


class DeliveryTemplate(BaseModel):
    """Loaded template metadata and prompt skeleton helper."""

    model_config = ConfigDict(frozen=True)

    template_ref: str = Field(min_length=1)
    family: str = Field(min_length=1)
    format: ArtifactFormat
    title: str = Field(min_length=1)
    default_structure: tuple[str, ...] = ()
    template_path: str | None = None

    def skeleton_for(self, structure: list[str]) -> str:
        sections = structure or list(self.default_structure)
        if not sections:
            return ""
        lines = ["Use exactly these sections in order:"]
        for section in sections:
            lines.extend(
                [
                    f"## {section}",
                    "- title: concise and audience-appropriate",
                    "- body_md: factual markdown prose",
                    "- citations: explicit lineage or verifier references",
                ]
            )
        return "\n".join(lines)


class DesignTheme(BaseModel):
    """Presentation theme for PPTX export."""

    model_config = ConfigDict(frozen=True)

    theme_id: str = Field(min_length=1)
    primary_color: str = Field(min_length=1)
    secondary_color: str = Field(min_length=1)
    font_heading: str = Field(min_length=1)
    font_body: str = Field(min_length=1)
    chart_palette: list[str] = Field(default_factory=list)
    logo_path: str | None = None


class DeliveryArtifact(BaseModel):
    """One stakeholder-specific artifact definition."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str = Field(min_length=1)
    type: ArtifactType
    audience: AudienceKind
    format: ArtifactFormat
    content_policy: ContentPolicy
    template_ref: str = Field(min_length=1)
    delivery_channel: list[DeliveryChannel] = Field(default_factory=list)
    dispatch_mode: DeliveryDispatchMode = DeliveryDispatchMode.MANUAL_REVIEW
    receivers: list[DeliveryReceiver] = Field(default_factory=list)
    rendered_uri: str | None = None
    verifier_report_id: str | None = None


class DeliveryItem(BaseModel):
    """Legacy flat representation retained for closure/evaluation paths."""

    deliverable_type: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    format: str = Field(min_length=1)
    artifact_path: str = Field(min_length=1)
    checksum: str | None = None
    delivered: bool = False
    delivery_channel: str | None = None
    artifact_id: str | None = None
    verifier_report_id: str | None = None


class DeliveryPack(BaseModel):
    """Collection of rendered outputs for the contract."""

    model_config = ConfigDict(validate_assignment=True, frozen=True)

    pack_id: str = Field(pattern=DELIVERY_PACK_ID_PATTERN)
    task_id: str = Field(min_length=1)
    source_analysis_id: str | None = None
    generated_at: datetime
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    signed_by: str | None = Field(default=None, min_length=1)
    signature: str | None = None
    global_context: dict[str, str] = Field(default_factory=dict)
    artifacts: list[DeliveryArtifact] = Field(default_factory=list)
    items: list[DeliveryItem] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    status: DeliveryPackStatus = DeliveryPackStatus.RENDERED
    tenant: str = "default"

    @model_validator(mode="after")
    def _synchronize_views(self) -> DeliveryPack:
        self._validate_artifacts()
        if not self.artifacts and self.items:
            object.__setattr__(
                self,
                "artifacts",
                [self._artifact_from_item(item) for item in self.items],
            )
        if self.artifacts:
            object.__setattr__(self, "items", self._merge_items(self.items, self.artifacts))
        return self

    def artifact_for(self, audience: AudienceKind | str) -> DeliveryArtifact | None:
        if isinstance(audience, str):
            try:
                audience = AudienceKind(audience)
            except ValueError:
                return None
        for artifact in self.artifacts:
            if artifact.audience == audience:
                return artifact
        return None

    def _validate_artifacts(self) -> None:
        seen_audiences: set[AudienceKind] = set()
        for artifact in self.artifacts:
            if artifact.audience in seen_audiences:
                raise ValueError(
                    f"Duplicate delivery artifact audience: {artifact.audience.value}"
                )
            seen_audiences.add(artifact.audience)
            if (
                artifact.audience == AudienceKind.AUDITOR
                and (
                    artifact.content_policy.speculative_claims
                    != SpeculativeClaimsPolicy.FORBIDDEN
                    or artifact.dispatch_mode != DeliveryDispatchMode.AUTO_WITH_SIGNATURE
                )
            ):
                raise ValueError(
                    "auditor artifacts require speculative_claims=forbidden "
                    "and dispatch_mode=auto_with_signature"
                )
            if (
                artifact.audience == AudienceKind.EXECUTIVE
                and artifact.content_policy.chart_count_range is not None
                and artifact.content_policy.chart_count_range[1] > 5
            ):
                raise ValueError("Executive artifacts cannot exceed 5 charts")

    @staticmethod
    def _merge_items(
        existing_items: list[DeliveryItem],
        artifacts: list[DeliveryArtifact],
    ) -> list[DeliveryItem]:
        merged: dict[str, DeliveryItem] = {
            item.artifact_id or f"{item.deliverable_type}:{item.audience}": item
            for item in existing_items
        }
        for artifact in artifacts:
            key = artifact.artifact_id
            if key in merged:
                continue
            merged[key] = DeliveryItem(
                artifact_id=artifact.artifact_id,
                deliverable_type=artifact.type.value,
                audience=artifact.audience.value,
                format=artifact.format.value,
                artifact_path=artifact.rendered_uri or f"artifact://{artifact.artifact_id}",
                delivered=artifact.rendered_uri is not None,
                delivery_channel=(
                    artifact.delivery_channel[0].value if artifact.delivery_channel else None
                ),
                verifier_report_id=artifact.verifier_report_id,
            )
        return list(merged.values())

    @staticmethod
    def _artifact_from_item(item: DeliveryItem) -> DeliveryArtifact:
        artifact_type = ArtifactType(item.deliverable_type)
        audience = AudienceKind(item.audience)
        artifact_format = ArtifactFormat(item.format)
        delivery_channels = (
            [DeliveryChannel(item.delivery_channel)] if item.delivery_channel else []
        )
        return DeliveryArtifact(
            artifact_id=item.artifact_id or f"{item.deliverable_type}-{item.audience}",
            type=artifact_type,
            audience=audience,
            format=artifact_format,
            content_policy=_default_content_policy(artifact_type, audience),
            template_ref=_default_template_ref(artifact_type),
            delivery_channel=delivery_channels,
            dispatch_mode=_default_dispatch_mode(audience),
            rendered_uri=item.artifact_path,
            verifier_report_id=item.verifier_report_id,
        )


def _default_content_policy(
    artifact_type: ArtifactType,
    audience: AudienceKind,
) -> ContentPolicy:
    structure_map: dict[ArtifactType, list[str]] = {
        ArtifactType.EXEC_BRIEF: [
            "situation",
            "finding",
            "impact",
            "recommendation",
            "decision_needed",
        ],
        ArtifactType.PM_ACTION_MEMO: [
            "summary",
            "next_actions",
            "eta",
            "trade_offs",
            "dependencies",
        ],
        ArtifactType.DS_EXPERIMENT_NOTE: [
            "hypothesis",
            "methodology",
            "results",
            "caveats",
            "reproducibility",
        ],
        ArtifactType.ML_HANDOFF_SPEC: [
            "model_card",
            "serving_config",
            "monitoring_setup",
            "rollback_plan",
        ],
        ArtifactType.AUDIT_TRAIL: [
            "data_provenance",
            "access_log",
            "policy_compliance",
            "approval_chain",
            "lineage",
        ],
        ArtifactType.DS_APPENDIX: ["summary", "analysis", "caveats"],
        ArtifactType.ACTION_PROPOSALS: ["summary", "actions", "owners"],
        ArtifactType.DASHBOARD: ["summary", "metrics", "filters"],
        ArtifactType.NOTEBOOK: ["summary", "analysis", "reproducibility"],
        ArtifactType.EMAIL: ["summary", "recommendation", "next_steps"],
        ArtifactType.SLACK_THREAD: ["summary", "recommendation", "next_steps"],
    }
    tone_map: dict[
        AudienceKind,
        Literal["decisive", "actionable", "precise", "neutral", "mentoring"],
    ] = {
        AudienceKind.EXECUTIVE: "decisive",
        AudienceKind.PM: "actionable",
        AudienceKind.DS_PEER: "precise",
        AudienceKind.ML_ENGINEER: "precise",
        AudienceKind.AUDITOR: "neutral",
        AudienceKind.JUNIOR_MENTEE: "mentoring",
        AudienceKind.SENIOR_STAFF: "precise",
        AudienceKind.OPS: "actionable",
        AudienceKind.CUSTOMER: "neutral",
    }
    return ContentPolicy(
        structure=structure_map[artifact_type],
        max_pages=3 if artifact_type == ArtifactType.EXEC_BRIEF else None,
        chart_count_range=(2, 3) if artifact_type == ArtifactType.EXEC_BRIEF else None,
        technical_detail=("minimal" if audience == AudienceKind.EXECUTIVE else "balanced"),
        tone=tone_map[audience],
        include_code=artifact_type in {ArtifactType.DS_EXPERIMENT_NOTE, ArtifactType.NOTEBOOK},
        include_verifier_results=artifact_type == ArtifactType.DS_EXPERIMENT_NOTE,
        include_jira_links=artifact_type == ArtifactType.PM_ACTION_MEMO,
        include_feature_registry_refs=artifact_type == ArtifactType.ML_HANDOFF_SPEC,
        speculative_claims=(
            SpeculativeClaimsPolicy.FORBIDDEN
            if audience == AudienceKind.AUDITOR
            else SpeculativeClaimsPolicy.FLAGGED
        ),
    )


def _default_template_ref(artifact_type: ArtifactType) -> str:
    mapping = {
        ArtifactType.EXEC_BRIEF: "tpl/exec_brief/v3",
        ArtifactType.PM_ACTION_MEMO: "tpl/pm_memo/v2",
        ArtifactType.DS_EXPERIMENT_NOTE: "tpl/ds_note/v4",
        ArtifactType.ML_HANDOFF_SPEC: "tpl/ml_handoff/v2",
        ArtifactType.AUDIT_TRAIL: "tpl/audit/v1",
    }
    return mapping.get(artifact_type, f"tpl/{artifact_type.value}/v1")


def _default_dispatch_mode(audience: AudienceKind) -> DeliveryDispatchMode:
    if audience == AudienceKind.AUDITOR:
        return DeliveryDispatchMode.AUTO_WITH_SIGNATURE
    return DeliveryDispatchMode.MANUAL_REVIEW
