"""Tests for claim-evidence linking and reporting hook behavior."""

from __future__ import annotations

import pytest

from ds_agent.agent.hooks import HookContext
from ds_agent.agent.reporting_hooks import ClaimTraceabilityHook
from ds_agent.application.services.claim_evidence_linker import ClaimEvidenceLinker


class TestClaimEvidenceLinker:
    def test_flags_claim_without_evidence(self):
        linker = ClaimEvidenceLinker()
        score = linker.score("Revenue increased 20% year-over-year.")
        assert score["claims"] >= 1
        assert score["unsupported"] == ["Revenue increased 20% year-over-year."]

    def test_accepts_claim_with_figure_reference(self):
        linker = ClaimEvidenceLinker()
        score = linker.score("Revenue increased 20% year-over-year (Figure 3).")
        assert score["unsupported"] == []


class TestClaimTraceabilityHook:
    @pytest.mark.asyncio
    async def test_warns_when_report_claim_has_no_evidence(self, tmp_path):
        hook = ClaimTraceabilityHook()
        report_path = tmp_path / "report.md"
        report_path.write_text("Revenue increased 20% year-over-year.", encoding="utf-8")
        events: list[tuple[str, dict]] = []
        context = HookContext(emit=lambda event, payload: events.append((event, payload)))

        result = await hook.post_tool_use(
            "generate_report",
            {"output_path": str(report_path)},
            "Report saved",
            False,
            context,
        )

        assert result.modified_result is not None
        assert "Claim traceability warning" in result.modified_result
        assert [event for event, _ in events] == ["claim.traceability", "harness.warning"]

    @pytest.mark.asyncio
    async def test_passes_when_report_claim_is_supported(self, tmp_path):
        hook = ClaimTraceabilityHook()
        report_path = tmp_path / "report.md"
        report_path.write_text(
            "Revenue increased 20% year-over-year (Figure 3).",
            encoding="utf-8",
        )
        context = HookContext()

        result = await hook.post_tool_use(
            "generate_report",
            {"output_path": str(report_path)},
            "Report saved",
            False,
            context,
        )

        assert result.modified_result is not None
        assert "passed" in result.modified_result
