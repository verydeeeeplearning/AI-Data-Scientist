"""Artifact/reporting hooks."""

from __future__ import annotations

from pathlib import Path

from ds_agent.agent.hooks import HookContext, PostToolUseResult, ToolHook
from ds_agent.application.services.claim_evidence_linker import ClaimEvidenceLinker


class ClaimTraceabilityHook(ToolHook):
    """Warn when report claims are not linked to evidence."""

    name = "claim_traceability"
    priority = 52

    def __init__(self, linker: ClaimEvidenceLinker | None = None) -> None:
        self._linker = linker or ClaimEvidenceLinker()

    async def post_tool_use(
        self, tool_name: str, arguments: dict, result: str, is_error: bool, context: HookContext
    ) -> PostToolUseResult:
        if tool_name != "generate_report" or is_error:
            return PostToolUseResult()

        report_text = result
        if isinstance(arguments.get("output_path"), str):
            path = Path(arguments["output_path"])
            if path.exists() and path.is_file():
                report_text = path.read_text(encoding="utf-8")

        score = self._linker.score(report_text)
        context.emit("claim.traceability", score)
        raw_unsupported = score.get("unsupported", [])
        unsupported: list[str] = (
            list(raw_unsupported) if isinstance(raw_unsupported, list) else []
        )
        if not unsupported:
            return PostToolUseResult(
                modified_result=str(result) + "\n\n---\n**Claim traceability**: passed"
            )

        warning_lines = "\n".join(f"- {claim}" for claim in unsupported[:5])
        context.emit(
            "harness.warning",
            {
                "type": "claim_traceability",
                "severity": "medium",
                "message": "Claims without evidence were detected",
                "details": unsupported[:5],
            },
        )
        return PostToolUseResult(
            modified_result=(
                str(result) + "\n\n---\n**Claim traceability warning**:\n" + warning_lines
            )
        )
