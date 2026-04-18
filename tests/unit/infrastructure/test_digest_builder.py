"""Tests for ds_agent.runtime.digest_builder."""

from __future__ import annotations

import time

from ds_agent.runtime.digest_builder import build_digest
from ds_agent.runtime.runtime_event_log import RuntimeEventLog


class TestDigestBuilder:
    def test_empty_digest(self, tmp_path) -> None:
        log = RuntimeEventLog(base_dir=tmp_path)
        result = build_digest(log, since=time.time() - 60)
        assert result.event_count == 0
        assert "No recent events" in result.text

    def test_digest_with_unresolved(self, tmp_path) -> None:
        log = RuntimeEventLog(base_dir=tmp_path)
        log.record(
            category="health",
            kind="pipeline.health.degraded",
            severity="error",
            message="Pipeline X failed",
            surface="daemon",
            source="test",
        )
        result = build_digest(log, since=time.time() - 60)
        assert result.event_count == 1
        assert result.has_unresolved is True
        assert "Unresolved" in result.text
        assert "Pipeline X" in result.text

    def test_digest_with_recovery(self, tmp_path) -> None:
        log = RuntimeEventLog(base_dir=tmp_path)
        log.record(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="info",
            message="Session can resume",
            surface="daemon",
            source="test",
        )
        result = build_digest(log, since=time.time() - 60)
        assert "Recoveries" in result.text

    def test_digest_with_suppressed(self, tmp_path) -> None:
        log = RuntimeEventLog(base_dir=tmp_path)
        for _ in range(3):
            log.record(
                category="policy",
                kind="policy.suppressed",
                severity="info",
                message="Throttled",
                surface="daemon",
                source="test",
                metadata={"policyReason": "resource_pressure"},
            )
        result = build_digest(log, since=time.time() - 60)
        assert "Suppressed" in result.text
        assert "resource_pressure" in result.text

    def test_digest_fits_in_telegram_limit(self, tmp_path) -> None:
        log = RuntimeEventLog(base_dir=tmp_path)
        for i in range(30):
            log.record(
                category="health",
                kind=f"test.event.{i}",
                severity="warning",
                message=f"Event {i} " * 20,
                surface="daemon",
                source="test",
            )
        result = build_digest(log, since=time.time() - 60)
        assert len(result.text) <= 4096

    def test_category_summary(self, tmp_path) -> None:
        log = RuntimeEventLog(base_dir=tmp_path)
        log.record(
            category="health", kind="a", severity="warning",
            message="x", surface="d", source="t",
        )
        log.record(
            category="recovery", kind="b", severity="warning",
            message="y", surface="d", source="t",
        )
        result = build_digest(log, since=time.time() - 60)
        assert "By category" in result.text

    def test_digest_includes_suggested_next_actions(self, tmp_path) -> None:
        log = RuntimeEventLog(base_dir=tmp_path)
        log.record(
            category="recovery",
            kind="recovery.resume_recommended",
            severity="warning",
            message="Session can resume",
            session_id="telegram:chat1",
            run_id="run-1",
            surface="daemon",
            source="test",
        )
        result = build_digest(log, since=time.time() - 60)
        assert "Suggested next actions" in result.text
        assert "/resume" in result.text
        assert "/run run-1" in result.text
