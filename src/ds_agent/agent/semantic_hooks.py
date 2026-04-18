"""Semantic-memory enforcement hooks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ds_agent.agent.hooks import (
    HookAction,
    HookContext,
    PostToolUseResult,
    PreToolUseResult,
    ToolHook,
)
from ds_agent.infrastructure.semantic_memory_runtime import get_semantic_memory_container
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.org_context import NegativeKnowledge
from ds_agent.memory.semantic.domain.proposal import SemanticProposalType
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery
from ds_agent.runtime.approval_payloads import serialize_approval
from ds_agent.runtime.semantic_proposal_router import create_semantic_proposal_approval
from ds_agent.runtime.tool_runtime_context import get_tool_runtime_context

_SQL_TABLE_PATTERN = re.compile(
    r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_.$]*|\"[^\"]+\")",
    re.IGNORECASE,
)


_SEMANTIC_TOOLS = frozenset({"semantic_query", "lookup_term"})
_METRIC_LIKE_PATTERN = re.compile(
    r"\b("
    r"churn|retention|gmv|revenue|mrr|arr|arpu|ltv|"
    r"conversion|ctr|roas|margin|aov|dau|wau|mau|"
    r"kpi|metric|active users?|signups?"
    r")\b",
    re.IGNORECASE,
)
_VERIFIER_WRITEBACK_RESULTS = frozenset({"pass", "warn"})


@dataclass(frozen=True)
class _TrustAssessment:
    action: str
    warnings: list[str]
    missing_tables: list[str]
    table_names: list[str]


class SemanticReadGuardHook(ToolHook):
    """Warn when raw SQL is used before semantic grounding on metric-like requests."""

    name = "semantic_read_guard"
    priority = 14

    def __init__(self) -> None:
        self._semantic_seen_sessions: set[str] = set()
        self._pending_warning_sessions: set[str] = set()

    async def pre_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        context: HookContext,
    ) -> PreToolUseResult:
        session_key = self._session_key(context)
        if tool_name in _SEMANTIC_TOOLS:
            return PreToolUseResult()

        if tool_name != "sql_query":
            return PreToolUseResult()

        if session_key in self._semantic_seen_sessions:
            return PreToolUseResult()

        if not self._looks_metric_like(context.user_message):
            return PreToolUseResult()

        warning = (
            "Metric-like request detected before semantic grounding. "
            "Prefer semantic_query or lookup_term before raw sql_query."
        )
        self._pending_warning_sessions.add(session_key)
        context.emit(
            "harness.warning",
            {
                "type": "semantic_read_guard",
                "tool": tool_name,
                "recommended_tool": "semantic_query",
                "message": warning,
            },
        )
        return PreToolUseResult()

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        session_key = self._session_key(context)

        if tool_name in _SEMANTIC_TOOLS and not is_error:
            self._semantic_seen_sessions.add(session_key)
            self._pending_warning_sessions.discard(session_key)
            return PostToolUseResult()

        if tool_name != "sql_query" or session_key not in self._pending_warning_sessions:
            return PostToolUseResult()

        self._pending_warning_sessions.discard(session_key)
        warning_text = (
            "\n\n---\n"
            "**Semantic memory warning**:\n"
            "- Metric-like request executed with `sql_query` before `semantic_query` "
            "or `lookup_term`."
        )
        return PostToolUseResult(modified_result=result + warning_text)

    @staticmethod
    def _looks_metric_like(user_message: str | None) -> bool:
        if not user_message:
            return False
        return _METRIC_LIKE_PATTERN.search(user_message) is not None

    @staticmethod
    def _session_key(context: HookContext) -> str:
        return context.session_id or "__global__"


class SemanticTrustHook(ToolHook):
    """Evaluate semantic trust policy before SQL execution."""

    name = "semantic_trust"
    priority = 16

    async def pre_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        context: HookContext,
    ) -> PreToolUseResult:
        if tool_name != "sql_query":
            return PreToolUseResult()

        sql = arguments.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            return PreToolUseResult()

        tables = self._extract_tables(sql)
        if not tables:
            return PreToolUseResult()

        assessment = self._evaluate_tables(tables)
        if assessment.action == "allow":
            return PreToolUseResult()

        if assessment.action == "caveat":
            context.emit(
                "harness.warning",
                {
                    "type": "semantic_trust",
                    "severity": "medium",
                    "tables": assessment.table_names,
                    "message": "; ".join(assessment.warnings) or "Semantic trust caveat",
                },
            )
            return PreToolUseResult()

        approval_id = self._request_approval(context, assessment)
        deny_reason = (
            f"Semantic trust policy requires confirmation for tables: "
            f"{', '.join(assessment.table_names)}."
        )
        if assessment.warnings:
            deny_reason += f" Warnings: {'; '.join(assessment.warnings)}."
        if approval_id is not None:
            deny_reason += f" (approval_id={approval_id})"
        return PreToolUseResult(action=HookAction.DENY, deny_reason=deny_reason)

    @staticmethod
    def _extract_tables(sql: str) -> list[str]:
        tables: list[str] = []
        seen: set[str] = set()
        for match in _SQL_TABLE_PATTERN.finditer(sql):
            raw = match.group(1).strip()
            normalized = raw.strip('"')
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            tables.append(normalized)
        return tables

    @staticmethod
    def _evaluate_tables(tables: list[str]) -> _TrustAssessment:
        result = get_semantic_memory_container().check_table_trust.execute(tables)
        return _TrustAssessment(
            action=result.action,
            warnings=result.warnings,
            missing_tables=result.missing_tables,
            table_names=[table.fqtn for table in result.tables] + result.missing_tables,
        )

    @staticmethod
    def _request_approval(
        context: HookContext,
        assessment: _TrustAssessment,
    ) -> str | None:
        if context.approval_store is None or context.session_id is None:
            return None

        runtime_context = get_tool_runtime_context()
        run_id = runtime_context.run_id if runtime_context is not None else None
        approval = context.approval_store.create(
            session_id=context.session_id,
            run_id=run_id,
            surface="agent",
            question=(
                "Approve SQL execution for semantic trust escalation: "
                f"{', '.join(assessment.table_names)}?"
            ),
            options=["approve", "reject"],
            default="reject",
        )
        approval_id = getattr(approval, "approval_id", None)
        context.emit(
            "approval.requested",
            {
                "approvalId": approval_id,
                "sessionId": context.session_id,
                "surface": "agent",
                "question": getattr(approval, "question", ""),
                "options": list(getattr(approval, "options", []) or []),
                "type": "semantic_trust",
                "tables": assessment.table_names,
                "warnings": assessment.warnings,
            },
        )
        context.emit(
            "semantic.trust_escalation",
            {
                "approvalId": approval_id,
                "tables": assessment.table_names,
                "action": assessment.action,
                "warnings": assessment.warnings,
            },
        )
        return approval_id if isinstance(approval_id, str) else None


class SemanticWritebackHook(ToolHook):
    """Persist semantic proposals after successful verifier outcomes."""

    name = "semantic_writeback"
    priority = 18

    async def post_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        is_error: bool,
        context: HookContext,
    ) -> PostToolUseResult:
        if tool_name != "run_verifier" or is_error:
            return PostToolUseResult()

        parsed_result = self._parse_result_payload(result)
        if parsed_result is None:
            return PostToolUseResult()

        candidates = self._extract_candidates(arguments)
        if not candidates:
            return PostToolUseResult()

        verdict_payload = parsed_result.get("payload")
        if not isinstance(verdict_payload, dict):
            return PostToolUseResult()

        verdict_result = str(verdict_payload.get("result") or "").casefold()
        if verdict_result not in _VERIFIER_WRITEBACK_RESULTS:
            warning = (
                "Semantic writeback skipped because verifier result was "
                f"'{verdict_result or 'unknown'}'."
            )
            self._emit_warning(context, warning)
            return PostToolUseResult(
                modified_result=self._inject_writeback(
                    parsed_result,
                    entries=[],
                    warnings=[warning],
                )
            )

        container = get_semantic_memory_container()
        writeback_entries: list[dict[str, Any]] = []
        warnings: list[str] = []
        for index, candidate in enumerate(candidates, start=1):
            try:
                prepared = self._prepare_submission(
                    candidate=candidate,
                    arguments=arguments,
                    parsed_result=parsed_result,
                    verdict_payload=verdict_payload,
                    context=context,
                )
                submission = container.submit_semantic_proposal.execute(**prepared)
            except ValueError as exc:
                warning = f"Semantic candidate #{index} skipped: {exc}"
                warnings.append(warning)
                self._emit_warning(context, warning)
                continue

            proposal = submission.proposal
            entry = {
                "proposal_id": proposal.proposal_id,
                "proposal_type": proposal.proposal_type.value,
                "target_id": proposal.target_id,
                "summary": proposal.summary,
                "created": submission.created,
                "deduplicated": submission.deduplicated,
                "confidence": proposal.confidence,
                "risk": proposal.risk,
                "auto_apply_eligible": proposal.auto_apply_eligible,
            }
            writeback_entries.append(entry)
            context.emit(
                "semantic.proposal.created"
                if submission.created
                else "semantic.proposal.deduplicated",
                {
                    "proposalId": proposal.proposal_id,
                    "proposalType": proposal.proposal_type.value,
                    "targetId": proposal.target_id,
                    "summary": proposal.summary,
                    "created": submission.created,
                    "deduplicated": submission.deduplicated,
                    "confidence": proposal.confidence,
                    "risk": proposal.risk,
                    "sessionId": proposal.source_session_id,
                    "runId": proposal.source_run_id,
                },
            )
            if submission.created:
                self._request_operator_review(context, proposal)

        if not writeback_entries and not warnings:
            return PostToolUseResult()
        return PostToolUseResult(
            modified_result=self._inject_writeback(
                parsed_result,
                entries=writeback_entries,
                warnings=warnings,
            )
        )

    @staticmethod
    def _parse_result_payload(result: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _extract_candidates(arguments: dict[str, Any]) -> list[dict[str, Any]]:
        artifacts = arguments.get("artifacts")
        if not isinstance(artifacts, dict):
            return []
        raw_candidates = artifacts.get("semantic_candidates")
        if not isinstance(raw_candidates, list):
            return []
        return [candidate for candidate in raw_candidates if isinstance(candidate, dict)]

    def _prepare_submission(
        self,
        *,
        candidate: dict[str, Any],
        arguments: dict[str, Any],
        parsed_result: dict[str, Any],
        verdict_payload: dict[str, Any],
        context: HookContext,
    ) -> dict[str, Any]:
        raw_type = candidate.get("proposal_type")
        if not isinstance(raw_type, str) or not raw_type.strip():
            raise ValueError("proposal_type is required")
        proposal_type = SemanticProposalType(raw_type)

        payload = self._validate_payload(proposal_type, candidate, arguments)
        summary = candidate.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = self._default_summary(proposal_type, payload)

        target_id = candidate.get("target_id")
        if not isinstance(target_id, str) or not target_id.strip():
            target_id = self._default_target_id(proposal_type, payload)

        return {
            "proposal_type": proposal_type,
            "summary": summary,
            "payload": payload,
            "target_id": target_id,
            "evidence_refs": self._build_evidence_refs(candidate, arguments, parsed_result),
            "confidence": self._resolve_confidence(candidate, verdict_payload),
            "risk": self._resolve_risk(candidate, proposal_type),
            "proposed_by": "agent",
            "auto_apply_eligible": bool(candidate.get("auto_apply_eligible", False)),
            "source_run_id": self._coerce_string(verdict_payload.get("run_id")),
            "source_session_id": context.session_id
            or self._coerce_string(arguments.get("session_id")),
            "source_tool_name": "run_verifier",
        }

    def _validate_payload(
        self,
        proposal_type: SemanticProposalType,
        candidate: dict[str, Any],
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        raw_payload = candidate.get("payload")
        if not isinstance(raw_payload, dict):
            raise ValueError("candidate payload must be an object")

        try:
            match proposal_type:
                case SemanticProposalType.VERIFIED_QUERY:
                    if not self._has_parity_evidence(candidate, raw_payload, arguments):
                        raise ValueError(
                            "verified_query candidate requires dashboard parity evidence"
                        )
                    return VerifiedQuery.model_validate(raw_payload).model_dump(mode="json")
                case SemanticProposalType.GLOSSARY_TERM:
                    return GlossaryTerm.model_validate(raw_payload).model_dump(mode="json")
                case SemanticProposalType.TABLE_TRUST_PATCH:
                    return TableTrust.model_validate(raw_payload).model_dump(mode="json")
                case SemanticProposalType.NEGATIVE_KNOWLEDGE:
                    return NegativeKnowledge.model_validate(raw_payload).model_dump(mode="json")
                case SemanticProposalType.METRIC_ALIAS:
                    metric_id = self._coerce_string(raw_payload.get("metric_id"))
                    alias = self._coerce_string(raw_payload.get("alias"))
                    if metric_id is None or alias is None:
                        raise ValueError("metric_alias payload requires metric_id and alias")
                    return {"metric_id": metric_id, "alias": alias}
                case SemanticProposalType.METRIC_REVIEW_REQUEST:
                    return dict(raw_payload)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc
        raise ValueError(f"unsupported proposal_type: {proposal_type.value}")

    @staticmethod
    def _has_parity_evidence(
        candidate: dict[str, Any],
        payload: dict[str, Any],
        arguments: dict[str, Any],
    ) -> bool:
        if candidate.get("parity_confirmed") is True:
            return True

        verification_evidence = payload.get("verification_evidence")
        if (
            isinstance(verification_evidence, str)
            and "parity" in verification_evidence.casefold()
        ):
            return True

        input_refs = arguments.get("evidence_refs")
        if not isinstance(input_refs, list):
            return False

        for ref in input_refs:
            if not isinstance(ref, dict):
                continue
            artifact_id = ref.get("artifact_id")
            if isinstance(artifact_id, str) and "parity" in artifact_id.casefold():
                return True
            excerpt = ref.get("excerpt")
            if isinstance(excerpt, str) and "parity" in excerpt.casefold():
                return True
            metadata = ref.get("metadata")
            if isinstance(metadata, dict):
                kind = metadata.get("kind")
                if isinstance(kind, str) and "parity" in kind.casefold():
                    return True
        return False

    @staticmethod
    def _build_evidence_refs(
        candidate: dict[str, Any],
        arguments: dict[str, Any],
        parsed_result: dict[str, Any],
    ) -> list[str]:
        refs: list[str] = []

        raw_candidate_refs = candidate.get("evidence_refs")
        if isinstance(raw_candidate_refs, list):
            refs.extend(
                ref.strip()
                for ref in raw_candidate_refs
                if isinstance(ref, str) and ref.strip()
            )

        raw_input_refs = arguments.get("evidence_refs")
        if isinstance(raw_input_refs, list):
            for ref in raw_input_refs:
                if not isinstance(ref, dict):
                    continue
                artifact_id = ref.get("artifact_id")
                if isinstance(artifact_id, str) and artifact_id.strip():
                    refs.append(artifact_id.strip())

        artifact_ref = parsed_result.get("artifact_ref")
        if isinstance(artifact_ref, str) and artifact_ref.strip():
            refs.append(artifact_ref.strip())

        deduped: list[str] = []
        seen: set[str] = set()
        for ref in refs:
            marker = ref.casefold()
            if marker in seen:
                continue
            seen.add(marker)
            deduped.append(ref)
        return deduped

    @staticmethod
    def _resolve_confidence(candidate: dict[str, Any], verdict_payload: dict[str, Any]) -> float:
        raw_confidence = candidate.get("confidence")
        if isinstance(raw_confidence, (int, float)):
            return max(0.0, min(1.0, float(raw_confidence)))

        verdict_confidence = verdict_payload.get("confidence")
        if isinstance(verdict_confidence, dict):
            score = verdict_confidence.get("score")
            if isinstance(score, (int, float)):
                return max(0.0, min(1.0, float(score)))

        verdict_result = str(verdict_payload.get("result") or "").casefold()
        return 0.85 if verdict_result == "pass" else 0.65

    @staticmethod
    def _resolve_risk(
        candidate: dict[str, Any],
        proposal_type: SemanticProposalType,
    ) -> str:
        raw_risk = candidate.get("risk")
        if isinstance(raw_risk, str) and raw_risk in {"low", "medium", "high"}:
            return raw_risk

        defaults = {
            SemanticProposalType.METRIC_ALIAS: "low",
            SemanticProposalType.GLOSSARY_TERM: "medium",
            SemanticProposalType.VERIFIED_QUERY: "high",
            SemanticProposalType.NEGATIVE_KNOWLEDGE: "high",
            SemanticProposalType.TABLE_TRUST_PATCH: "high",
            SemanticProposalType.METRIC_REVIEW_REQUEST: "medium",
        }
        return defaults[proposal_type]

    @staticmethod
    def _default_summary(proposal_type: SemanticProposalType, payload: dict[str, Any]) -> str:
        if proposal_type is SemanticProposalType.VERIFIED_QUERY:
            vq_id = str(payload.get("vq_id") or "verified-query")
            metric_id = payload.get("metric_id")
            if isinstance(metric_id, str) and metric_id.strip():
                return f"Verified query candidate for {metric_id.strip()} ({vq_id})"
            return f"Verified query candidate {vq_id}"
        if proposal_type is SemanticProposalType.GLOSSARY_TERM:
            return f"Glossary term candidate for {payload['canonical_form']}"
        if proposal_type is SemanticProposalType.TABLE_TRUST_PATCH:
            return f"Table trust patch for {payload['fqtn']}"
        if proposal_type is SemanticProposalType.NEGATIVE_KNOWLEDGE:
            return f"Negative knowledge for {payload['topic']}"
        if proposal_type is SemanticProposalType.METRIC_ALIAS:
            return f"Metric alias '{payload['alias']}' for {payload['metric_id']}"
        return "Metric review request"

    @staticmethod
    def _default_target_id(
        proposal_type: SemanticProposalType,
        payload: dict[str, Any],
    ) -> str | None:
        if proposal_type is SemanticProposalType.VERIFIED_QUERY:
            metric_id = payload.get("metric_id")
            if isinstance(metric_id, str) and metric_id.strip():
                return metric_id.strip()
            vq_id = payload.get("vq_id")
            return vq_id.strip() if isinstance(vq_id, str) and vq_id.strip() else None
        if proposal_type is SemanticProposalType.GLOSSARY_TERM:
            return str(payload["term_id"])
        if proposal_type is SemanticProposalType.TABLE_TRUST_PATCH:
            return str(payload["fqtn"])
        if proposal_type is SemanticProposalType.NEGATIVE_KNOWLEDGE:
            return str(payload["topic"])
        if proposal_type is SemanticProposalType.METRIC_ALIAS:
            return str(payload["metric_id"])
        return None

    @staticmethod
    def _inject_writeback(
        parsed_result: dict[str, Any],
        *,
        entries: list[dict[str, Any]],
        warnings: list[str],
    ) -> str:
        updated = dict(parsed_result)
        if entries:
            updated["semantic_writeback"] = entries
        if warnings:
            updated["semantic_writeback_warnings"] = warnings
        return json.dumps(updated, ensure_ascii=False)

    @staticmethod
    def _emit_warning(context: HookContext, message: str) -> None:
        context.emit(
            "harness.warning",
            {
                "type": "semantic_writeback",
                "severity": "medium",
                "message": message,
            },
        )

    @staticmethod
    def _request_operator_review(context: HookContext, proposal: Any) -> None:
        if context.approval_store is None or context.session_id is None:
            return

        runtime_context = get_tool_runtime_context()
        run_id = runtime_context.run_id if runtime_context is not None else proposal.source_run_id
        surface = runtime_context.surface if runtime_context is not None else "agent"
        approval = create_semantic_proposal_approval(
            approval_store=context.approval_store,
            proposal=proposal,
            session_id=context.session_id,
            run_id=run_id,
            surface=surface,
        )
        context.emit("approval.requested", serialize_approval(approval))

    @staticmethod
    def _coerce_string(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None
