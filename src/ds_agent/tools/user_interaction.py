"""User interaction tool backed by the persisted approval bus."""

from __future__ import annotations

import json

from ds_agent.domain.entities.approval import ApprovalStatus
from ds_agent.runtime.approval_payloads import serialize_approval
from ds_agent.runtime.tool_runtime_context import get_tool_runtime_context
from ds_agent.tools.registry import tool


@tool(
    name="ask_user",
    description=(
        "Ask the user a question and wait for their response. "
        "Use for clarification, approval requests, or parameter confirmation."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask the user",
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of choices for the user to select from",
            },
            "default": {
                "type": "string",
                "description": "Default answer if user doesn't respond",
            },
        },
        "required": ["question"],
    },
    timeout=300,
    prompt=(
        "Asks the user a question and waits for their response.\n\n"
        "## When to Use\n"
        "- Ambiguous task requirements that need clarification\n"
        "- Confirmation before irreversible actions (in supervised mode)\n"
        "- Choosing between multiple valid approaches\n\n"
        "## Do NOT Use When\n"
        "- You can make a reasonable default decision\n"
        "- In auto mode for routine decisions"
    ),
)
async def ask_user(
    question: str,
    options: list[str] | None = None,
    default: str | None = None,
) -> str:
    context = get_tool_runtime_context()
    if (
        context is None
        or context.approval_store is None
        or not context.session_id
        or context.surface == "cli"
    ):
        return json.dumps(
            {
                "type": "user_input_required",
                "question": question,
                "options": options,
                "default": default,
                "note": "Approval bus is not active for this surface.",
            }
        )

    approval = context.approval_store.create(
        session_id=context.session_id,
        run_id=context.run_id,
        surface=context.surface,
        question=question,
        options=options,
        default=default,
    )

    if callable(context.emit_event):
        context.emit_event("approval.requested", serialize_approval(approval))

    resolved = await context.approval_store.wait_for_resolution(approval.approval_id)
    payload = serialize_approval(resolved)

    if callable(context.emit_event):
        context.emit_event("approval.resolved", payload)

    if resolved.status == ApprovalStatus.REJECTED:
        payload["error"] = "Approval rejected by user"
        return json.dumps(payload)

    payload["type"] = "user_input"
    payload["response"] = resolved.response or default or ""
    return json.dumps(payload)
