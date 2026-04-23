from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ds_agent.agent.auto_verifier_hook import AutoVerifierHook
from ds_agent.agent.hooks import HookContext
from ds_agent.domain.entities.messages import ChatMessage, Role, ToolCall
from ds_agent.domain.entities.review_verdict import (
    ActionHint,
    ConfidenceBand,
    Issue,
    ReviewVerdict,
)
from ds_agent.domain.entities.task_contract import (
    DefinitionOfDone,
    DeliverableSpec,
    TaskContract,
    TaskContractStatus,
)


def _task_contract(
    status: TaskContractStatus = TaskContractStatus.IN_PROGRESS,
    min_confidence_grade: str | None = None,
) -> TaskContract:
    definition_of_done = None
    if min_confidence_grade is not None:
        definition_of_done = DefinitionOfDone(
            criteria=["Verifier confidence must satisfy the contract gate."],
            verifier=DefinitionOfDone.VerifierRequirements(
                min_confidence_grade=min_confidence_grade,
            ),
        )
    return TaskContract(
        task_id="TC-2026-001",
        session_id="session-1",
        type="analysis",
        status=status,
        business_goal="Improve churn forecasting quality.",
        definition_of_done=definition_of_done,
        required_deliverables=[
            DeliverableSpec(type="exec_brief", audience="executive", format="md")
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _review_verdict(
    task_id: str = "TC-2026-001",
    *,
    metadata: dict[str, object] | None = None,
) -> ReviewVerdict:
    return ReviewVerdict(
        verdict_id="RV-1",
        task_id=task_id,
        reviewer="verifier",
        created_at=datetime.now(UTC),
        run_id="run-1",
        confidence=ConfidenceBand(score=0.82, rationale="shadow verdict"),
        metadata=metadata or {},
    )


def _context(**overrides) -> HookContext:
    defaults = {
        "session_id": "session-1",
        "run_id": "run-1",
        "user_message": "Summarize the findings and next actions.",
        "workspace_path": "C:/workspace",
        "active_task_contract": _task_contract(),
        "recent_messages": (
            ChatMessage(
                role=Role.USER,
                content="What changed in retention last week?",
                message_id="msg-user-1",
            ),
            ChatMessage(
                role=Role.TOOL,
                content='{"retention_delta": -0.03, "psi": 0.17}',
                message_id="msg-tool-1",
            ),
        ),
        "emit": MagicMock(),
    }
    defaults.update(overrides)
    return HookContext(**defaults)


@pytest.mark.asyncio
async def test_auto_verifier_runs_for_in_progress_contract_and_records_verdict() -> None:
    verdict = _review_verdict()
    orchestrator = MagicMock(run=AsyncMock(return_value=verdict))
    recorder = MagicMock()
    emit = MagicMock()
    hook = AutoVerifierHook(
        verifier_orchestrator=orchestrator,
        record_review_verdict=recorder,
        mode="shadow",
    )

    result = await hook.on_final_response(
        "Retention fell 3% week over week based on the latest run.",
        _context(emit=emit),
    )

    assert result.modified_response is None
    orchestrator.run.assert_awaited_once()
    recorder.execute.assert_called_once()
    persisted_dto = recorder.execute.call_args.args[0]
    assert persisted_dto.metadata["source"] == "auto_verifier"
    assert persisted_dto.metadata["auto_verifier_mode"] == "shadow"
    verifier_ctx = orchestrator.run.await_args.args[0]
    assert verifier_ctx.run_id == "run-1"
    assert verifier_ctx.artifacts["run_log"] == []
    assert verifier_ctx.config.shadow_mode is True
    assert verifier_ctx.evidence_refs[0].artifact_id == "msg-user-1"
    emit.assert_called_once()
    assert emit.call_args.args[0] == "verifier.auto_run"
    payload = emit.call_args.args[1]
    assert payload["taskId"] == "TC-2026-001"
    assert payload["mode"] == "shadow"
    assert payload["status"] == "success"
    assert payload["verdictId"] == "RV-1"
    assert payload["result"] == "pass"
    assert payload["blockingIssueCount"] == 0
    assert payload["confidenceScore"] == pytest.approx(0.82)
    assert payload["confidenceGrade"] == "high"
    assert payload["durationMs"] >= 0


@pytest.mark.asyncio
async def test_auto_verifier_skips_non_in_progress_contracts() -> None:
    orchestrator = MagicMock(run=AsyncMock())
    hook = AutoVerifierHook(verifier_orchestrator=orchestrator)

    await hook.on_final_response(
        "Ready to close.",
        _context(active_task_contract=_task_contract(TaskContractStatus.REVIEW)),
    )

    orchestrator.run.assert_not_called()


@pytest.mark.asyncio
async def test_auto_verifier_uses_log_mode_without_shadow_flag() -> None:
    verdict = _review_verdict()
    orchestrator = MagicMock(run=AsyncMock(return_value=verdict))
    hook = AutoVerifierHook(verifier_orchestrator=orchestrator, mode="log")

    await hook.on_final_response("Metric drift is mild.", _context())

    verifier_ctx = orchestrator.run.await_args.args[0]
    assert verifier_ctx.config.shadow_mode is False


@pytest.mark.asyncio
async def test_auto_verifier_strips_hidden_review_artifact_markup_from_narrative() -> None:
    verdict = _review_verdict()
    orchestrator = MagicMock(run=AsyncMock(return_value=verdict))
    hook = AutoVerifierHook(verifier_orchestrator=orchestrator)

    await hook.on_final_response(
        (
            "Executive summary.\n\n"
            '<!-- DS_REVIEW_ARTIFACTS {"artifacts": [{"run_id": "run-candidate", '
            '"skill_name": "retrain-vs-rollback", "summary": "s", "narrative": "n", '
            '"artifact": {"recommendation": "retrain"}}]} -->'
        ),
        _context(),
    )

    verifier_ctx = orchestrator.run.await_args.args[0]
    assert verifier_ctx.artifacts["narrative"] == "Executive summary."


@pytest.mark.asyncio
async def test_auto_verifier_threads_semantic_query_payload_into_verifier_artifacts() -> None:
    verdict = _review_verdict()
    orchestrator = MagicMock(run=AsyncMock(return_value=verdict))
    hook = AutoVerifierHook(verifier_orchestrator=orchestrator)

    await hook.on_final_response(
        "Use the semantic metric payload instead of heuristics.",
        _context(
            recent_messages=(
                ChatMessage(
                    role=Role.ASSISTANT,
                    tool_calls=[
                        ToolCall(
                            id="tc-semantic-1",
                            name="semantic_query",
                            arguments={"question": "weekly retention", "required_grain": "weekly"},
                        )
                    ],
                    message_id="msg-assistant-1",
                ),
                ChatMessage(
                    role=Role.TOOL,
                    name="semantic_query",
                    tool_call_id="tc-semantic-1",
                    content=(
                        '{"kind":"verified","metric":{"metric_id":"weekly_retention",'
                        '"definition":"Weekly retained users / weekly active users",'
                        '"grain":"weekly"},"verified_query_id":"vq-1"}'
                    ),
                    message_id="msg-tool-semantic-1",
                ),
            ),
        ),
    )

    verifier_ctx = orchestrator.run.await_args.args[0]
    assert verifier_ctx.artifacts["semantic_metric"] == {
        "metric_id": "weekly_retention",
        "definition": "Weekly retained users / weekly active users",
        "grain": "weekly",
    }
    assert (
        verifier_ctx.artifacts["metric_definition"] == "Weekly retained users / weekly active users"
    )
    assert verifier_ctx.artifacts["required_grain"] == "weekly"
    assert verifier_ctx.artifacts["query_grain"] == "weekly"


@pytest.mark.asyncio
async def test_auto_verifier_ignores_malformed_or_error_semantic_query_payloads() -> None:
    verdict = _review_verdict()
    orchestrator = MagicMock(run=AsyncMock(return_value=verdict))
    hook = AutoVerifierHook(verifier_orchestrator=orchestrator)

    await hook.on_final_response(
        "Ignore broken semantic tool payloads.",
        _context(
            recent_messages=(
                ChatMessage(
                    role=Role.ASSISTANT,
                    tool_calls=[
                        ToolCall(
                            id="tc-semantic-1",
                            name="semantic_query",
                            arguments={"question": "weekly retention", "required_grain": "weekly"},
                        )
                    ],
                    message_id="msg-assistant-1",
                ),
                ChatMessage(
                    role=Role.TOOL,
                    name="semantic_query",
                    tool_call_id="tc-semantic-1",
                    content='{"error":"semantic lookup failed"}',
                    message_id="msg-tool-semantic-1",
                ),
                ChatMessage(
                    role=Role.TOOL,
                    name="semantic_query",
                    tool_call_id="tc-semantic-1",
                    content="{not-json}",
                    message_id="msg-tool-semantic-2",
                ),
            ),
        ),
    )

    verifier_ctx = orchestrator.run.await_args.args[0]
    assert "semantic_metric" not in verifier_ctx.artifacts
    assert "metric_definition" not in verifier_ctx.artifacts
    assert "required_grain" not in verifier_ctx.artifacts
    assert "query_grain" not in verifier_ctx.artifacts


@pytest.mark.asyncio
async def test_auto_verifier_timeout_does_not_raise_or_modify_response() -> None:
    emit = MagicMock()
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(side_effect=TimeoutError)),
    )

    result = await hook.on_final_response("Final answer.", _context(emit=emit))

    assert result.modified_response is None
    assert [call.args[0] for call in emit.call_args_list] == [
        "verifier.auto_run",
        "harness.warning",
    ]
    verifier_payload = emit.call_args_list[0].args[1]
    assert verifier_payload["status"] == "timeout"
    assert verifier_payload["mode"] == "shadow"
    assert verifier_payload["errorType"] == "TimeoutError"
    assert verifier_payload["durationMs"] >= 0
    warning_payload = emit.call_args_list[1].args[1]
    assert warning_payload["source"] == "auto_verifier"


