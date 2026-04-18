"""Plain-text renderers for stakeholder delivery surfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def render_delivery_build(result: Mapping[str, Any]) -> str:
    """Render a compact summary for delivery-pack planning."""

    audiences = ", ".join(str(item) for item in result.get("audiences", [])) or "-"
    artifact_ids = ", ".join(str(item) for item in result.get("artifact_ids", [])) or "-"
    return "\n".join(
        [
            f"Delivery pack: {result['pack_id']}",
            (
                "Status: "
                f"{result['status']} | Artifacts: {result['artifacts']} | "
                f"Legacy items: {result['items']} | Version: {result['new_version']}"
            ),
            f"Audiences: {audiences}",
            f"Artifact ids: {artifact_ids}",
        ]
    )


def render_delivery_render(result: Mapping[str, Any]) -> str:
    """Render one artifact materialization result."""

    flagged_claims = result.get("flagged_claims", [])
    flagged_count = len(flagged_claims) if isinstance(flagged_claims, Sequence) else 0
    lines = [
        f"Rendered artifact: {result['artifact_id']}",
        (
            "Pack: "
            f"{result['pack_id']} | Status: {result['pack_status']} | "
            f"Version: {result['new_version']}"
        ),
        f"Output: {result['output_path']}",
        (
            "Format: "
            f"{result['format']} | Verifier: {result['verifier_status']} | "
            f"Flagged claims: {flagged_count}"
        ),
    ]
    renderer_mode = result.get("renderer_mode")
    if renderer_mode:
        renderer_line = f"Renderer: {renderer_mode}"
        renderer_model = result.get("renderer_model")
        if renderer_model:
            renderer_line += f" | Model: {renderer_model}"
        lines.append(renderer_line)
    verifier_report_id = result.get("verifier_report_id")
    if verifier_report_id:
        lines.append(f"Verifier report: {verifier_report_id}")
    return "\n".join(lines)


def render_delivery_dispatch(result: Mapping[str, Any]) -> str:
    """Render channel-level dispatch status."""

    lines = [
        f"Delivery dispatch: {result['pack_id']}",
        (
            "Status: "
            f"{result['dispatch_status']} | Pack: {result['pack_status']} | "
            f"Version: {result['new_version']}"
        ),
        (
            "Counts: "
            f"sent={result['sent']} blocked={result['blocked']} "
            f"failed={result['failed']} duplicates={result['duplicates']}"
        ),
    ]
    log_path = result.get("log_path")
    if log_path:
        lines.append(f"Log: {log_path}")
    receipts = result.get("receipts", [])
    if isinstance(receipts, Sequence) and receipts:
        lines.append("Receipts:")
        lines.extend(
            _render_receipt(receipt)
            for receipt in receipts
            if isinstance(receipt, Mapping)
        )
    return "\n".join(lines)


def render_delivery_log(result: Mapping[str, Any]) -> str:
    """Render persisted dispatch-log records."""

    lines = [
        f"Delivery log: {result['task_id']}",
        f"Returned: {result.get('returned', 0)}",
    ]
    pack_id = result.get("pack_id")
    if pack_id:
        lines.append(f"Pack: {pack_id}")
    log_path = result.get("log_path")
    if log_path:
        lines.append(f"Log: {log_path}")
    summary = result.get("summary")
    if isinstance(summary, Mapping):
        lines.extend(_render_log_summary(summary))
    records = result.get("records", [])
    if isinstance(records, Sequence) and records:
        lines.append("Entries:")
        lines.extend(
            _render_log_record(record)
            for record in records
            if isinstance(record, Mapping)
        )
    return "\n".join(lines)


def _render_receipt(receipt: Mapping[str, Any]) -> str:
    channel = receipt.get("channel", "-")
    status = receipt.get("status", "-")
    reason = receipt.get("reason")
    adapter = receipt.get("adapter_name")
    parts = [f"- {receipt.get('artifact_id', '-')} -> {channel} | {status}"]
    if adapter:
        parts.append(f"adapter={adapter}")
    if reason:
        parts.append(f"reason={reason}")
    return " | ".join(parts)


def _render_log_record(record: Mapping[str, Any]) -> str:
    parts = [
        f"- {record.get('recorded_at', '-')}",
        f"{record.get('artifact_id', '-')} -> {record.get('channel', '-')}",
        str(record.get("status", "-")),
    ]
    adapter = record.get("adapter_name")
    reason = record.get("reason")
    if adapter:
        parts.append(f"adapter={adapter}")
    if reason:
        parts.append(f"reason={reason}")
    return " | ".join(parts)


def _render_log_summary(summary: Mapping[str, Any]) -> list[str]:
    return [
        (
            "Summary: "
            f"pack={summary.get('pack_id', '-')} status={summary.get('pack_status', '-')} "
            f"artifacts={summary.get('artifact_count', 0)} "
            f"rendered={summary.get('rendered_count', 0)}"
        ),
        (
            "Counts: "
            f"sent={summary.get('sent', 0)} blocked={summary.get('blocked', 0)} "
            f"failed={summary.get('failed', 0)} duplicates={summary.get('duplicate', 0)} "
            f"dry_runs={summary.get('dry_run', 0)}"
        ),
        f"Last attempt: {summary.get('last_attempt', '-')}",
    ]


def parse_delivery_context(values: Sequence[str]) -> dict[str, str]:
    """Parse repeated KEY=VALUE CLI arguments."""

    context: dict[str, str] = {}
    for raw_value in values:
        key, separator, value = str(raw_value).partition("=")
        if not separator or not key.strip():
            raise ValueError(f"Invalid context entry: {raw_value}")
        context[key.strip()] = value
    return context


def load_delivery_analysis(
    *,
    analysis_json: str | None,
    analysis_file: str | None,
) -> dict[str, Any] | str:
    """Load render analysis payload from inline JSON or a file."""

    if analysis_json and analysis_file:
        raise ValueError("Use either --analysis-json or --analysis-file, not both")
    if analysis_json:
        return _parse_analysis_payload(analysis_json)
    if not analysis_file:
        raise ValueError("One of --analysis-json or --analysis-file is required")
    return _parse_analysis_payload(Path(analysis_file).read_text(encoding="utf-8"))


def _parse_analysis_payload(raw_value: str) -> dict[str, Any] | str:
    stripped = raw_value.strip()
    if not stripped:
        raise ValueError("Analysis payload cannot be empty")
    import json

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return raw_value
    if isinstance(parsed, dict):
        return parsed
    return raw_value
