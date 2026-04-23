"""Auto-run the verifier on final responses for active task contracts."""

from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from time import perf_counter, time
from typing import TYPE_CHECKING, Any

import structlog

from ds_agent.agent.hooks import FinalResponseResult, HookContext, ToolHook
from ds_agent.application.dtos.task_contract import ReviewVerdictInputDTO
from ds_agent.application.services.review_artifact_capture import (
    extract_review_artifact_captures,
)
from ds_agent.domain.dtos.verifier_context import EvidenceRef, VerifierConfig, VerifierContext
from ds_agent.domain.entities.messages import ChatMessage, Role
from ds_agent.domain.entities.review_verdict import ReviewVerdict
from ds_agent.domain.entities.task_contract import TaskContractStatus
from ds_agent.runtime.verifier_shadow_runtime import snapshot_shadow_runtime_log

if TYPE_CHECKING:
    from ds_agent.application.services.task_contract_usecases import RecordReviewVerdictUseCase
    from ds_agent.application.services.verifier_orchestrator import VerifierOrchestrator
    from ds_agent.domain.entities.review_verdict import ReviewVerdict

logger = structlog.get_logger()

_CONFIDENCE_ORDER = {
    "insufficient": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}
_DEFAULT_BLOCKING_CONFIDENCE_GRADE = "medium"
_MAX_RECENT_AUTO_VERIFIER_RESULTS = 64
_REMEDIATION_TEMPLATE = (
    "\n\n---\n"
    "Verifier follow-up required before this task can move to review.\n\n"
    "Critical issues:\n"
    "{issues}\n\n"
    "Required follow-up:\n"
    "{actions}"
)