@pytest.mark.asyncio
async def test_auto_verifier_error_emits_telemetry_and_warning() -> None:
    emit = MagicMock()
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(side_effect=ValueError("boom"))),
        mode="log",
    )

    result = await hook.on_final_response("Final answer.", _context(emit=emit))

    assert result.modified_response is None
    assert [call.args[0] for call in emit.call_args_list] == [
        "verifier.auto_run",
        "harness.warning",
    ]
    verifier_payload = emit.call_args_list[0].args[1]
    assert verifier_payload["status"] == "error"
    assert verifier_payload["mode"] == "log"
    assert verifier_payload["errorType"] == "ValueError"
    assert verifier_payload["durationMs"] >= 0


@pytest.mark.asyncio
async def test_auto_verifier_emits_warning_for_unmapped_mission_required_checks() -> None:
    emit = MagicMock()
    verdict = _review_verdict(
        metadata={
            "mission_name": "data_analysis",
            "mission_pack_loaded": True,
            "mission_unmapped_required_checks": ["metric_definition_confirmed"],
        }
    )
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(return_value=verdict)),
        mode="shadow",
    )

    result = await hook.on_final_response("Final answer.", _context(emit=emit))

    assert result.modified_response is None
    assert [call.args[0] for call in emit.call_args_list] == [
        "verifier.auto_run",
        "harness.warning",
    ]
    assert (
        emit.call_args_list[1].args[1]["message"]
        == "mission pack required_checks are not mapped to verifier inventory: "
        "metric_definition_confirmed"
    )


