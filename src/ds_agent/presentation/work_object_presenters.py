"""Plain-text renderers for WorkObject CLI/operator surfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ds_agent.application.dtos.work_object import WorkObjectListItemDTO, WorkObjectViewDTO
from ds_agent.domain.entities.integration_event import IntegrationEvent


def render_work_object_list(items: list[WorkObjectListItemDTO]) -> str:
    """Render a compact list of work objects."""

    if not items:
        return "Work objects:\n  - none"
    lines = ["Work objects:"]
    for item in items:
        lines.append(
            "  - "
            f"{item.work_object_id} | {item.phase} | {item.title} | "
            f"task={item.task_contract_id} | refs={item.reference_count} | "
            f"follow_up={item.follow_up_count}"
        )
    return "\n".join(lines)


def render_work_object_view(view: WorkObjectViewDTO) -> str:
    """Render one detailed work object view with timeline context."""

    work_object = view.work_object
    lines = [
        f"Work object: {work_object.work_object_id}",
        f"Title: {work_object.title}",
        (
            "Phase: "
            f"{work_object.execution.current_phase.value} | "
            f"Task contract: {work_object.execution.task_contract_id}"
        ),
        f"Source: {work_object.request.source.value}",
        (
            "Requestor: "
            f"{work_object.request.requestor_display} ({work_object.request.requestor_id})"
        ),
        f"Channel: {work_object.request.channel or '-'}",
        f"Original request: {work_object.request.original_text}",
        f"Runs: {', '.join(work_object.execution.run_ids) or '-'}",
        f"Tags: {', '.join(work_object.tags) or '-'}",
        (
            "References: "
            f"request={_render_reference_identity(work_object.request.external_ref)} | "
            f"documentation={len(work_object.documentation.references)} | "
            f"follow_up={len(work_object.follow_up.actions)}"
        ),
    ]
    if work_object.metadata.get("pending_policy_actions"):
        lines.append(
            f"Pending policy actions: {len(work_object.metadata['pending_policy_actions'])}"
        )
    if work_object.request.metadata:
        lines.append("Request metadata:")
        lines.extend(
            f"  - {key}: {_render_scalar(value)}"
            for key, value in sorted(work_object.request.metadata.items())
        )
    if work_object.documentation.references:
        lines.append("Documentation refs:")
        lines.extend(
            f"  - {_render_reference_identity(reference)}"
            for reference in work_object.documentation.references
        )
    if work_object.follow_up.actions:
        lines.append("Follow-up actions:")
        lines.extend(
            "  - "
            f"{action.action_type} | {action.status.value} | "
            f"{action.description} | {_render_reference_identity(action.external_ref)}"
            for action in work_object.follow_up.actions
        )
    if view.timeline:
        lines.append(render_work_object_timeline(view.timeline))
    return "\n".join(lines)


def render_work_object_timeline(events: Sequence[IntegrationEvent]) -> str:
    """Render a standalone timeline view."""

    if not events:
        return "Timeline:\n  - none"
    lines = ["Timeline:"]
    for event in events:
        line = (
            "  - "
            f"{event.started_at.isoformat()} | {event.status.value} | "
            f"{event.system}.{event.action} | {_render_reference_identity(event.external_ref)}"
        )
        if event.error_code:
            line += f" | error={event.error_code}"
        lines.append(line)
    return "\n".join(lines)


def parse_work_metadata(values: Sequence[str]) -> dict[str, str]:
    """Parse repeated KEY=VALUE CLI arguments for work-object metadata."""

    context: dict[str, str] = {}
    for raw_value in values:
        key, separator, value = str(raw_value).partition("=")
        if not separator or not key.strip():
            raise ValueError(f"Invalid metadata entry: {raw_value}")
        context[key.strip()] = value
    return context


def _render_reference_identity(reference: object) -> str:
    if reference is None:
        return "-"
    system = getattr(reference, "system", None)
    resource_type = getattr(reference, "resource_type", None)
    resource_id = getattr(reference, "resource_id", None)
    if system is None or resource_type is None or resource_id is None:
        return str(reference)
    return f"{system}:{resource_type}:{resource_id}"


def _render_scalar(value: object) -> str:
    if isinstance(value, Mapping):
        return ", ".join(f"{key}={_render_scalar(item)}" for key, item in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return ", ".join(_render_scalar(item) for item in value)
    return str(value)
