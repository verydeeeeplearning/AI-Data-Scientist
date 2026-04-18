"""Semantic hook tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from ds_agent.agent.hooks import HookContext
from ds_agent.agent.semantic_hooks import (
    SemanticReadGuardHook,
    SemanticTrustHook,
    SemanticWritebackHook,
)
from ds_agent.memory.semantic.application.dtos import ProposalSubmissionResultDTO
from ds_agent.memory.semantic.domain.proposal import (
    SemanticProposal,
    SemanticProposalType,
)


def _ctx(**kwargs) -> HookContext:
    events: list[tuple[str, dict]] = []
    ctx = HookContext(emit=lambda event, payload: events.append((event, payload)), **kwargs)
    ctx._events = events  # type: ignore[attr-defined]
    return ctx


class TestSemanticReadGuardHook:
    @pytest.mark.asyncio
    async def test_warns_on_metric_like_sql_without_semantic_lookup(self) -> None:
        hook = SemanticReadGuardHook()
        ctx = _ctx(session_id="session-1", user_message="Show churn by month")

        await hook.pre_tool_use("sql_query", {"sql": "SELECT 1"}, ctx)
        result = await hook.post_tool_use(
            "sql_query",
            {"sql": "SELECT 1"},
            '{"ok": true}',
            False,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        warning_events = [event for event in events if event[0] == "harness.warning"]
        assert len(warning_events) == 1
        assert warning_events[0][1]["type"] == "semantic_read_guard"
        assert result.modified_result is not None
        assert "Semantic memory warning" in result.modified_result

    @pytest.mark.asyncio
    async def test_does_not_warn_after_semantic_tool_success(self) -> None:
        hook = SemanticReadGuardHook()
        ctx = _ctx(session_id="session-2", user_message="Show churn by month")

        await hook.post_tool_use("semantic_query", {}, '{"kind":"verified"}', False, ctx)
        await hook.pre_tool_use("sql_query", {"sql": "SELECT 1"}, ctx)
        result = await hook.post_tool_use(
            "sql_query",
            {"sql": "SELECT 1"},
            '{"ok": true}',
            False,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        warning_events = [event for event in events if event[0] == "harness.warning"]
        assert warning_events == []
        assert result.modified_result is None

    @pytest.mark.asyncio
    async def test_ignores_non_metric_messages(self) -> None:
        hook = SemanticReadGuardHook()
        ctx = _ctx(session_id="session-3", user_message="List all tables in growth schema")

        await hook.pre_tool_use("sql_query", {"sql": "SELECT 1"}, ctx)
        result = await hook.post_tool_use(
            "sql_query",
            {"sql": "SELECT 1"},
            '{"ok": true}',
            False,
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        warning_events = [event for event in events if event[0] == "harness.warning"]
        assert warning_events == []
        assert result.modified_result is None

    def test_priority_and_name(self) -> None:
        hook = SemanticReadGuardHook()
        assert hook.priority == 14
        assert hook.name == "semantic_read_guard"


@dataclass
class _TrustResult:
    action: str
    warnings: list[str]
    missing_tables: list[str]
    tables: list[object]


@dataclass
class _Table:
    fqtn: str


class _FakeTrustUseCase:
    def __init__(self, result: _TrustResult) -> None:
        self._result = result
        self.calls: list[list[str]] = []

    def execute(self, tables: list[str]):
        self.calls.append(tables)
        return self._result


class _FakeContainer:
    def __init__(self, result: _TrustResult) -> None:
        self.check_table_trust = _FakeTrustUseCase(result)


class _FakeApproval:
    def __init__(
        self,
        approval_id: str,
        question: str,
        options: list[str],
        *,
        kind: str = "generic",
        metadata: dict | None = None,
    ) -> None:
        self.approval_id = approval_id
        self.question = question
        self.options = options
        self.kind = kind
        self.metadata = metadata or {}
        self.session_id = "session-trust"
        self.run_id = None
        self.surface = "agent"
        self.default = None
        self.status = type("Status", (), {"value": "pending"})()
        self.response = None
        self.source = None
        self.actor = None
        self.created_at = 0.0
        self.updated_at = 0.0
        self.resolved_at = None


class _FakeApprovalStore:
    def __init__(self) -> None:
        self.created: list[dict] = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return _FakeApproval(
            "appr-1",
            kwargs["question"],
            kwargs["options"],
            kind=str(kwargs.get("kind", "generic")),
            metadata=dict(kwargs.get("metadata", {}) or {}),
        )


class TestSemanticTrustHook:
    @pytest.mark.asyncio
    async def test_emits_caveat_warning_for_silver_tables(self, monkeypatch) -> None:
        hook = SemanticTrustHook()
        ctx = _ctx(session_id="session-trust", user_message="Show churn")
        fake = _FakeContainer(
            _TrustResult(
                action="caveat",
                warnings=["silver-grade table requires caveat"],
                missing_tables=[],
                tables=[_Table("prod.growth.subscription")],
            )
        )
        monkeypatch.setattr(
            "ds_agent.agent.semantic_hooks.get_semantic_memory_container",
            lambda: fake,
        )

        result = await hook.pre_tool_use(
            "sql_query",
            {"sql": "SELECT * FROM prod.growth.subscription"},
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        warning_events = [event for event in events if event[0] == "harness.warning"]
        assert result.action.value == "allow"
        assert warning_events
        assert warning_events[0][1]["type"] == "semantic_trust"

    @pytest.mark.asyncio
    async def test_denies_and_requests_approval_for_bronze_tables(self, monkeypatch) -> None:
        hook = SemanticTrustHook()
        approval_store = _FakeApprovalStore()
        ctx = _ctx(
            session_id="session-trust",
            user_message="Show churn",
            approval_store=approval_store,
        )
        fake = _FakeContainer(
            _TrustResult(
                action="confirm",
                warnings=["manual confirmation required for bronze/untrusted table"],
                missing_tables=[],
                tables=[_Table("prod.growth.subscription")],
            )
        )
        monkeypatch.setattr(
            "ds_agent.agent.semantic_hooks.get_semantic_memory_container",
            lambda: fake,
        )

        result = await hook.pre_tool_use(
            "sql_query",
            {"sql": "SELECT * FROM prod.growth.subscription"},
            ctx,
        )

        events = ctx._events  # type: ignore[attr-defined]
        approval_events = [event for event in events if event[0] == "approval.requested"]
        semantic_events = [event for event in events if event[0] == "semantic.trust_escalation"]
        assert result.action.value == "deny"
        assert approval_store.created
        assert approval_events
        assert semantic_events
        assert "approval_id=appr-1" in (result.deny_reason or "")

    @pytest.mark.asyncio
    async def test_ignores_non_sql_tools(self, monkeypatch) -> None:
        hook = SemanticTrustHook()
        ctx = _ctx(session_id="session-trust")

        result = await hook.pre_tool_use("data_loader", {"file_path": "x.csv"}, ctx)

        events = ctx._events  # type: ignore[attr-defined]
        assert result.action.value == "allow"
        assert events == []


class _FakeProposalSubmitUseCase:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        proposal = SemanticProposal(
            proposal_id="SP-1",
            proposal_type=SemanticProposalType(kwargs["proposal_type"]),
            summary=kwargs["summary"],
            payload=kwargs["payload"],
            target_id=kwargs.get("target_id"),
            evidence_refs=list(kwargs.get("evidence_refs", [])),
            confidence=float(kwargs["confidence"]),
            risk=kwargs["risk"],
            proposed_by=kwargs["proposed_by"],
            auto_apply_eligible=bool(kwargs["auto_apply_eligible"]),
            source_run_id=kwargs.get("source_run_id"),
            source_session_id=kwargs.get("source_session_id"),
            source_tool_name=kwargs.get("source_tool_name"),
            created_at=datetime(2026, 4, 16, tzinfo=UTC),
        )
        return ProposalSubmissionResultDTO(
            proposal=proposal,
            created=True,
            deduplicated=False,
        )


class _FakeWritebackContainer:
    def __init__(self) -> None:
        self.submit_semantic_proposal = _FakeProposalSubmitUseCase()


class TestSemanticWritebackHook:
    @pytest.mark.asyncio
    async def test_creates_verified_query_proposal_after_verifier_pass(
        self,
        monkeypatch,
    ) -> None:
        hook = SemanticWritebackHook()
        approval_store = _FakeApprovalStore()
        ctx = _ctx(session_id="session-writeback", approval_store=approval_store)
        fake = _FakeWritebackContainer()
        monkeypatch.setattr(
            "ds_agent.agent.semantic_hooks.get_semantic_memory_container",
            lambda: fake,
        )

        result = await hook.post_tool_use(
            "run_verifier",
            {
                "session_id": "session-writeback",
                "evidence_refs": [
                    {
                        "artifact_id": "dashboard://growth/churn",
                        "excerpt": "Dashboard parity confirmed",
                    }
                ],
                "artifacts": {
                    "semantic_candidates": [
                        {
                            "proposal_type": "verified_query",
                            "parity_confirmed": True,
                            "payload": {
                                "vq_id": "vq-monthly-churn-postgres",
                                "metric_id": "monthly_churn_rate",
                                "dialect": "postgres",
                                "description": "Verified monthly churn query",
                                "sql_template": (
                                    "SELECT DATE '{{as_of_date}}' AS as_of_date, "
                                    "0.05 AS monthly_churn_rate"
                                ),
                                "parameters": [
                                    {
                                        "name": "as_of_date",
                                        "type": "date",
                                        "description": "As-of date",
                                    }
                                ],
                                "referenced_tables": ["prod.growth.subscription"],
                                "verified_by": "reviewer@corp.example",
                                "last_verified": "2026-04-16",
                                "verification_evidence": "Dashboard parity with Growth board",
                            },
                        }
                    ]
                },
            },
            json.dumps(
                {
                    "ok": True,
                    "artifact_ref": "verdict:RV-1",
                    "payload": {
                        "verdict_id": "RV-1",
                        "result": "pass",
                        "run_id": "TC-1:session-writeback",
                        "confidence": {"score": 0.92, "grade": "high"},
                        "blocking_issues": [],
                    },
                },
                ensure_ascii=False,
            ),
            False,
            ctx,
        )

        payload = json.loads(result.modified_result or "{}")
        events = ctx._events  # type: ignore[attr-defined]
        created_events = [event for event in events if event[0] == "semantic.proposal.created"]
        approval_events = [event for event in events if event[0] == "approval.requested"]

        assert fake.submit_semantic_proposal.calls
        assert (
            fake.submit_semantic_proposal.calls[0]["source_run_id"]
            == "TC-1:session-writeback"
        )
        assert (
            fake.submit_semantic_proposal.calls[0]["source_session_id"]
            == "session-writeback"
        )
        assert (
            "dashboard://growth/churn"
            in fake.submit_semantic_proposal.calls[0]["evidence_refs"]
        )
        assert "verdict:RV-1" in fake.submit_semantic_proposal.calls[0]["evidence_refs"]
        assert payload["semantic_writeback"][0]["proposal_type"] == "verified_query"
        assert created_events
        assert approval_store.created
        assert approval_store.created[0]["kind"] == "semantic_proposal"
        assert approval_events

    @pytest.mark.asyncio
    async def test_skips_verified_query_without_parity_evidence(self, monkeypatch) -> None:
        hook = SemanticWritebackHook()
        ctx = _ctx(session_id="session-writeback")
        fake = _FakeWritebackContainer()
        monkeypatch.setattr(
            "ds_agent.agent.semantic_hooks.get_semantic_memory_container",
            lambda: fake,
        )

        result = await hook.post_tool_use(
            "run_verifier",
            {
                "session_id": "session-writeback",
                "artifacts": {
                    "semantic_candidates": [
                        {
                            "proposal_type": "verified_query",
                            "payload": {
                                "vq_id": "vq-monthly-churn-postgres",
                                "metric_id": "monthly_churn_rate",
                                "dialect": "postgres",
                                "description": "Verified monthly churn query",
                                "sql_template": "SELECT 0.05 AS monthly_churn_rate",
                                "referenced_tables": ["prod.growth.subscription"],
                                "verified_by": "reviewer@corp.example",
                                "last_verified": "2026-04-16",
                                "verification_evidence": "Matched report export",
                            },
                        }
                    ]
                },
            },
            json.dumps(
                {
                    "ok": True,
                    "artifact_ref": "verdict:RV-1",
                    "payload": {
                        "verdict_id": "RV-1",
                        "result": "pass",
                        "run_id": "TC-1:session-writeback",
                    },
                },
                ensure_ascii=False,
            ),
            False,
            ctx,
        )

        payload = json.loads(result.modified_result or "{}")
        events = ctx._events  # type: ignore[attr-defined]
        warning_events = [event for event in events if event[0] == "harness.warning"]

        assert fake.submit_semantic_proposal.calls == []
        assert payload["semantic_writeback_warnings"]
        assert "parity evidence" in payload["semantic_writeback_warnings"][0]
        assert warning_events
