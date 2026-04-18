"""Plain-text renderers for verifier shadow comparison review surfaces."""

from __future__ import annotations

from collections.abc import Sequence

from ds_agent.domain.entities.shadow_comparison import (
    ShadowComparisonItem,
    ShadowComparisonRecord,
)


def pick_effective_shadow_comparison(
    comparisons: Sequence[ShadowComparisonRecord],
) -> ShadowComparisonRecord | None:
    """Pick the latest shadow comparison record."""

    if not comparisons:
        return None
    return max(comparisons, key=lambda record: (record.created_at, record.comparison_id))


def render_shadow_comparison_snapshot(record: ShadowComparisonRecord) -> str:
    """Render a compact shadow-diff snapshot for lists and summaries."""

    return (
        f"shadow={round(record.match_rate * 100)}% "
        f"| mismatches={record.mismatch_count}/{record.applicable_count}"
    )


def render_shadow_comparison_report(
    record: ShadowComparisonRecord,
    *,
    compact: bool = False,
) -> str:
    """Render a detailed multiline shadow review for CLI and Telegram."""

    mismatches = _mismatches(record)
    lines = [
        f"Shadow comparison: {record.comparison_id}",
        f"Verdict: {record.verdict_id} | Task: {record.task_id}",
        (
            "Match: "
            f"{round(record.match_rate * 100)}% | mismatches={record.mismatch_count}"
            f"/{record.applicable_count}"
        ),
    ]
    if record.run_id or record.session_id:
        lines.append(
            "Run: "
            f"{record.run_id or '-'} | session={record.session_id or '-'}"
        )
    if mismatches:
        lines.append("Mismatches:")
        max_items = 2 if compact else 5
        lines.extend(_render_item_line(item) for item in mismatches[:max_items])
        if len(mismatches) > max_items:
            lines.append(f"  - ... +{len(mismatches) - max_items} more")
    else:
        lines.append("Mismatches: none")
    return "\n".join(lines)


def _mismatches(record: ShadowComparisonRecord) -> list[ShadowComparisonItem]:
    return [item for item in record.items if item.applicable and not item.matches]


def _render_item_line(item: ShadowComparisonItem) -> str:
    detail = item.note or f"{item.legacy_state} -> {item.verifier_state}"
    return (
        f"  - [{item.mismatch_kind}] {item.comparison_key}: "
        f"legacy={item.legacy_state}, verifier={item.verifier_state} | {detail}"
    )
