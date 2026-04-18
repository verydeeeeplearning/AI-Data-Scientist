"""Governance tools for policy and lineage inspection."""

from __future__ import annotations

import json

from ds_agent.application.services.lineage_capture_service import get_lineage_service
from ds_agent.application.services.policy_evaluator import get_policy_evaluator
from ds_agent.tools.registry import tool


@tool(
    name="policy_check",
    description=(
        "Evaluate an action against the policy approval matrix and optionally "
        "record a resolved approval for standing-approval promotion."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "Action or tool name to evaluate."},
            "data_sensitivity": {
                "type": "string",
                "enum": ["public", "internal", "pii", "restricted"],
                "default": "internal",
            },
            "environment": {
                "type": "string",
                "default": "dev",
                "description": "Execution environment such as dev/staging/prod.",
            },
            "confidence": {
                "type": "number",
                "default": 1.0,
                "description": "Confidence score used for deployment-style approvals.",
            },
            "record_approval": {
                "type": "boolean",
                "default": False,
                "description": "Whether to record an explicit approval for standing approval tracking.",
            },
            "approved_by": {
                "type": "string",
                "default": "user",
                "description": "Actor label stored when record_approval=true.",
            },
        },
        "required": ["action"],
    },
    timeout=10,
)
def policy_check(
    action: str,
    data_sensitivity: str = "internal",
    environment: str = "dev",
    confidence: float = 1.0,
    record_approval: bool = False,
    approved_by: str = "user",
) -> str:
    evaluator = get_policy_evaluator()
    decision = evaluator.evaluate(
        action,
        sensitivity=data_sensitivity,
        env=environment,
        confidence=confidence,
    )
    approval_payload: dict[str, object] = {}
    if record_approval:
        standing = evaluator.record_approval(
            action,
            approved_by=approved_by,
            sensitivity=data_sensitivity,
            env=environment,
        )
        approval_payload = {
            "standing_count": standing.count,
            "promoted": standing.promoted,
        }

    return json.dumps(
        {
            "action": action,
            "data_sensitivity": data_sensitivity,
            "environment": environment,
            "confidence": confidence,
            "decision": decision.decision.value,
            "reason": decision.reason,
            **approval_payload,
        }
    )


@tool(
    name="lineage_capture",
    description=(
        "Capture an explicit decision memo into lineage or trace an existing "
        "record back through dataset, feature, and model ancestry."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["decision", "trace"],
                "description": "Whether to capture a decision memo or trace a record.",
            },
            "record_id": {
                "type": "string",
                "description": "Existing lineage record id for trace action.",
            },
            "what": {"type": "string", "description": "Decision subject."},
            "why": {"type": "string", "description": "Decision rationale."},
            "alternatives_considered": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Alternatives that were considered.",
            },
            "parent_id": {
                "type": "string",
                "description": "Optional parent lineage id for decision action.",
            },
            "session_id": {
                "type": "string",
                "description": "Optional session id to associate with the decision.",
            },
        },
        "required": ["action"],
    },
    timeout=10,
)
def lineage_capture(
    action: str,
    record_id: str | None = None,
    what: str | None = None,
    why: str | None = None,
    alternatives_considered: list[str] | None = None,
    parent_id: str | None = None,
    session_id: str | None = None,
) -> str:
    service = get_lineage_service()
    if action == "trace":
        if not record_id:
            return json.dumps({"error": "record_id is required for trace"})
        trace = service.trace(record_id)
        return json.dumps(
            [
                {
                    "id": record.id,
                    "type": record.record_type.value,
                    "parent_id": record.parent_id,
                    "session_id": record.session_id,
                    "content": record.content,
                }
                for record in trace
            ],
            default=str,
        )

    if action == "decision":
        if not what or not why:
            return json.dumps({"error": "what and why are required for decision capture"})
        record = service.capture_decision(
            what=what,
            why=why,
            alternatives_considered=alternatives_considered,
            session_id=session_id,
            parent_id=parent_id,
        )
        return json.dumps(
            {
                "id": record.id,
                "type": record.record_type.value,
                "parent_id": record.parent_id,
                "session_id": record.session_id,
            }
        )

    return json.dumps({"error": f"Unsupported action: {action}"})
