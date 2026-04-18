"""Ports for stakeholder communication rendering and export."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ds_agent.domain.entities.delivery_pack import (
    DeliveryArtifact,
    DeliveryTemplate,
    NarrativeBlocks,
    NarrativeVerification,
    RenderedChart,
)


@runtime_checkable
class NarrativeGenerationPort(Protocol):
    """LLM-backed narrative generation boundary."""

    async def generate(self, *, system_prompt: str, user_prompt: str) -> Any: ...


@runtime_checkable
class ArtifactNarrativeVerifierPort(Protocol):
    """Artifact-level verification boundary."""

    async def verify(
        self,
        *,
        artifact: DeliveryArtifact,
        analysis: Mapping[str, Any],
        narrative: NarrativeBlocks,
    ) -> NarrativeVerification: ...


@runtime_checkable
class ChartRendererPort(Protocol):
    """Chart rendering boundary for presentation exporters."""

    async def render(
        self,
        *,
        artifact: DeliveryArtifact,
        narrative: NarrativeBlocks,
        output_dir: Path,
    ) -> list[RenderedChart]: ...


@runtime_checkable
class TemplateRegistryPort(Protocol):
    """Template metadata lookup boundary."""

    def load(self, template_ref: str) -> DeliveryTemplate: ...


@runtime_checkable
class ArtifactExporterPort(Protocol):
    """Format-specific artifact serializer."""

    def export(
        self,
        *,
        artifact: DeliveryArtifact,
        analysis: Mapping[str, Any],
        narrative: NarrativeBlocks,
        charts: Sequence[RenderedChart],
        verification: NarrativeVerification,
        output_dir: Path,
        template: DeliveryTemplate,
    ) -> Path: ...
