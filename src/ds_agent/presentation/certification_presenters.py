"""Plain-text renderers for certification surfaces."""

from __future__ import annotations

from ds_agent.application.services.certification_usecases import (
    CertificationStatusResult,
    SubmitCertificationResult,
)


def render_certification_status(
    result: CertificationStatusResult,
    *,
    compact: bool = False,
) -> str:
    """Render one certification status summary for CLI and Telegram."""

    lines = [
        f"Certification: {result.mission_name} v{result.mission_version}",
        (
            "Levels: "
            f"current={_display_level(result.current_level)} | "
            f"effective={_display_level(result.effective_level)} | "
            f"next={_display_level(result.next_target)}"
        ),
        (
            "Readiness: "
            f"{'certified' if result.certified_for_next_target else 'not certified'} | "
            f"owner approvals={result.required_approvers}"
        ),
        (
            "Evidence: "
            f"shadow_runs={result.stats.shadow_runs_passed} | "
            f"critical={result.stats.critical_violations} | "
            "score="
            f"{_display_score(result.stats.verifier_avg_score)} | "
            f"rollback={'passed' if result.stats.rollback_rehearsal_passed else 'not passed'}"
        ),
    ]
    if result.latest_certification is not None:
        lines.append(
            "Latest approval: "
            f"{result.latest_certification.level.value} on "
            f"{result.latest_certification.approved_at.date().isoformat()} by "
            f"{', '.join(result.latest_certification.approved_by)}"
        )
    if result.gaps:
        lines.append("Gaps:")
        max_items = 2 if compact else 4
        lines.extend(f"  - {gap}" for gap in result.gaps[:max_items])
        if len(result.gaps) > max_items:
            lines.append(f"  - ... +{len(result.gaps) - max_items} more")
    return "\n".join(lines)


def render_certification_submission(result: SubmitCertificationResult) -> str:
    """Render one certification submission outcome."""

    lines = [
        f"Certification submit: {result.mission_name} v{result.mission_version}",
        f"Target: {result.target_level.value}",
        f"Status: {result.status}",
    ]
    if result.certification is not None:
        lines.append(f"Approved by: {', '.join(result.certification.approved_by)}")
    elif result.approved_by:
        lines.append(f"Approvals received: {', '.join(result.approved_by)}")
    if result.status == "awaiting_approval":
        lines.append(
            "Owner approvals required: "
            f"{len(result.approved_by)}/{result.required_approvers}"
        )
    if result.gaps:
        lines.append("Gaps:")
        lines.extend(f"  - {gap}" for gap in result.gaps)
    return "\n".join(lines)


def _display_level(level: object) -> str:
    if level is None:
        return "none"
    return str(getattr(level, "value", level))


def _display_score(score: float | None) -> str:
    if score is None:
        return "n/a"
    return f"{score:.2f}"
