"""Artifact generation tools for notebooks, slides, and dashboard specs."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ds_agent.application.services.artifact_generator import ArtifactGenerator
from ds_agent.application.services.audience_renderer import (
    AudienceRenderer,
    NarrativeVerificationResult,
)
from ds_agent.domain.entities.delivery_pack import (
    DeliveryArtifact,
    DeliveryPack,
    NarrativeBlocks,
)
from ds_agent.domain.value_objects.artifact import ArtifactSpec, ArtifactType
from ds_agent.infrastructure.artifact.dashboard_engine import DashboardSpecEngine
from ds_agent.infrastructure.artifact.notebook_engine import NotebookEngine
from ds_agent.infrastructure.artifact.pptx_exporter import PptxExporter
from ds_agent.infrastructure.artifact.stakeholder_exporters import (
    default_stakeholder_exporters,
)
from ds_agent.infrastructure.artifact.template_registry import StaticTemplateRegistry
from ds_agent.tools.registry import tool


class _ToolNarrativeGenerator:
    def generate(self, request: Any) -> NarrativeBlocks:
        sections = request.structure or ["summary"]
        blocks = []
        for section in sections:
            value = request.analysis.get(section)
            if value is None and section == "summary":
                value = request.analysis.get("summary", "No evidence provided.")
            if value is None:
                value = "No evidence provided."
            if isinstance(value, list):
                body = "\n".join(f"- {item}" for item in value)
            else:
                body = str(value)
            blocks.append(
                {
                    "section": section,
                    "title": section.replace("_", " ").title(),
                    "body_md": body,
                }
            )
        return NarrativeBlocks.model_validate(
            {
                "blocks": blocks,
                "overall_tone": request.tone,
                "flagged_claims": _tool_string_list(request.analysis.get("flagged_claims")),
            }
        )


class _ToolNarrativeVerifier:
    def verify(
        self,
        artifact: DeliveryArtifact,
        narrative: NarrativeBlocks,
        analysis: Mapping[str, Any],
    ) -> NarrativeVerificationResult:
        del artifact, analysis
        return NarrativeVerificationResult(
            narrative=narrative,
            status="warn" if narrative.flagged_claims else "pass",
            report_id="vr::tool",
        )


@tool(
    name="notebook_generate",
    description="Generate a Jupyter notebook (.ipynb) from markdown and code blocks.",
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "code_blocks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered code cells to include in the notebook.",
            },
            "descriptions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Markdown cells to include before the code cells.",
            },
            "outputs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional stdout output for each code cell.",
            },
            "output_path": {
                "type": "string",
                "description": "Target .ipynb path to write.",
            },
        },
        "required": ["code_blocks", "output_path"],
    },
    timeout=30,
)
def notebook_generate(
    code_blocks: list[str],
    output_path: str,
    descriptions: list[str] | None = None,
    outputs: list[str] | None = None,
) -> str:
    engine = NotebookEngine()
    notebook = engine.write(
        output_path,
        markdown_blocks=list(descriptions or []),
        code_blocks=code_blocks,
        output_blocks=outputs,
    )
    return json.dumps(
        {
            "output_path": output_path,
            "cell_count": len(cast("Sequence[object]", notebook.get("cells", []))),
            "nbformat": notebook["nbformat"],
        }
    )


@tool(
    name="slide_generate",
    description="Generate a markdown slide spec or executive memo-like slide outline.",
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "sections": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Ordered slide sections with title and bullets.",
            },
            "audience": {
                "type": "string",
                "default": "executive",
                "description": "Audience hint used in output metadata.",
            },
            "output_path": {
                "type": "string",
                "description": "Optional file path to write the markdown slide spec.",
            },
            "output_format": {
                "type": "string",
                "enum": ["markdown"],
                "default": "markdown",
            },
        },
        "required": ["sections"],
    },
    timeout=30,
)
def slide_generate(
    sections: list[dict[str, object]],
    audience: str = "executive",
    output_path: str | None = None,
    output_format: str = "markdown",
) -> str:
    generator = ArtifactGenerator()
    spec = ArtifactSpec(
        artifact_type=ArtifactType.SLIDE,
        format=output_format,
        metadata={"audience": audience},
    )
    artifact = generator.generate(spec, {"sections": sections})
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(artifact.content, encoding="utf-8")
    return json.dumps(
        {
            "output_path": output_path,
            "format": artifact.format,
            "content": artifact.content,
        }
    )


@tool(
    name="dashboard_spec",
    description="Generate a JSON or YAML BI dashboard specification.",
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "metrics": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Metric definitions with names, SQL, and chart types.",
            },
            "dimensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Dashboard dimensions or breakdowns.",
            },
            "filters": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Filter definitions.",
            },
            "layout": {
                "type": "object",
                "description": "Optional layout metadata.",
            },
            "format": {
                "type": "string",
                "enum": ["json", "yaml"],
                "default": "json",
            },
            "output_path": {
                "type": "string",
                "description": "Optional file path to write the generated spec.",
            },
        },
        "required": ["metrics"],
    },
    timeout=30,
)
def dashboard_spec(
    metrics: list[dict[str, object]],
    dimensions: list[str] | None = None,
    filters: list[dict[str, object]] | None = None,
    layout: dict[str, object] | None = None,
    format: str = "json",
    output_path: str | None = None,
) -> str:
    engine = DashboardSpecEngine()
    content = engine.build(
        metrics=metrics,
        dimensions=dimensions,
        filters=filters,
        layout=layout,
        output_format=format,
    )
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return json.dumps(
        {
            "output_path": output_path,
            "format": format,
            "content": content,
        }
    )


@tool(
    name="render_stakeholder_artifact",
    description=(
        "Render one typed stakeholder artifact to a local file using the phase-1 "
        "audience-aware delivery engine."
    ),
    category="ds_analysis",
    parameters={
        "type": "object",
        "properties": {
            "artifact": {
                "type": "object",
                "description": "DeliveryArtifact payload to render.",
            },
            "analysis": {
                "type": "object",
                "description": "Structured analysis payload keyed by section name.",
            },
            "output_dir": {
                "type": "string",
                "description": "Directory where the rendered file should be written.",
            },
            "pack_context": {
                "type": "object",
                "description": "Optional DeliveryPack-level metadata such as pack_id and confidence.",
            },
        },
        "required": ["artifact", "analysis", "output_dir"],
    },
    timeout=60,
)
def render_stakeholder_artifact(
    artifact: dict,
    analysis: dict,
    output_dir: str,
    pack_context: dict | None = None,
) -> str:
    artifact_model = DeliveryArtifact.model_validate(artifact)
    pack_metadata = dict(pack_context or {})
    pack = DeliveryPack(
        pack_id=str(pack_metadata.get("pack_id", "DP-1")),
        task_id=str(pack_metadata.get("task_id", "adhoc-task")),
        source_analysis_id=(
            str(pack_metadata["source_analysis_id"])
            if pack_metadata.get("source_analysis_id") is not None
            else None
        ),
        generated_at=datetime.now(UTC),
        confidence=float(pack_metadata.get("confidence", 1.0)),
        signed_by=str(pack_metadata.get("signed_by", "ds-agent")),
        signature=(
            str(pack_metadata["signature"]) if pack_metadata.get("signature") is not None else None
        ),
        global_context={
            str(key): str(value) for key, value in dict(pack_metadata.get("global_context", {})).items()
        },
        artifacts=[artifact_model],
    )
    exporters = cast("Sequence[Any]", [*default_stakeholder_exporters(), PptxExporter()])
    renderer = AudienceRenderer(
        generator=_ToolNarrativeGenerator(),
        verifier=_ToolNarrativeVerifier(),
        template_registry=StaticTemplateRegistry(),
        exporters=exporters,
    )
    rendered = renderer.render(
        pack=pack,
        artifact_id=artifact_model.artifact_id,
        analysis=analysis,
        output_dir=Path(output_dir),
    )
    return json.dumps(
        {
            "artifact_id": rendered.artifact_id,
            "format": rendered.format.value,
            "output_path": str(rendered.output_path),
            "verifier_status": rendered.verifier_status,
            "verifier_report_id": rendered.verifier_report_id,
            "flagged_claims": list(rendered.flagged_claims),
            "block_count": rendered.block_count,
        },
        ensure_ascii=False,
    )


def _tool_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
