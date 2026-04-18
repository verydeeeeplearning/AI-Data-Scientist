"""Readonly PDF delivery exporter for audit-facing artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from textwrap import wrap
from typing import Any

from ds_agent.domain.entities.delivery_pack import (
    ArtifactFormat,
    DeliveryArtifact,
    DeliveryPack,
    DeliveryTemplate,
    DesignTheme,
    NarrativeBlocks,
    NarrativeVerification,
    RenderedChart,
)
from ds_agent.infrastructure.exporters.theme_loader import DEFAULT_THEME, FileSystemThemeLoader

_PDF_PAGE_HEIGHT = 792
_PDF_PAGE_WIDTH = 612
_PDF_LEFT_MARGIN = 54
_PDF_TOP_MARGIN = 740
_PDF_LINE_HEIGHT = 14
_PDF_LINES_PER_PAGE = 46


class PdfExporter:
    """Render narrative blocks into a simple readonly PDF document."""

    supported_format = ArtifactFormat.PDF

    def __init__(
        self,
        theme: DesignTheme | None = None,
        *,
        theme_loader: FileSystemThemeLoader | None = None,
    ) -> None:
        self._theme = theme
        self._theme_loader = theme_loader

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
        pack: object | None = None,
    ) -> Path:
        del charts
        output_dir.mkdir(parents=True, exist_ok=True)
        resolved_pack = pack if isinstance(pack, DeliveryPack) else None
        theme = self._resolve_theme(resolved_pack)
        lines = self._build_lines(
            artifact=artifact,
            analysis=analysis,
            narrative=narrative,
            verification=verification,
            template=template,
            pack=resolved_pack,
            theme=theme,
        )
        target = output_dir / f"{artifact.artifact_id}.pdf"
        target.write_bytes(_render_pdf_pages(_paginate_lines(lines)))
        return target

    def _resolve_theme(self, pack: DeliveryPack | None) -> DesignTheme:
        if self._theme is not None:
            return self._theme
        if self._theme_loader is not None:
            return self._theme_loader.resolve(pack=pack)
        return DEFAULT_THEME

    @staticmethod
    def _build_lines(
        *,
        artifact: DeliveryArtifact,
        analysis: Mapping[str, Any],
        narrative: NarrativeBlocks,
        verification: NarrativeVerification,
        template: DeliveryTemplate,
        pack: DeliveryPack | None,
        theme: DesignTheme,
    ) -> list[str]:
        lines = [
            template.title,
            "Read-only compliance artifact.",
            "",
            f"Artifact: {artifact.type.value}",
            f"Audience: {artifact.audience.value}",
            f"Theme: {theme.theme_id}",
        ]
        if pack is not None:
            lines.extend(
                [
                    f"Task: {pack.task_id}",
                    f"Pack: {pack.pack_id}",
                    f"Generated At: {pack.generated_at.isoformat()}",
                    f"Tenant: {pack.tenant}",
                ]
            )
            if pack.source_analysis_id:
                lines.append(f"Analysis: {pack.source_analysis_id}")
            if pack.signed_by:
                lines.append(f"Signed by: {pack.signed_by}")
            if pack.signature:
                lines.append(f"Signature: {pack.signature}")
        if verification.report_id:
            lines.append(f"Verifier report: {verification.report_id}")
        summary = analysis.get("summary")
        if summary:
            lines.extend(["", "Summary", str(summary)])
        for block in narrative.blocks:
            lines.extend(["", block.title])
            lines.extend(_plain_markdown_lines(block.body_md))
            if block.citations:
                lines.append(f"Citations: {', '.join(block.citations)}")
        if verification.flagged_claims:
            lines.extend(["", "Verifier Flags"])
            lines.extend(f"- {claim}" for claim in verification.flagged_claims)
        if verification.notes:
            lines.extend(["", "Verifier Notes"])
            lines.extend(f"- {note}" for note in verification.notes)
        return lines


def _plain_markdown_lines(body_md: str) -> list[str]:
    lines: list[str] = []
    for raw_line in body_md.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        if line.startswith("### "):
            lines.append(line[4:])
            continue
        if line.startswith("## "):
            lines.append(line[3:])
            continue
        if line.startswith("# "):
            lines.append(line[2:])
            continue
        if line.startswith("- "):
            lines.append(f"* {line[2:]}")
            continue
        lines.append(line)
    return lines or ["No delivery content available."]


def _paginate_lines(lines: Sequence[str]) -> list[list[str]]:
    flattened: list[str] = []
    for line in lines:
        if not line:
            flattened.append("")
            continue
        wrapped = wrap(line, width=92, break_long_words=False, break_on_hyphens=False)
        flattened.extend(wrapped or [""])
    pages: list[list[str]] = []
    for index in range(0, len(flattened), _PDF_LINES_PER_PAGE):
        pages.append(flattened[index : index + _PDF_LINES_PER_PAGE])
    return pages or [["No delivery content available."]]


def _render_pdf_pages(pages: Sequence[Sequence[str]]) -> bytes:
    objects: list[bytes] = []
    page_ids: list[int] = []
    font_id = 3
    next_object_id = 4

    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Count 0 /Kids [] >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    )

    for page_lines in pages:
        page_id = next_object_id
        content_id = next_object_id + 1
        next_object_id += 2
        page_ids.append(page_id)
        stream = _page_stream(page_lines)
        objects.append(
            (
                f"{page_id} 0 obj\n"
                "<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {_PDF_PAGE_WIDTH} {_PDF_PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>\n"
                "endobj\n"
            ).encode("ascii")
        )
        objects.append(
            (
                f"{content_id} 0 obj\n"
                f"<< /Length {len(stream)} >>\n"
                "stream\n"
            ).encode("ascii")
            + stream
            + b"\nendstream\nendobj\n"
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = (
        f"2 0 obj\n<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>\nendobj\n"
    ).encode("ascii")

    content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets: list[int] = [0]
    for obj in objects:
        offsets.append(len(content))
        content += obj

    xref_start = len(content)
    content += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    content += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        content += f"{offset:010d} 00000 n \n".encode("ascii")
    content += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    ).encode("ascii")
    return content


def _page_stream(lines: Sequence[str]) -> bytes:
    commands = [
        "BT",
        "/F1 12 Tf",
        f"{_PDF_LINE_HEIGHT} TL",
        f"{_PDF_LEFT_MARGIN} {_PDF_TOP_MARGIN} Td",
    ]
    for index, line in enumerate(lines):
        escaped = _pdf_escape(line)
        if index == 0:
            commands.append(f"({escaped}) Tj")
            continue
        commands.append("T*")
        commands.append(f"({escaped}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def _pdf_escape(value: str) -> str:
    normalized = value.encode("latin-1", errors="replace").decode("latin-1")
    return normalized.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
