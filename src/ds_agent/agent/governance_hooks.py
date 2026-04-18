"""Governance hooks for policy approval, lineage capture, and PII protection."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ds_agent.agent.hooks import (
    HookAction,
    HookContext,
    PostToolUseResult,
    PreToolUseResult,
    ToolHook,
)
from ds_agent.application.services.lineage_capture_service import (
    LineageCaptureService,
    current_environment_info,
    get_lineage_service,
    infer_seed_from_code,
)
from ds_agent.application.services.policy_evaluator import PolicyEvaluator, get_policy_evaluator
from ds_agent.domain.entities.approval_policy import DataSensitivity, PolicyDecisionType
from ds_agent.domain.entities.lineage import LineageRecord, LineageRecordType
from ds_agent.infrastructure.pii_detector import PIIDetector

_METRIC_LINE_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9_ ]*?)\s*[=:]\s*([\d.]+)%?\s*$",
    re.MULTILINE,
)


class PolicyApprovalHook(ToolHook):
    """Applies policy-based approvals after legacy permission checks."""

    name = "policy_approval"
    priority = 11

    def __init__(
        self,
        evaluator: PolicyEvaluator | None = None,
        pii_detector: PIIDetector | None = None,
    ) -> None:
        self._evaluator = evaluator or get_policy_evaluator()
        self._pii_detector = pii_detector or PIIDetector()

    async def pre_tool_use(
        self,
        tool_name: str,
        arguments: dict,
        context: HookContext,
    ) -> PreToolUseResult:
        sensitivity = self._infer_sensitivity(tool_name, arguments)
        confidence = _coerce_confidence(arguments.get("confidence"))
        decision = self._evaluator.evaluate(
            tool_name,
            sensitivity=sensitivity,
            env=context.environment,
            confidence=confidence,
        )
        context.emit(
            "policy.decision",
            {
                "tool": tool_name,
                "decision": decision.decision.value,
                "reason": decision.reason,
                "sensitivity": sensitivity.value,
                "environment": context.environment,
            },
        )
        if decision.decision == PolicyDecisionType.AUTO or context.user_approved:
            return PreToolUseResult()
        if decision.decision == PolicyDecisionType.DENY:
            return PreToolUseResult(action=HookAction.DENY, deny_reason=decision.reason)

        approval_id = self._request_approval(
            tool_name=tool_name,
            sensitivity=sensitivity,
            context=context,
        )
        reason = f"{decision.decision.value} required: {decision.reason}"
        if approval_id is not None:
            reason += f" (approval_id={approval_id})"
        return PreToolUseResult(action=HookAction.DENY, deny_reason=reason)

    def _infer_sensitivity(self, tool_name: str, arguments: dict) -> DataSensitivity:
        raw = arguments.get("data_sensitivity")
        if isinstance(raw, str):
            return DataSensitivity(raw)
        if tool_name == "file_read":
            return DataSensitivity.PUBLIC
        return self._pii_detector.classify_sensitivity(arguments)

    @staticmethod
    def _request_approval(
        *,
        tool_name: str,
        sensitivity: DataSensitivity,
        context: HookContext,
    ) -> str | None:
        if context.approval_store is None or context.session_id is None:
            return None
        approval = context.approval_store.create(
            session_id=context.session_id,
            run_id=None,
            surface="agent",
            question=(
                f"Approve tool '{tool_name}' for {sensitivity.value} data in {context.environment}?"
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
            },
        )
        return approval_id if isinstance(approval_id, str) else None


class PIIRedactionHook(ToolHook):
    """Detect and optionally redact PII from tool inputs and outputs."""

    name = "pii_redaction"
    priority = 12

    def __init__(self, *, auto_mask: bool = True, detector: PIIDetector | None = None) -> None:
        self._auto_mask = auto_mask
        self._detector = detector or PIIDetector()

    async def pre_tool_use(
        self, tool_name: str, arguments: dict, context: HookContext
    ) -> PreToolUseResult:
        matches = self._detector.detect(arguments)
        if not matches:
            return PreToolUseResult()
        context.emit(
            "harness.warning",
            {
                "type": "pii_detected",
                "severity": "high",
                "message": f"PII detected before {tool_name}",
                "details": [match.location for match in matches],
            },
        )
        if not self._auto_mask:
            return PreToolUseResult()
        return PreToolUseResult(
            action=HookAction.MODIFY,
            modified_arguments=self._detector.redact(arguments),
        )

    async def post_tool_use(
        self, tool_name: str, arguments: dict, result: str, is_error: bool, context: HookContext
    ) -> PostToolUseResult:
        redacted_result = self._detector.redact(result)
        file_redacted = False
        if tool_name == "generate_report" and isinstance(arguments.get("output_path"), str):
            output_path = Path(arguments["output_path"])
            if output_path.exists():
                content = output_path.read_text(encoding="utf-8")
                redacted_content = self._detector.redact(content)
                if redacted_content != content:
                    output_path.write_text(redacted_content, encoding="utf-8")
                    file_redacted = True

        if redacted_result == result and not file_redacted:
            return PostToolUseResult()

        context.emit(
            "harness.warning",
            {
                "type": "pii_redacted",
                "severity": "medium",
                "message": f"PII redacted from {tool_name}",
            },
        )
        suffix = "\n\n---\n**PII Redaction**: sensitive values were masked."
        return PostToolUseResult(modified_result=str(redacted_result) + suffix)


class LineageCaptureHook(ToolHook):
    """Automatically capture dataset, feature, model, and evaluation lineage."""

    name = "lineage_capture"
    priority = 51

    def __init__(self, service: LineageCaptureService | None = None) -> None:
        self._service = service or get_lineage_service()

    async def post_tool_use(
        self, tool_name: str, arguments: dict, result: str, is_error: bool, context: HookContext
    ) -> PostToolUseResult:
        if is_error:
            return PostToolUseResult()

        record = None
        session_id = context.session_id
        if tool_name == "data_loader" and isinstance(arguments.get("file_path"), str):
            payload = _parse_json(result)
            shape = payload.get("shape", [])
            row_count = int(shape[0]) if isinstance(shape, list) and shape else 0
            schema = payload.get("columns", payload.get("dtypes", {}))
            record = self._service.capture_dataset(
                arguments["file_path"],
                schema=schema if isinstance(schema, (list, dict)) else [],
                row_count=row_count,
                session_id=session_id,
            )
        elif tool_name == "feature_engineer":
            parent = self._latest_parent(session_id, preferred=LineageRecordType.FEATURE)
            record = self._service.capture_feature(
                str(arguments.get("code", "")),
                params={
                    "input_path": arguments.get("input_path"),
                    "output_path": arguments.get("output_path"),
                    "target_column": arguments.get("target_column"),
                },
                input_data_id=None if parent is None else parent.id,
                session_id=session_id,
            )
        elif tool_name == "train_model":
            parent = self._latest_parent(session_id, preferred=LineageRecordType.FEATURE)
            record = self._service.capture_model(
                hyperparams=_extract_hyperparams(arguments),
                seed=infer_seed_from_code(str(arguments.get("code", ""))),
                env_info=current_environment_info(),
                feature_id=None if parent is None else parent.id,
                session_id=session_id,
                model_type=str(arguments.get("model_type", "")) or None,
                model_path=str(arguments.get("model_output_path", "")) or None,
            )
        elif tool_name == "evaluate_model":
            model_record = None
            if session_id is not None:
                model_record = self._service.latest_for_session(
                    session_id,
                    record_type=LineageRecordType.MODEL,
                )
            holdout = None
            if session_id is not None:
                holdout = self._service.latest_for_session(
                    session_id,
                    record_type=LineageRecordType.DATASET,
                )
            record = self._service.capture_evaluation(
                metrics={k: v for k, v in _parse_metrics(result).items()},
                holdout_data_id=None if holdout is None else holdout.id,
                model_id=None if model_record is None else model_record.id,
                session_id=session_id,
            )

        if record is None:
            return PostToolUseResult()

        context.emit(
            "lineage.recorded",
            {
                "id": record.id,
                "type": record.record_type.value,
                "parentId": record.parent_id,
                "sessionId": record.session_id,
            },
        )
        return PostToolUseResult()

    def _latest_parent(
        self,
        session_id: str | None,
        *,
        preferred: LineageRecordType,
    ) -> LineageRecord | None:
        if session_id is None:
            return None
        parent = self._service.latest_for_session(session_id, record_type=preferred)
        if parent is not None:
            return parent
        return self._service.latest_for_session(session_id, record_type=LineageRecordType.DATASET)


def _coerce_confidence(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 1.0


def _parse_json(text: str) -> dict:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_hyperparams(arguments: dict) -> dict[str, object]:
    raw = arguments.get("hyperparameters")
    if isinstance(raw, dict):
        return {str(key): value for key, value in raw.items()}
    return {}


def _parse_metrics(text: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    payload = _parse_json(text)
    raw_metrics = payload.get("metrics")
    if isinstance(raw_metrics, dict):
        for key, value in raw_metrics.items():
            if isinstance(value, (int, float)):
                metrics[str(key)] = float(value)
    for match in _METRIC_LINE_RE.finditer(text):
        key = match.group(1).strip().lower().replace(" ", "_")
        value = float(match.group(2))
        if 1.0 < value <= 100.0:
            value /= 100.0
        metrics[key] = value
    return metrics
