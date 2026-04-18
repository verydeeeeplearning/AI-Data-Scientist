"""Tests for PII detection and masking hooks."""

from __future__ import annotations

import pytest

from ds_agent.agent.governance_hooks import PIIRedactionHook
from ds_agent.agent.hooks import HookAction, HookContext
from ds_agent.infrastructure.pii_detector import PIIDetector


class TestPIIDetector:
    def test_detects_common_patterns(self):
        detector = PIIDetector()
        matches = detector.detect(
            {
                "email": "alice@example.com",
                "phone": "415-555-1212",
                "ssn": "123-45-6789",
            }
        )
        assert {match.pii_type for match in matches} >= {"email", "phone", "ssn"}

    def test_redacts_structure(self):
        detector = PIIDetector()
        redacted = detector.redact({"email": "alice@example.com"})
        assert "[REDACTED_EMAIL:" in redacted["email"]


class TestPIIRedactionHook:
    @pytest.mark.asyncio
    async def test_pre_hook_masks_pii_arguments(self):
        hook = PIIRedactionHook(auto_mask=True)
        context = HookContext()

        result = await hook.pre_tool_use(
            "execute_code",
            {"email": "alice@example.com"},
            context,
        )

        assert result.action == HookAction.MODIFY
        assert "[REDACTED_EMAIL:" in result.modified_arguments["email"]

    @pytest.mark.asyncio
    async def test_post_hook_redacts_generated_report_file(self, tmp_path):
        hook = PIIRedactionHook(auto_mask=True)
        report_path = tmp_path / "report.md"
        report_path.write_text(
            "Customer email alice@example.com and phone 415-555-1212",
            encoding="utf-8",
        )
        events: list[tuple[str, dict]] = []
        context = HookContext(emit=lambda event, payload: events.append((event, payload)))

        result = await hook.post_tool_use(
            "generate_report",
            {"output_path": str(report_path)},
            "Report saved",
            False,
            context,
        )

        redacted = report_path.read_text(encoding="utf-8")
        assert "[REDACTED_EMAIL:" in redacted
        assert "[REDACTED_PHONE:" in redacted
        assert result.modified_result is not None
        assert [event for event, _ in events] == ["harness.warning"]