@pytest.mark.asyncio
async def test_auto_verifier_emits_warning_when_mission_pack_is_missing() -> None:
    emit = MagicMock()
    verdict = _review_verdict(
        metadata={
            "mission_name": "unknown-mission",
            "mission_pack_loaded": False,
        }
    )
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(return_value=verdict)),
        mode="shadow",
    )

    await hook.on_final_response("Final answer.", _context(emit=emit))

    assert [call.args[0] for call in emit.call_args_list] == [
        "verifier.auto_run",
        "harness.warning",
    ]
    assert (
        emit.call_args_list[1].args[1]["message"]
        == "mission pack required_checks could not be loaded for verifier preflight: "
        "unknown-mission"
    )


@pytest.mark.asyncio
async def test_auto_verifier_reuses_cached_result_for_identical_run_and_response() -> None:
    emit = MagicMock()
    verdict = _review_verdict()
    orchestrator = MagicMock(run=AsyncMock(return_value=verdict))
    hook = AutoVerifierHook(
        verifier_orchestrator=orchestrator,
        mode="shadow",
    )
    context = _context(emit=emit)

    first = await hook.on_final_response("Final answer.", context)
    second = await hook.on_final_response("Final answer.", context)

    assert first.modified_response is None
    assert second.modified_response is None
    orchestrator.run.assert_awaited_once()
    assert [call.args[0] for call in emit.call_args_list] == ["verifier.auto_run"]