class AutoVerifierHook(ToolHook):
    """Persist verifier verdicts for active in-progress task contracts."""

    name = "auto_verifier"
    priority = 59

    def __init__(
        self,
        *,
        verifier_orchestrator: VerifierOrchestrator | None,
        record_review_verdict: RecordReviewVerdictUseCase | None = None,
        mode: str = "shadow",
    ) -> None:
        self._verifier = verifier_orchestrator
        self._record_review_verdict = record_review_verdict
        self._mode = mode
        self._recent_results: OrderedDict[str, FinalResponseResult] = OrderedDict()

    @property
    def verifier_orchestrator(self) -> VerifierOrchestrator | None:
        return self._verifier

    @property
    def mode(self) -> str:
        return self._mode

    async def on_final_response(
        self,
        response: str,
        context: HookContext,
    ) -> FinalResponseResult:
        verifier = context.verifier_orchestrator or self._verifier
        contract = context.active_task_contract
        if verifier is None or contract is None:
            return FinalResponseResult()
        if contract.status != TaskContractStatus.IN_PROGRESS:
            return FinalResponseResult()
        if not context.run_id:
            logger.debug(
                "auto_verifier_skipped_missing_run_id",
                session_id=context.session_id,
                task_id=contract.task_id,
            )
            return FinalResponseResult()

        cache_key = _cache_key(
            session_id=context.session_id,
            run_id=context.run_id,
            task_id=contract.task_id,
            mode=self._mode,
            response=response,
        )
        cached_result = self._recent_results.get(cache_key)
        if cached_result is not None:
            self._recent_results.move_to_end(cache_key)
            logger.info(
                "auto_verifier_reused_cached_result",
                session_id=context.session_id,
                run_id=context.run_id,
                task_id=contract.task_id,
                mode=self._mode,
            )
            return cached_result

        started_at = perf_counter()
        try:
            verifier_context = self._build_context(response, context)
            verdict = await verifier.run(verifier_context)
        except TimeoutError:
            duration_ms = _elapsed_ms(started_at)
            self._emit_auto_run_event(
                context,
                task_id=contract.task_id,
                status="timeout",
                duration_ms=duration_ms,
                error_type="TimeoutError",
            )
            self._emit_warning(
                context,
                "auto verifier timed out; response will not be blocked",
            )
            logger.warning(
                "auto_verifier_timed_out",
                session_id=context.session_id,
                run_id=context.run_id,
                task_id=contract.task_id,
                mode=self._mode,
                duration_ms=duration_ms,
            )
            self._persist_contract_verdict(
                _build_fallback_verdict(
                    task_id=contract.task_id,
                    run_id=context.run_id,
                    auto_verifier_status="timeout",
                    summary="Auto verifier timed out; verdict is inconclusive for this turn.",
                )
            )
            return self._store_cached_result(cache_key, FinalResponseResult())
        except Exception as exc:
            duration_ms = _elapsed_ms(started_at)
            self._emit_auto_run_event(
                context,
                task_id=contract.task_id,
                status="error",
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
            )
            self._emit_warning(
                context,
                "auto verifier failed; response will not be blocked",
            )
            logger.warning(
                "auto_verifier_failed",
                session_id=context.session_id,
                run_id=context.run_id,
                task_id=contract.task_id,
                mode=self._mode,
                duration_ms=duration_ms,
                error=str(exc),
            )
            self._persist_contract_verdict(
                _build_fallback_verdict(
                    task_id=contract.task_id,
                    run_id=context.run_id,
                    auto_verifier_status="error",
                    summary=f"Auto verifier error ({type(exc).__name__}); verdict is inconclusive for this turn.",
                    error_type=type(exc).__name__,
                )
            )
            return self._store_cached_result(cache_key, FinalResponseResult())

        self._persist_contract_verdict(verdict)
        duration_ms = _elapsed_ms(started_at)
        self._emit_auto_run_event(
            context,
            task_id=contract.task_id,
            status="success",
            duration_ms=duration_ms,
            verdict=verdict,
        )
        self._emit_mission_check_warning(context, verdict)
        self._emit_remediation_pending_if_needed(context, verdict)
        logger.info(
            "auto_verifier_completed",
            session_id=context.session_id,
            run_id=context.run_id,
            task_id=contract.task_id,
            verdict_id=verdict.verdict_id,
            result=verdict.result,
            blocking_issue_count=len(verdict.blocking_issues),
            mode=self._mode,
            duration_ms=duration_ms,
        )
        if self._should_block_response(verdict, contract):
            remediation = self._build_remediation_text(verdict)
            critical_blocking = [
                issue
                for issue in verdict.blocking_issues
                if issue.blocking and issue.severity == "critical"
            ]
            followup_reason = (
                critical_blocking[0] if critical_blocking else verdict.blocking_issues[0]
            ).message
            logger.info(
                "auto_verifier_blocked_response",
                session_id=context.session_id,
                run_id=context.run_id,
                task_id=contract.task_id,
                verdict_id=verdict.verdict_id,
                confidence_grade=(None if verdict.confidence is None else verdict.confidence.grade),
                blocking_issue_count=len(verdict.blocking_issues),
            )
            return self._store_cached_result(
                cache_key,
                FinalResponseResult(
                    modified_response=_append_remediation(response, remediation),
                    requires_followup=True,
                    followup_reason=followup_reason,
                ),
            )
        return self._store_cached_result(cache_key, FinalResponseResult())

    def _build_context(self, response: str, context: HookContext) -> VerifierContext:
        contract = context.active_task_contract
        if contract is None:
            raise ValueError("active task contract is required")

        parsed = extract_review_artifact_captures(response)
        if parsed.errors:
            logger.warning(
                "auto_verifier_artifact_strip_failed",
                session_id=context.session_id,
                run_id=context.run_id,
                errors=parsed.errors,
            )

        narrative = parsed.cleaned_response.strip() or response.strip()
        run_log = snapshot_shadow_runtime_log(context.session_id, context.run_id)
        artifacts: dict[str, object] = {
            "narrative": narrative,
            "run_log": run_log,
        }
        artifacts.update(self._extract_semantic_query_artifacts(context.recent_messages))
        return VerifierContext(
            run_id=context.run_id or f"{contract.task_id}:{contract.session_id}",
            task_contract=contract,
            artifacts=artifacts,
            run_log=run_log,
            evidence_refs=self._build_evidence_refs(context.recent_messages, context.user_message),
            config=VerifierConfig(shadow_mode=self._mode == "shadow"),
            workspace_path=context.workspace_path,
        )

    def _persist_contract_verdict(self, verdict: ReviewVerdict) -> None:
        if self._record_review_verdict is None:
            return
        verdict.metadata.setdefault("source", "auto_verifier")
        verdict.metadata.setdefault("auto_verifier_mode", self._mode)
        try:
            self._record_review_verdict.execute(
                ReviewVerdictInputDTO(
                    task_id=verdict.task_id,
                    verdict_id=verdict.verdict_id,
                    category=verdict.category,
                    result=verdict.result,
                    reviewer=verdict.reviewer,
                    summary=verdict.summary,
                    evidence_refs=verdict.evidence_refs,
                    run_id=verdict.run_id,
                    layers=verdict.layers,
                    blocking_issues=verdict.blocking_issues,
                    confidence=verdict.confidence,
                    recommended_actions=verdict.recommended_actions,
                    metadata=verdict.metadata,
                )
            )
        except Exception:
            logger.exception(
                "auto_verifier_contract_persist_failed",
                task_id=verdict.task_id,
                verdict_id=verdict.verdict_id,
            )

    @staticmethod
    def _build_evidence_refs(
        messages: Sequence[ChatMessage],
        fallback_user_message: str | None,
    ) -> list[EvidenceRef]:
        refs: list[EvidenceRef] = []
        for index, message in enumerate(messages[-8:], start=1):
            if message.role == Role.SYSTEM or not message.content or not message.content.strip():
                continue
            refs.append(
                EvidenceRef(
                    artifact_id=message.message_id or f"turn-message-{index}",
                    excerpt=_truncate(message.content.strip()),
                    locator=message.role.value,
                    metadata={"role": message.role.value},
                )
            )
        if refs or not fallback_user_message or not fallback_user_message.strip():
            return refs
        return [
            EvidenceRef(
                artifact_id="turn-user-message",
                excerpt=_truncate(fallback_user_message.strip()),
                locator="user",
                metadata={"role": "user"},
            )
        ]

    @staticmethod
    def _extract_semantic_query_artifacts(
        messages: Sequence[ChatMessage],
    ) -> dict[str, object]:
        query_args_by_tool_call_id: dict[str, dict[str, Any]] = {}
        for message in messages:
            if message.role != Role.ASSISTANT or not message.tool_calls:
                continue
            for tool_call in message.tool_calls:
                if tool_call.name != "semantic_query":
                    continue
                query_args_by_tool_call_id[tool_call.id] = tool_call.arguments

        artifacts: dict[str, object] = {}
        for message in reversed(messages):
            if message.role != Role.TOOL or message.name != "semantic_query":
                continue
            payload = _parse_tool_payload(message.content)
            if not isinstance(payload, dict) or "error" in payload:
                continue

            metric = payload.get("metric")
            if isinstance(metric, dict) and metric:
                artifacts.setdefault("semantic_metric", metric)
                definition = metric.get("definition")
                if isinstance(definition, str) and definition.strip():
                    artifacts.setdefault("metric_definition", definition.strip())
                grain = metric.get("grain")
                if isinstance(grain, str) and grain.strip():
                    artifacts.setdefault("query_grain", grain.strip())

            tool_args = (
                query_args_by_tool_call_id.get(message.tool_call_id or "")
                if message.tool_call_id
                else None
            )
            if isinstance(tool_args, dict):
                required_grain = tool_args.get("required_grain")
                if isinstance(required_grain, str) and required_grain.strip():
                    artifacts.setdefault("required_grain", required_grain.strip())

            if artifacts:
                break
        return artifacts

    @staticmethod
    def _emit_warning(context: HookContext, message: str) -> None:
        context.emit(
            "harness.warning",
            {
                "sessionId": context.session_id,
                "runId": context.run_id,
                "source": "auto_verifier",
                "message": message,
            },
        )

    def _emit_auto_run_event(
        self,
        context: HookContext,
        *,
        task_id: str,
        status: str,
        duration_ms: int,
        verdict: ReviewVerdict | None = None,
        error_type: str | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "sessionId": context.session_id,
            "runId": context.run_id,
            "taskId": task_id,
            "mode": self._mode,
            "status": status,
            "durationMs": duration_ms,
        }
        if verdict is not None:
            payload["verdictId"] = verdict.verdict_id
            payload["result"] = verdict.result
            payload["blockingIssueCount"] = len(verdict.blocking_issues)
            if verdict.confidence is not None:
                payload["confidenceScore"] = verdict.confidence.score
                if verdict.confidence.grade is not None:
                    payload["confidenceGrade"] = verdict.confidence.grade
        if error_type:
            payload["errorType"] = error_type
        context.emit("verifier.auto_run", payload)

    def _emit_mission_check_warning(
        self,
        context: HookContext,
        verdict: ReviewVerdict,
    ) -> None:
        if verdict.metadata.get("mission_pack_loaded") is False:
            mission_name = verdict.metadata.get("mission_name")
            if isinstance(mission_name, str) and mission_name.strip():
                self._emit_warning(
                    context,
                    (
                        "mission pack required_checks could not be loaded for verifier preflight: "
                        f"{mission_name.strip()}"
                    ),
                )
            return

        unmapped = verdict.metadata.get("mission_unmapped_required_checks")
        if not isinstance(unmapped, list) or not unmapped:
            return
        unresolved = [item.strip() for item in unmapped if isinstance(item, str) and item.strip()]
        if not unresolved:
            return
        self._emit_warning(
            context,
            (
                "mission pack required_checks are not mapped to verifier inventory: "
                + ", ".join(unresolved[:5])
            ),
        )

    def _emit_remediation_pending_if_needed(
        self,
        context: HookContext,
        verdict: ReviewVerdict,
    ) -> None:
        """Emit a structured event so the next turn can reinjest verifier findings.

        HookContext does not expose a working_memory_store, so the remediation
        payload is broadcast as a structured event (verifier.remediation_pending).
        An outer session loop or middleware can listen and rewrite working memory
        before the next prompt is built.
        """
        if verdict.result not in ("fail", "warn"):
            return
        if not verdict.blocking_issues and not verdict.recommended_actions:
            return
        issue_summaries = [
            {
                "severity": issue.severity,
                "message": issue.message,
                "blocking": issue.blocking,
            }
            for issue in verdict.blocking_issues[:10]
        ]
        action_summaries = [
            {"title": action.title, "description": action.description}
            for action in verdict.recommended_actions[:5]
        ]
        context.emit(
            "verifier.remediation_pending",
            {
                "sessionId": context.session_id,
                "runId": context.run_id,
                "taskId": verdict.task_id,
                "verdictId": verdict.verdict_id,
                "verdictResult": verdict.result,
                "issues": issue_summaries,
                "recommendedActions": action_summaries,
            },
        )

    def _should_block_response(self, verdict: ReviewVerdict, contract: object) -> bool:
        if self._mode != "block":
            return False
        critical_issues = [
            issue
            for issue in verdict.blocking_issues
            if issue.blocking and issue.severity == "critical"
        ]
        if not critical_issues:
            return False
        confidence = verdict.confidence
        if confidence is None or confidence.grade is None:
            return False
        threshold = _blocking_confidence_threshold(contract)
        return _CONFIDENCE_ORDER[confidence.grade] >= _CONFIDENCE_ORDER[threshold]

    def _build_remediation_text(self, verdict: ReviewVerdict) -> str:
        critical_issues = [
            issue
            for issue in verdict.blocking_issues
            if issue.blocking and issue.severity == "critical"
        ]
        issue_lines = "\n".join(
            _format_issue_line(issue.layer, issue.check_id, issue.message)
            for issue in critical_issues[:5]
        )
        action_lines: list[str] = []
        for action in verdict.recommended_actions[:5]:
            detail = action.description or "Resolve the verifier finding and rerun the review."
            action_lines.append(f"- {action.title}: {detail}")
        if not action_lines:
            action_lines.append(
                "- Revise the response and supporting artifacts, then rerun the verifier."
            )
        return _REMEDIATION_TEMPLATE.format(
            issues=issue_lines,
            actions="\n".join(action_lines),
        )

    def _store_cached_result(
        self,
        cache_key: str,
        result: FinalResponseResult,
    ) -> FinalResponseResult:
        self._recent_results[cache_key] = result
        self._recent_results.move_to_end(cache_key)
        while len(self._recent_results) > _MAX_RECENT_AUTO_VERIFIER_RESULTS:
            self._recent_results.popitem(last=False)
        return result


