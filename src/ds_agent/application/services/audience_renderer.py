"""Audience-aware rendering pipeline for stakeholder communication artifacts."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from inspect import Parameter, isawaitable, signature
from pathlib import Path
from typing import Any, Protocol, cast

from pydantic import BaseModel, Field, ValidationError

from ds_agent.application.dtos.delivery import (
    NarrativeVerificationResult as DeliveryNarrativeVerificationResult,
)
from ds_agent.application.dtos.delivery import (
    RenderedArtifact,
)
from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    AudienceKind,
    DeliveryArtifact,
    DeliveryPack,
    DeliveryTemplate,
    NarrativeBlocks,
    NarrativeVerification,
)
from ds_agent.domain.interfaces.delivery import NarrativeGenerationPort
from ds_agent.domain.value_objects.audience_persona import AudiencePersona

_PERSONA_PROMPTS: dict[AudienceKind, str] = {
    AudienceKind.EXECUTIVE: (
        "You are briefing a C-level decision maker.\n"
        "- Be business-first and brief.\n"
        "- Tie every number to business impact.\n"
        "- Avoid p-values, AUC, and model internals.\n"
        "- End with one concrete decision request."
    ),
    AudienceKind.PM: (
        "You are writing for a product manager.\n"
        "- Convert analysis into sprint-ready actions.\n"
        "- Prefer owners, ETA, dependencies, and trade-offs.\n"
        "- Avoid vague observations without next steps."
    ),
    AudienceKind.DS_PEER: (
        "You are writing for a senior data scientist peer.\n"
        "- Keep hypothesis, method, results, and caveats explicit.\n"
        "- Preserve reproducibility details.\n"
        "- Do not hide negative findings."
    ),
    AudienceKind.ML_ENGINEER: (
        "You are handing a model off to an ML engineer.\n"
        "- Focus on serving constraints, monitoring, and rollback.\n"
        "- Prefer concrete configuration over summary prose."
    ),
    AudienceKind.AUDITOR: (
        "You are writing for a regulatory auditor.\n"
        "- State only evidence-backed claims.\n"
        "- Zero speculation.\n"
        "- Cite lineage or verifier evidence for every important assertion."
    ),
    AudienceKind.JUNIOR_MENTEE: (
        "You are mentoring a junior practitioner.\n"
        "- Explain reasoning explicitly.\n"
        "- Preserve caveats and uncertainty in simple language."
    ),
}


class TemplateSpec(BaseModel):
    """Resolved template metadata used by exporters."""

    template_ref: str
    format: ArtifactFormat
    structure: list[str] = Field(default_factory=list)
    path: str | None = None
    title: str | None = None

    def skeleton_for(self) -> str:
        if not self.structure:
            return ""
        lines = ["Use exactly these sections in order:"]
        for section in self.structure:
            lines.extend(
                [
                    f"## {section}",
                    "- title: concise and audience-appropriate",
                    "- body_md: factual markdown prose",
                    "- citations: explicit lineage or verifier references",
                ]
            )
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class NarrativeGenerationRequest:
    """Structured request passed to the generator backend."""

    delivery_artifact: DeliveryArtifact
    artifact_id: str
    artifact_type: str
    audience: str
    format: str
    template_ref: str
    structure: list[str]
    technical_detail: str
    tone: str
    analysis: Mapping[str, Any]
    system_prompt: str

    @property
    def artifact(self) -> DeliveryArtifact:
        return self.delivery_artifact


class NarrativeVerificationResult(BaseModel):
    """Verifier result passed back into the renderer pipeline."""

    narrative: NarrativeBlocks
    status: str = "pass"
    report_id: str | None = None
    flagged_claims: list[str] = Field(default_factory=list)
    rejected: bool = False
    notes: list[str] = Field(default_factory=list)


class NarrativeGenerator(Protocol):
    """Backend that produces structured narrative blocks."""

    def generate(self, request: NarrativeGenerationRequest) -> NarrativeBlocks | dict[str, Any]:
        ...


class NarrativeVerifier(Protocol):
    """Policy gate that can block or annotate narratives."""

    def verify(
        self,
        artifact: DeliveryArtifact,
        narrative: NarrativeBlocks,
        analysis: Mapping[str, Any],
    ) -> NarrativeVerificationResult | NarrativeVerification:
        ...


class ArtifactExporter(Protocol):
    """Format-specific artifact exporter."""

    supported_format: ArtifactFormat

    def export(self, **kwargs: object) -> Path: ...


class TemplateRegistry(Protocol):
    """Resolves template refs into local metadata."""

    def load(
        self,
        template_ref: str,
        *,
        format: ArtifactFormat,
        fallback_structure: Sequence[str],
    ) -> TemplateSpec | DeliveryTemplate:
        ...


class DeterministicNarrativeGenerator:
    """Fallback generator used until provider-backed narrative rendering is wired."""

    def generate(self, request: NarrativeGenerationRequest) -> NarrativeBlocks:
        blocks = []
        for section in request.structure:
            blocks.append(
                {
                    "section": section,
                    "title": section.replace("_", " ").title(),
                    "body_md": _render_section_body(section, request.analysis),
                    "citations": _collect_citations(section, request.analysis),
                }
            )
        return NarrativeBlocks.model_validate(
            {
                "blocks": blocks,
                "overall_tone": request.tone,
                "flagged_claims": _string_list(
                    request.analysis.get("flagged_claims")
                    or request.analysis.get("speculative_claims")
                ),
            }
        )


class PolicyAwareNarrativeVerifier:
    """Minimal verifier that enforces speculative-claim policy."""

    def verify(
        self,
        artifact: DeliveryArtifact,
        narrative: NarrativeBlocks,
        analysis: Mapping[str, Any],
    ) -> NarrativeVerificationResult:
        del analysis
        if (
            artifact.content_policy.speculative_claims.value == "forbidden"
            and narrative.flagged_claims
        ):
            raise ValueError(
                "Artifact cannot be rendered because speculative claims are forbidden"
            )
        return NarrativeVerificationResult(
            narrative=narrative,
            status="warn" if narrative.flagged_claims else "pass",
            report_id=f"vr::{artifact.artifact_id}",
            flagged_claims=list(narrative.flagged_claims),
        )


class NoopChartRenderer:
    """Default chart renderer used until chart generation is wired."""

    def render(self, **kwargs: Any) -> list[Any]:
        del kwargs
        return []


class AudienceRenderer:
    """Render one delivery artifact for a specific audience."""

    def __init__(
        self,
        *,
        llm_gateway: NarrativeGenerationPort | None = None,
        generator: NarrativeGenerator | None = None,
        verifier: NarrativeVerifier | None = None,
        chart_renderer: Any | None = None,
        template_registry: TemplateRegistry,
        exporters: Mapping[ArtifactFormat, ArtifactExporter]
        | Sequence[ArtifactExporter],
    ) -> None:
        self._llm_gateway = llm_gateway
        self._generator = generator or DeterministicNarrativeGenerator()
        self._verifier = verifier or PolicyAwareNarrativeVerifier()
        self._chart_renderer = chart_renderer or NoopChartRenderer()
        self._template_registry = template_registry
        self._exporters = self._normalize_exporters(exporters)

    def render(
        self,
        *,
        analysis: Mapping[str, Any] | str,
        output_dir: Path,
        artifact: DeliveryArtifact | None = None,
        pack: DeliveryPack | None = None,
        artifact_id: str | None = None,
        audience_profile: AudiencePersona | None = None,
    ) -> RenderedArtifact:
        analysis_payload = self._normalize_analysis(analysis)
        resolved_artifact, resolved_pack = self._resolve_artifact(
            artifact=artifact,
            pack=pack,
            artifact_id=artifact_id,
        )
        template = self._coerce_template(
            self._template_registry.load(
                resolved_artifact.template_ref,
                format=resolved_artifact.format,
                fallback_structure=resolved_artifact.content_policy.structure,
            ),
            artifact=resolved_artifact,
        )
        request = NarrativeGenerationRequest(
            delivery_artifact=resolved_artifact,
            artifact_id=resolved_artifact.artifact_id,
            artifact_type=resolved_artifact.type.value,
            audience=resolved_artifact.audience.value,
            format=resolved_artifact.format.value,
            template_ref=resolved_artifact.template_ref,
            structure=list(template.structure),
            technical_detail=resolved_artifact.content_policy.technical_detail,
            tone=resolved_artifact.content_policy.tone,
            analysis=analysis_payload,
            system_prompt=self._build_system_prompt(
                artifact=resolved_artifact,
                audience_profile=audience_profile,
            ),
        )
        narrative = self._build_narrative(request, template)
        verification = self._verify(
            artifact=resolved_artifact,
            analysis=analysis_payload,
            narrative=narrative,
        )
        charts = self._render_charts(
            artifact=resolved_artifact,
            narrative=narrative,
            output_dir=output_dir,
        )
        exporter = self._exporters.get(resolved_artifact.format)
        if exporter is None:
            raise ValueError(f"No exporter registered for format: {resolved_artifact.format.value}")
        output_path = self._export(
            exporter=exporter,
            pack=resolved_pack,
            artifact=resolved_artifact,
            analysis=analysis_payload,
            narrative=narrative,
            charts=charts,
            verification=verification,
            template=template,
            output_dir=output_dir,
        )
        return RenderedArtifact(
            artifact_id=resolved_artifact.artifact_id,
            format=resolved_artifact.format,
            output_path=output_path,
            narrative=narrative,
            verifier_status=verification.status,
            verifier_report_id=verification.report_id,
            flagged_claims=tuple(verification.flagged_claims),
        )

    @staticmethod
    def _normalize_exporters(
        exporters: Mapping[ArtifactFormat, ArtifactExporter] | Sequence[ArtifactExporter],
    ) -> dict[ArtifactFormat, ArtifactExporter]:
        if isinstance(exporters, Mapping):
            return dict(exporters)
        return {exporter.supported_format: exporter for exporter in exporters}

    @staticmethod
    def _normalize_analysis(analysis: Mapping[str, Any] | str) -> Mapping[str, Any]:
        if isinstance(analysis, Mapping):
            return dict(analysis)
        return {"summary": str(analysis)}

    @staticmethod
    def _resolve_artifact(
        *,
        artifact: DeliveryArtifact | None,
        pack: DeliveryPack | None,
        artifact_id: str | None,
    ) -> tuple[DeliveryArtifact, DeliveryPack]:
        if artifact is not None:
            generated_pack = pack or DeliveryPack(
                pack_id="DP-0",
                task_id="adhoc",
                generated_at=datetime.now(tz=UTC),
                artifacts=[artifact],
            )
            return artifact, generated_pack
        if pack is None or artifact_id is None:
            raise ValueError("Provide either artifact or pack + artifact_id")
        resolved_artifact = next(
            (candidate for candidate in pack.artifacts if candidate.artifact_id == artifact_id),
            None,
        )
        if resolved_artifact is None:
            raise ValueError(f"Unknown artifact_id: {artifact_id}")
        return resolved_artifact, pack

    def _build_narrative(
        self,
        request: NarrativeGenerationRequest,
        template: TemplateSpec,
    ) -> NarrativeBlocks:
        if self._llm_gateway is not None:
            gateway_result = self._llm_gateway.generate(
                system_prompt=request.system_prompt,
                user_prompt=self._build_user_prompt(request.analysis, request, template),
            )
            raw: Any = _resolve_maybe_awaitable(gateway_result)
            return self._coerce_narrative_blocks(raw)
        raw = self._generator.generate(request)
        raw = _resolve_maybe_awaitable(raw)
        return self._coerce_narrative_blocks(raw)

    def _verify(
        self,
        *,
        artifact: DeliveryArtifact,
        analysis: Mapping[str, Any],
        narrative: NarrativeBlocks,
    ) -> NarrativeVerificationResult:
        result = self._verifier.verify(artifact, narrative, analysis)
        result = _resolve_maybe_awaitable(result)
        if isinstance(result, NarrativeVerificationResult):
            return result
        if isinstance(result, DeliveryNarrativeVerificationResult):
            return NarrativeVerificationResult(
                narrative=result.narrative,
                status=result.status,
                report_id=result.report_id,
                flagged_claims=list(result.flagged_claims),
                rejected=result.rejected,
                notes=list(result.notes),
            )
        if isinstance(result, NarrativeVerification):
            return NarrativeVerificationResult(
                narrative=narrative,
                status="rejected" if result.rejected else "pass",
                report_id=result.report_id,
                flagged_claims=list(result.flagged_claims),
                rejected=result.rejected,
                notes=list(result.notes),
            )
        if hasattr(result, "narrative") and hasattr(result, "report_id"):
            status = getattr(result, "status", "pass")
            flagged_claims = list(getattr(result, "flagged_claims", []))
            if not flagged_claims and hasattr(result, "narrative"):
                flagged_claims = list(getattr(result.narrative, "flagged_claims", []))
            narrative = result.narrative
            return NarrativeVerificationResult(
                narrative=narrative,
                status=status,
                report_id=getattr(result, "report_id", None),
                flagged_claims=flagged_claims,
                rejected=bool(getattr(result, "rejected", status == "rejected")),
                notes=list(getattr(result, "notes", [])),
            )
        raise ValueError("Verifier returned an unsupported result type")

    def _render_charts(
        self,
        *,
        artifact: DeliveryArtifact,
        narrative: NarrativeBlocks,
        output_dir: Path,
    ) -> list[Any]:
        render = getattr(self._chart_renderer, "render", None)
        if render is None:
            return []
        result = render(
            artifact=artifact,
            narrative=narrative,
            output_dir=output_dir,
        )
        result = _resolve_maybe_awaitable(result)
        return list(result)

    @staticmethod
    def _export(
        *,
        exporter: ArtifactExporter,
        pack: DeliveryPack,
        artifact: DeliveryArtifact,
        analysis: Mapping[str, Any],
        narrative: NarrativeBlocks,
        charts: list[Any],
        verification: NarrativeVerificationResult,
        template: TemplateSpec,
        output_dir: Path,
    ) -> Path:
        payload = {
            "pack": pack,
            "artifact": artifact,
            "analysis": analysis,
            "narrative": narrative,
            "charts": charts,
            "verification": NarrativeVerification(
                report_id=verification.report_id,
                flagged_claims=list(verification.flagged_claims),
                rejected=verification.rejected,
                notes=list(verification.notes),
            ),
            "template": template,
            "output_dir": output_dir,
        }
        export_signature = signature(exporter.export)
        if any(
            parameter.kind == Parameter.VAR_KEYWORD
            for parameter in export_signature.parameters.values()
        ):
            return exporter.export(**payload)
        accepted = {
            name
            for name, parameter in export_signature.parameters.items()
            if name != "self"
            and parameter.kind in {Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY}
        }
        return exporter.export(**{key: value for key, value in payload.items() if key in accepted})

    @staticmethod
    def _build_system_prompt(
        *,
        artifact: DeliveryArtifact,
        audience_profile: AudiencePersona | None,
    ) -> str:
        persona_prompt = _PERSONA_PROMPTS.get(
            artifact.audience,
            "Tailor the narrative to the requested audience and keep it evidence-based.",
        )
        policy = artifact.content_policy
        constraints = [
            f"Structure: {', '.join(policy.structure)}",
            f"Technical detail: {policy.technical_detail}",
            f"Tone: {policy.tone}",
            f"Speculative claims policy: {policy.speculative_claims.value}",
        ]
        if audience_profile is not None:
            spec = audience_profile.spec()
            constraints.extend(
                [
                    f"Prompt audience tone modifier: {spec.tone}",
                    f"Prompt audience depth modifier: {spec.depth}",
                    f"Prompt uncertainty style: {spec.uncertainty_style}",
                ]
            )
        return persona_prompt + "\n" + "\n".join(f"- {item}" for item in constraints)

    @staticmethod
    def _build_user_prompt(
        analysis: Mapping[str, Any],
        request: NarrativeGenerationRequest,
        template: TemplateSpec,
    ) -> str:
        serialized = json.dumps(analysis, ensure_ascii=False, indent=2, default=str)
        return "\n\n".join(
            [
                f"Render artifact `{request.artifact_id}` in `{request.format}` format.",
                "Analysis payload:",
                serialized,
                "Template skeleton:",
                template.skeleton_for(),
                "Return a NarrativeBlocks-compatible JSON object only.",
            ]
        )

    @staticmethod
    def _coerce_narrative_blocks(raw: Any) -> NarrativeBlocks:
        try:
            if isinstance(raw, NarrativeBlocks):
                narrative = raw
            elif isinstance(raw, Mapping):
                narrative = NarrativeBlocks.model_validate(raw)
            elif isinstance(raw, str):
                narrative = NarrativeBlocks.model_validate_json(raw)
            else:
                raise ValueError("LLM response did not match NarrativeBlocks schema")
        except ValidationError as exc:
            raise ValueError("LLM response did not match NarrativeBlocks schema") from exc
        if not narrative.blocks:
            raise ValueError("LLM response did not match NarrativeBlocks schema")
        return narrative

    @staticmethod
    def _coerce_template(
        raw: TemplateSpec | DeliveryTemplate,
        *,
        artifact: DeliveryArtifact,
    ) -> TemplateSpec:
        if isinstance(raw, TemplateSpec):
            return raw
        return TemplateSpec(
            template_ref=raw.template_ref,
            format=raw.format,
            structure=list(raw.default_structure or artifact.content_policy.structure),
            path=raw.template_path,
            title=raw.title,
        )


def _resolve_maybe_awaitable(value: Any) -> Any:
    if not isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(cast(Any, value))
    raise RuntimeError("AudienceRenderer.sync render cannot await inside an active event loop")


def _render_section_body(section: str, analysis: Mapping[str, Any]) -> str:
    direct = analysis.get(section)
    if direct is not None:
        return _render_value(direct)

    aliases = {
        "finding": "key_findings",
        "recommendation": "recommendations",
        "next_actions": "actions",
        "decision_needed": "decision",
    }
    alias_value = analysis.get(aliases.get(section, ""))
    if alias_value is not None:
        return _render_value(alias_value)
    if section == "summary" and "summary" in analysis:
        return _render_value(analysis["summary"])
    return "No evidence provided."


def _collect_citations(section: str, analysis: Mapping[str, Any]) -> list[str]:
    citations = analysis.get("citations")
    if isinstance(citations, Mapping):
        return _string_list(citations.get(section))
    return []


def _render_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip() or "No evidence provided."
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        bullets = [item for item in (_render_scalar(element) for element in value) if item]
        return "\n".join(f"- {item}" for item in bullets) or "No evidence provided."
    if isinstance(value, Mapping):
        rows = [f"- {key}: {_render_scalar(item)}" for key, item in value.items()]
        return "\n".join(rows) or "No evidence provided."
    return _render_scalar(value) or "No evidence provided."


def _render_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(item) for item in value]
    return [str(value)]