@pytest.mark.asyncio
async def test_auto_verifier_block_mode_appends_remediation_and_marks_followup() -> None:
    emit = MagicMock()
    verdict = _review_verdict()
    verdict.blocking_issues = [
        Issue(
            issue_id="ISSUE-1",
            layer="policy",
            check_id="lineage_citation",
            severity="critical",
            message="Data lineage is missing for the customer extract.",
            blocking=True,
        )
    ]
    verdict.recommended_actions = [
        ActionHint(
            action_id="ACTION-1",
            title="Attach lineage evidence",
            description="Cite the source table and extract timestamp before review.",
        )
    ]
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(return_value=verdict)),
        mode="block",
    )

    result = await hook.on_final_response(
        "Final answer.",
        _context(
            emit=emit,
            active_task_contract=_task_contract(min_confidence_grade="medium"),
        ),
    )

    assert result.modified_response is not None
    assert (
        "Verifier follow-up required before this task can move to review."
        in result.modified_response
    )
    assert "Data lineage is missing for the customer extract." in result.modified_response
    assert "Attach lineage evidence" in result.modified_response
    assert result.requires_followup is True
    assert result.followup_reason == "Data lineage is missing for the customer extract."
    assert emit.call_args_list[0].args[0] == "verifier.auto_run"


@pytest.mark.asyncio
async def test_auto_verifier_block_mode_respects_confidence_threshold() -> None:
    verdict = _review_verdict()
    verdict.confidence = ConfidenceBand(score=0.55, rationale="borderline")
    verdict.blocking_issues = [
        Issue(
            issue_id="ISSUE-2",
            layer="policy",
            check_id="lineage_citation",
            severity="critical",
            message="Lineage citation is still missing.",
            blocking=True,
        )
    ]
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(return_value=verdict)),
        mode="block",
    )

    result = await hook.on_final_response(
        "Final answer.",
        _context(active_task_contract=_task_contract(min_confidence_grade="high")),
    )

    assert result.modified_response is None
    assert result.requires_followup is False


# ---------------------------------------------------------------------------
# Gap 2A-3: persist failure → logger.exception (error-level) signal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_contract_verdict_exception_is_logged_at_error_level(capsys) -> None:
    """_persist_contract_verdict failures must be logged via logger.exception (error-level).

    structlog writes to stdout in test environments.  We verify that the
    error key appears in the captured output and that the hook itself does
    NOT re-raise (response is unmodified).
    """
    recorder = MagicMock()
    recorder.execute.side_effect = RuntimeError("db gone")
    verdict = _review_verdict()
    orchestrator = MagicMock(run=AsyncMock(return_value=verdict))
    hook = AutoVerifierHook(
        verifier_orchestrator=orchestrator,
        record_review_verdict=recorder,
        mode="shadow",
    )

    result = await hook.on_final_response("Final answer.", _context())

    # The hook must not crash — response is unmodified
    assert result.modified_response is None
    # structlog error output should contain the event key and the traceback
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "auto_verifier_contract_persist_failed" in output, (
        f"Expected error-level log for persist failure in captured output; got:\n{output}"
    )
    # Confirm exc_info was included: logger.exception captures the traceback
    assert "RuntimeError" in output or "db gone" in output