def _truncate(text: str, limit: int = 400) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))


def _cache_key(
    *,
    session_id: str | None,
    run_id: str,
    task_id: str,
    mode: str,
    response: str,
) -> str:
    response_hash = sha256(response.rstrip().encode("utf-8")).hexdigest()
    return "|".join(
        [
            session_id or "",
            run_id,
            task_id,
            mode,
            response_hash,
        ]
    )


def _blocking_confidence_threshold(contract: object) -> str:
    definition_of_done = getattr(contract, "definition_of_done", None)
    verifier = None if definition_of_done is None else getattr(definition_of_done, "verifier", None)
    threshold = None if verifier is None else getattr(verifier, "min_confidence_grade", None)
    if isinstance(threshold, str) and threshold in _CONFIDENCE_ORDER:
        return threshold
    return _DEFAULT_BLOCKING_CONFIDENCE_GRADE


def _format_issue_line(layer: str | None, check_id: str | None, message: str) -> str:
    parts = [part for part in [layer, check_id] if part]
    prefix = ".".join(parts) if parts else "critical_issue"
    return f"- [{prefix}] {message}"


def _append_remediation(response: str, remediation: str) -> str:
    return response.rstrip() + remediation


def _parse_tool_payload(content: str | None) -> object:
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def _build_fallback_verdict(
    *,
    task_id: str,
    run_id: str | None,
    auto_verifier_status: str,
    summary: str,
    error_type: str | None = None,
) -> ReviewVerdict:
    verdict_id = f"RV-{int(time() * 1000)}"
    metadata: dict[str, object] = {
        "source": "auto_verifier",
        "auto_verifier_status": auto_verifier_status,
    }
    if error_type is not None:
        metadata["error_type"] = error_type
    return ReviewVerdict(
        verdict_id=verdict_id,
        task_id=task_id,
        category="orchestrator",
        result="warn",
        reviewer="verifier_orchestrator",
        summary=summary,
        run_id=run_id,
        metadata=metadata,
        created_at=datetime.now(UTC),
    )
