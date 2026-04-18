"""Plain-text renderers for verifier verdict surfaces."""

from __future__ import annotations

from collections.abc import Sequence

from ds_agent.domain.entities.review_verdict import Issue, ReviewVerdict


def pick_effective_review_verdict(
    review_verdicts: Sequence[ReviewVerdict],
) -> ReviewVerdict | None:
    """Pick the latest orchestrator verdict, falling back to the latest overall verdict."""

    if not review_verdicts:
        return None
    preferred = [verdict for verdict in review_verdicts if verdict.category == "orchestrator"]
    candidates = preferred or list(review_verdicts)
    return max(candidates, key=lambda verdict: (verdict.created_at, verdict.verdict_id))


def render_verdict_snapshot(verdict: ReviewVerdict) -> str:
    """Render one compact verifier snapshot for lists and summaries."""

    confidence = verdict.confidence.grade if verdict.confidence is not None else "unknown"
    blockers = len(_blocking_issues(verdict))
    judge_mode = _judge_mode(verdict)
    shadow_rate = _shadow_match_rate(verdict)
    base = f"{verdict.result or 'fail'} | confidence={confidence} | blockers={blockers}"
    if judge_mode:
        base = f"{base} | judge={judge_mode}"
    if shadow_rate is not None:
        base = f"{base} | shadow={round(shadow_rate * 100)}%"
    return base


def render_verdict_report(verdict: ReviewVerdict, *, compact: bool = False) -> str:
    """Render a detailed multiline summary for CLI and Telegram surfaces."""

    blocking_issues = _blocking_issues(verdict)
    confidence_grade = verdict.confidence.grade if verdict.confidence is not None else "unknown"
    confidence_score = (
        f"{verdict.confidence.score:.2f}" if verdict.confidence is not None else "-"
    )
    judge_mode = _judge_mode(verdict) or "-"
    lines = [
        f"Review verdict: {verdict.verdict_id}",
        f"Task: {verdict.task_id}",
        (
            "Result: "
            f"{verdict.result or 'fail'} | confidence={confidence_grade} ({confidence_score}) "
            f"| blockers={len(blocking_issues)} | judge={judge_mode}"
        ),
        f"Category: {verdict.category} | Reviewer: {verdict.reviewer}",
    ]
    if verdict.summary:
        lines.append(f"Summary: {verdict.summary}")
    if verdict.layers:
        layer_statuses = ", ".join(
            f"{layer.layer}={layer.overall or 'pass'}" for layer in verdict.layers
        )
        lines.append(f"Layers: {layer_statuses}")
    shadow_rate = _shadow_match_rate(verdict)
    shadow_mismatches = _shadow_mismatch_count(verdict)
    if shadow_rate is not None and shadow_mismatches is not None:
        lines.append(
            "Shadow: "
            f"{round(shadow_rate * 100)}% match | mismatches={shadow_mismatches}"
        )
    if blocking_issues:
        lines.append("Blocking issues:")
        max_items = 2 if compact else 4
        lines.extend(_render_issue_line(issue) for issue in blocking_issues[:max_items])
        if len(blocking_issues) > max_items:
            lines.append(f"  - ... +{len(blocking_issues) - max_items} more")
    if not compact and verdict.recommended_actions:
        lines.append("Recommended actions:")
        lines.extend(
            f"  - [{action.priority}] {action.title}" for action in verdict.recommended_actions[:3]
        )
        if len(verdict.recommended_actions) > 3:
            lines.append(f"  - ... +{len(verdict.recommended_actions) - 3} more")
    return "\n".join(lines)


def _blocking_issues(verdict: ReviewVerdict) -> list[Issue]:
    return [issue for issue in verdict.blocking_issues if issue.blocking]


def _judge_mode(verdict: ReviewVerdict) -> str | None:
    raw = verdict.metadata.get("judge_mode")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _shadow_match_rate(verdict: ReviewVerdict) -> float | None:
    raw = verdict.metadata.get("shadow_match_rate")
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def _shadow_mismatch_count(verdict: ReviewVerdict) -> int | None:
    raw = verdict.metadata.get("shadow_mismatch_count")
    if isinstance(raw, int):
        return raw
    return None


def _render_issue_line(issue: Issue) -> str:
    scope = issue.layer or issue.check_id or "general"
    return f"  - [{issue.severity}] {scope}: {issue.message}"
