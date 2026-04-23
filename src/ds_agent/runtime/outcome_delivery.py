"""Run outcome and artifact auto-delivery policy.

Decides which run outcomes deserve operator notification and which
artifacts should be auto-sent.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ds_agent.runtime.delivery_policy_store import JsonDeliveryPolicyStore


@dataclass(frozen=True, slots=True)
class OutcomeDeliverable:
    """One deliverable item from a run outcome."""

    kind: str  # "summary", "file", "hint"
    text: str | None = None
    file_path: str | None = None
    caption: str | None = None


def select_outcome_deliverables(
    run_status: str,
    run_message: str,
    result_preview: str | None,
    error: str | None,
    project_id: str | None,
    project_files: list[dict],
    policy_store: JsonDeliveryPolicyStore,
    *,
    max_artifacts: int = 3,
) -> list[OutcomeDeliverable]:
    """Select deliverables for a completed run.

    Returns a list of items to send.  Caller is responsible for actual
    delivery via Telegram or other channel.
    """
    deliverables: list[OutcomeDeliverable] = []

    if run_status == "failed":
        summary = f"Run failed: {error or 'unknown error'}"
        if result_preview:
            summary += f"\nLast output: {result_preview[:200]}"
        deliverables.append(OutcomeDeliverable(kind="summary", text=summary))
        return deliverables

    if run_status == "cancelled":
        deliverables.append(OutcomeDeliverable(kind="summary", text="Run was cancelled."))
        return deliverables

    if run_status == "succeeded":
        summary = f"Run completed: {run_message[:120]}"
        if result_preview:
            summary += f"\nResult: {result_preview[:200]}"
        deliverables.append(OutcomeDeliverable(kind="summary", text=summary))

        file_count = 0
        for entry in project_files:
            if file_count >= max_artifacts:
                remaining = len(project_files) - file_count
                deliverables.append(
                    OutcomeDeliverable(
                        kind="hint",
                        text=f"+ {remaining} more files. Use /artifacts {project_id}",
                    )
                )
                break
            file_path = entry.get("path", "")
            full_path = entry.get("full_path", file_path)
            try:
                size = Path(full_path).stat().st_size if Path(full_path).exists() else 0
            except OSError:
                size = 0
            if policy_store.should_auto_send_file(file_path, size):
                deliverables.append(
                    OutcomeDeliverable(
                        kind="file",
                        file_path=full_path,
                        caption=f"{project_id or 'project'} | {file_path}",
                    )
                )
                file_count += 1

        if project_id and project_files and file_count == 0:
            deliverables.append(
                OutcomeDeliverable(
                    kind="hint",
                    text=f"Artifacts are available. Use /artifacts {project_id}",
                )
            )

        return deliverables

    deliverables.append(OutcomeDeliverable(kind="summary", text=f"Run ended: {run_status}"))
    return deliverables