# ---------------------------------------------------------------------------
# Gap 2B-2: followup_reason must prefer critical+blocking issue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_followup_reason_prefers_critical_blocking_issue_over_first_in_list() -> None:
    """When blocking_issues[0] is not critical, followup_reason must pick the first critical one."""
    emit = MagicMock()
    verdict = _review_verdict()
    # First issue is medium severity (not critical), second is critical
    verdict.blocking_issues = [
        Issue(
            issue_id="ISSUE-A",
            layer="policy",
            check_id="formatting",
            severity="medium",
            message="Minor formatting issue.",
            blocking=True,
        ),
        Issue(
            issue_id="ISSUE-B",
            layer="policy",
            check_id="lineage_citation",
            severity="critical",
            message="Critical: data lineage is absent.",
            blocking=True,
        ),
    ]
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(return_value=verdict)),
        mode="block",
    )

    result = await hook.on_final_response(
        "Final answer.",
        _context(
            emit=emit,
            active_task_contract=_task_contract(min_confidence_grade="medium"),
        ),
    )

    assert result.requires_followup is True
    # Must pick the critical issue, not the first (medium) one
    assert result.followup_reason == "Critical: data lineage is absent."


@pytest.mark.asyncio
async def test_followup_reason_uses_first_critical_blocking_when_only_critical_exists() -> None:
    """When blocking_issues[0] is the sole critical+blocking issue, followup_reason uses it."""
    emit = MagicMock()
    verdict = _review_verdict()
    verdict.blocking_issues = [
        Issue(
            issue_id="ISSUE-C",
            layer="policy",
            check_id="completeness",
            severity="critical",
            message="Only one critical blocking issue present.",
            blocking=True,
        ),
    ]
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(return_value=verdict)),
        mode="block",
    )

    result = await hook.on_final_response(
        "Final answer.",
        _context(
            emit=emit,
            active_task_contract=_task_contract(min_confidence_grade="medium"),
        ),
    )

    assert result.requires_followup is True
    assert result.followup_reason == "Only one critical blocking issue present."


# ---------------------------------------------------------------------------
# Gap 2A-4: verifier.remediation_pending event emitted on fail/warn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remediation_pending_event_emitted_on_warn_verdict() -> None:
    """verifier.remediation_pending must be emitted when verdict is warn with issues."""
    emit = MagicMock()
    verdict = _review_verdict()
    verdict.result = "warn"
    verdict.blocking_issues = [
        Issue(
            issue_id="ISSUE-D",
            layer="data",
            check_id="freshness",
            severity="medium",
            message="Data freshness may be stale.",
            blocking=False,
        )
    ]
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(return_value=verdict)),
        mode="shadow",
    )

    await hook.on_final_response("Final answer.", _context(emit=emit))

    event_names = [call.args[0] for call in emit.call_args_list]
    assert "verifier.remediation_pending" in event_names

    remediation_call = next(
        call for call in emit.call_args_list
        if call.args[0] == "verifier.remediation_pending"
    )
    payload = remediation_call.args[1]
    assert payload["verdictResult"] == "warn"
    assert payload["taskId"] == "TC-2026-001"
    assert len(payload["issues"]) == 1
    assert payload["issues"][0]["message"] == "Data freshness may be stale."


@pytest.mark.asyncio
async def test_remediation_pending_event_not_emitted_on_pass_verdict() -> None:
    """verifier.remediation_pending must NOT be emitted when verdict result is pass."""
    emit = MagicMock()
    verdict = _review_verdict()
    # Default result is "pass" with no blocking issues
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(return_value=verdict)),
        mode="shadow",
    )

    await hook.on_final_response("Final answer.", _context(emit=emit))

    event_names = [call.args[0] for call in emit.call_args_list]
    assert "verifier.remediation_pending" not in event_names


@pytest.mark.asyncio
async def test_remediation_pending_event_not_emitted_when_no_issues_or_actions() -> None:
    """verifier.remediation_pending must NOT be emitted when warn verdict has no issues/actions."""
    emit = MagicMock()
    verdict = _review_verdict()
    verdict.result = "warn"
    # No blocking_issues and no recommended_actions
    hook = AutoVerifierHook(
        verifier_orchestrator=MagicMock(run=AsyncMock(return_value=verdict)),
        mode="shadow",
    )

    await hook.on_final_response("Final answer.", _context(emit=emit))

    event_names = [call.args[0] for call in emit.call_args_list]
    assert "verifier.remediation_pending" not in event_names
