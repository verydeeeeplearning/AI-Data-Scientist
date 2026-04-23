"""Failure taxonomy GC loop over persisted failure-signal learning items."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from ds_agent.domain.interfaces.learning import LearningStore
from ds_agent.domain.learning.failure_taxonomy import (
    FailureClass,
    FailureTaxonomyItem,
)
from ds_agent.domain.learning.learning_item import (
    LearningItem,
    LearningItemStatus,
    LearningItemType,
)
from ds_agent.self_improve.promotion_candidates import JsonPromotionCandidateStore

_log = logging.getLogger(__name__)

_IGNORED_STATUSES = frozenset(
    {
        LearningItemStatus.ARCHIVED,
        LearningItemStatus.DEPRECATED,
        LearningItemStatus.REJECTED,
    }
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class FailureSignalSync(Protocol):
    """Optional source sync hook executed before the GC sweep."""

    def sync(self, *, limit: int) -> None: ...


@dataclass(frozen=True)
class FailureClassSummary:
    """Aggregate view of one failure class in the GC loop."""

    failure_class: FailureClass
    item_count: int
    recurrence_count: int
    warning_types: tuple[str, ...]
    source_kinds: tuple[str, ...]


@dataclass(frozen=True)
class FailureTaxonomySkillCandidate:
    """Pending self-improve skill candidate derived from one repeated failure class."""

    failure_class: FailureClass
    candidate_id: str
    status: str
    pending_path: str
    reused_existing: bool = False


@dataclass(frozen=True)
class FailureTaxonomyGCLoopResult:
    """Structured result for one GC loop execution."""

    generated_at: datetime
    total_items: int
    total_recurrences: int
    promotion_threshold: int
    class_summaries: tuple[FailureClassSummary, ...]
    promotion_candidate_classes: tuple[FailureClass, ...]
    registered_skill_candidates: tuple[FailureTaxonomySkillCandidate, ...]
    report_path: str | None
    # Gap 5D-4: promotion candidates lacking remediation surface assignment
    incomplete_promotion_candidate_classes: tuple[FailureClass, ...] = ()


class FailureTaxonomyGCLoopUseCase:
    """Classify persisted failure signals and emit a GC report."""

    def __init__(
        self,
        store: LearningStore,
        clock: Clock,
        workspace_dir: str | Path,
        signal_sync: FailureSignalSync | None = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._workspace_dir = Path(workspace_dir)
        self._signal_sync = signal_sync

    def execute(
        self,
        *,
        promotion_threshold: int = 3,
        limit: int = 200,
        write_report: bool = True,
    ) -> FailureTaxonomyGCLoopResult:
        if promotion_threshold < 1:
            raise ValueError("promotion_threshold must be >= 1")
        if limit < 1:
            raise ValueError("limit must be >= 1")

        generated_at = self._clock.now()
        if self._signal_sync is not None:
            self._signal_sync.sync(limit=limit)
        learning_items = self._load_failure_signal_items(limit=limit)
        taxonomy_items = [FailureTaxonomyItem.from_learning_item(item) for item in learning_items]
        summaries = self._build_summaries(taxonomy_items)
        promotion_candidates = tuple(
            summary.failure_class
            for summary in summaries
            if summary.failure_class is not FailureClass.UNCATEGORIZED
            and summary.recurrence_count >= promotion_threshold
        )
        incomplete_promotion_candidates = self._detect_incomplete_promotion_candidates(
            taxonomy_items=taxonomy_items,
            promotion_candidates=promotion_candidates,
        )
        registered_skill_candidates = self._register_skill_candidates(
            taxonomy_items=taxonomy_items,
            promotion_candidates=promotion_candidates,
            generated_at=generated_at,
        )

        self._persist_gc_metadata(
            learning_items,
            taxonomy_items,
            generated_at=generated_at,
            promotion_candidates=set(promotion_candidates),
            registered_skill_candidates=registered_skill_candidates,
        )

        report_path = (
            self._write_report(
                generated_at=generated_at,
                summaries=summaries,
                taxonomy_items=taxonomy_items,
                promotion_threshold=promotion_threshold,
                promotion_candidates=promotion_candidates,
                incomplete_promotion_candidates=incomplete_promotion_candidates,
                registered_skill_candidates=registered_skill_candidates,
            )
            if write_report
            else None
        )

        return FailureTaxonomyGCLoopResult(
            generated_at=generated_at,
            total_items=len(taxonomy_items),
            total_recurrences=sum(item.recurrence_count for item in taxonomy_items),
            promotion_threshold=promotion_threshold,
            class_summaries=tuple(summaries),
            promotion_candidate_classes=promotion_candidates,
            registered_skill_candidates=registered_skill_candidates,
            report_path=str(report_path) if report_path is not None else None,
            incomplete_promotion_candidate_classes=incomplete_promotion_candidates,
        )

    def _load_failure_signal_items(self, *, limit: int) -> list[LearningItem]:
        items = self._store.list_items(item_type=LearningItemType.PATTERN, limit=limit)
        return [
            item
            for item in items
            if item.status not in _IGNORED_STATUSES and self._is_failure_signal_item(item)
        ]

    @staticmethod
    def _is_failure_signal_item(item: LearningItem) -> bool:
        if "harness.warning" in item.tags:
            return True
        warning_type = item.metadata.get("warningType")
        if isinstance(warning_type, str) and warning_type.strip() != "":
            return True
        signal_type = item.metadata.get("failureSignalType")
        return isinstance(signal_type, str) and signal_type.strip() != ""

    @staticmethod
    def _build_summaries(
        taxonomy_items: list[FailureTaxonomyItem],
    ) -> list[FailureClassSummary]:
        by_class: dict[FailureClass, list[FailureTaxonomyItem]] = {}
        for item in taxonomy_items:
            by_class.setdefault(item.failure_class, []).append(item)

        summaries: list[FailureClassSummary] = []
        for failure_class, items in by_class.items():
            warning_types = sorted({item.warning_type for item in items})
            source_kinds = sorted({item.source_kind for item in items})
            summaries.append(
                FailureClassSummary(
                    failure_class=failure_class,
                    item_count=len(items),
                    recurrence_count=sum(item.recurrence_count for item in items),
                    warning_types=tuple(warning_types),
                    source_kinds=tuple(source_kinds),
                )
            )
        summaries.sort(
            key=lambda item: (-item.recurrence_count, -item.item_count, item.failure_class.value)
        )
        return summaries

    @staticmethod
    def _detect_incomplete_promotion_candidates(
        *,
        taxonomy_items: list[FailureTaxonomyItem],
        promotion_candidates: tuple[FailureClass, ...],
    ) -> tuple[FailureClass, ...]:
        """Return promotion candidate classes that have no remediation surface assigned."""
        if not promotion_candidates:
            return ()
        # A failure class is complete if at least one of its items has remediation surfaces
        classes_with_surfaces: set[FailureClass] = set()
        for item in taxonomy_items:
            if item.remediation_surfaces:
                classes_with_surfaces.add(item.failure_class)
        incomplete = tuple(
            fc for fc in promotion_candidates if fc not in classes_with_surfaces
        )
        for fc in incomplete:
            _log.warning(
                "Promotion candidate %r has no remediation surface assigned — "
                "set remediationSurfaces in item metadata to close this gap.",
                fc.value,
            )
        return incomplete

    def _persist_gc_metadata(
        self,
        learning_items: list[LearningItem],
        taxonomy_items: list[FailureTaxonomyItem],
        *,
        generated_at: datetime,
        promotion_candidates: set[FailureClass],
        registered_skill_candidates: tuple[FailureTaxonomySkillCandidate, ...],
    ) -> None:
        generated_at_iso = generated_at.isoformat()
        candidates_by_class = {
            candidate.failure_class: candidate for candidate in registered_skill_candidates
        }
        for learning_item, taxonomy_item in zip(learning_items, taxonomy_items, strict=False):
            metadata = dict(learning_item.metadata)
            metadata["failureTaxonomyClass"] = taxonomy_item.failure_class.value
            metadata["failureTaxonomyLastGcAt"] = generated_at_iso
            metadata["failureTaxonomyRecurrenceCount"] = taxonomy_item.recurrence_count
            metadata["failureTaxonomyPromotionCandidate"] = (
                taxonomy_item.failure_class in promotion_candidates
            )
            candidate = candidates_by_class.get(taxonomy_item.failure_class)
            if candidate is not None:
                metadata["failureTaxonomyCandidateId"] = candidate.candidate_id
                metadata["failureTaxonomyCandidateStatus"] = candidate.status
                metadata["failureTaxonomyCandidatePath"] = candidate.pending_path
            else:
                metadata.pop("failureTaxonomyCandidateId", None)
                metadata.pop("failureTaxonomyCandidateStatus", None)
                metadata.pop("failureTaxonomyCandidatePath", None)
            if metadata == learning_item.metadata:
                continue
            self._store.save_item(
                learning_item.model_copy(
                    update={
                        "metadata": metadata,
                        "updated_at": generated_at,
                    }
                )
            )

    def _write_report(
        self,
        *,
        generated_at: datetime,
        summaries: list[FailureClassSummary],
        taxonomy_items: list[FailureTaxonomyItem],
        promotion_threshold: int,
        promotion_candidates: tuple[FailureClass, ...],
        incomplete_promotion_candidates: tuple[FailureClass, ...],
        registered_skill_candidates: tuple[FailureTaxonomySkillCandidate, ...],
    ) -> Path:
        report_dir = self._workspace_dir / "Docs" / "operations" / "gc_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"GC_REPORT_{generated_at.strftime('%Y-%m-%d_%H%M%S')}.md"
        lines = [
            "# Failure Taxonomy GC Report",
            "",
            f"- generated_at: {generated_at.isoformat()}",
            f"- total_items: {len(taxonomy_items)}",
            f"- total_recurrences: {sum(item.recurrence_count for item in taxonomy_items)}",
            f"- promotion_threshold: {promotion_threshold}",
            "",
            "## Class Summary",
        ]
        if summaries:
            for summary in summaries:
                warning_types = ", ".join(summary.warning_types) or "none"
                source_kinds = ", ".join(summary.source_kinds) or "none"
                lines.append(
                    "- "
                    f"{summary.failure_class.value}: items={summary.item_count}, "
                    f"recurrences={summary.recurrence_count}, "
                    f"signal_types={warning_types}, "
                    f"source_kinds={source_kinds}"
                )
        else:
            lines.append("- none")

        # Build per-class remediation surface map for the Promotion Candidates section
        incomplete_set = set(incomplete_promotion_candidates)
        surfaces_by_class: dict[FailureClass, list[str]] = {}
        owners_by_class: dict[FailureClass, set[str]] = {}
        artifacts_by_class: dict[FailureClass, set[str]] = {}
        for item in taxonomy_items:
            if item.failure_class not in promotion_candidates:
                continue
            surfaces_by_class.setdefault(item.failure_class, [])
            owners_by_class.setdefault(item.failure_class, set())
            artifacts_by_class.setdefault(item.failure_class, set())
            surfaces_by_class[item.failure_class].extend(item.remediation_surfaces)
            if item.owner:
                owners_by_class[item.failure_class].add(item.owner)
            if item.target_artifact:
                artifacts_by_class[item.failure_class].add(item.target_artifact)

        lines.extend(["", "## Promotion Candidates"])
        if promotion_candidates:
            for failure_class in promotion_candidates:
                is_incomplete = failure_class in incomplete_set
                status_tag = "INCOMPLETE (no remediation surface)" if is_incomplete else "OK"
                lines.append(f"- {failure_class.value} [{status_tag}]")
                if not is_incomplete:
                    dedupe_surfaces = sorted(set(surfaces_by_class.get(failure_class, [])))
                    owners = sorted(owners_by_class.get(failure_class, set()))
                    artifacts = sorted(artifacts_by_class.get(failure_class, set()))
                    if dedupe_surfaces:
                        lines.append(
                            f"  - Remediation: {', '.join(dedupe_surfaces)}"
                            + (f" → {', '.join(artifacts)}" if artifacts else "")
                        )
                    if owners:
                        lines.append(f"  - Owner: {', '.join(owners)}")
        else:
            lines.append("- none")

        lines.extend(["", "## Registered Skill Candidates"])
        if registered_skill_candidates:
            for candidate in registered_skill_candidates:
                lines.append(
                    "- "
                    f"{candidate.failure_class.value}: id={candidate.candidate_id}, "
                    f"status={candidate.status}, "
                    f"reused_existing={str(candidate.reused_existing).lower()}, "
                    f"path={candidate.pending_path}"
                )
        else:
            lines.append("- none")

        lines.extend(["", "## Top Failure Items"])
        top_items = sorted(
            taxonomy_items,
            key=lambda item: (-item.recurrence_count, item.failure_class.value, item.item_id),
        )[:10]
        if top_items:
            for item in top_items:
                lines.append(
                    "- "
                    f"{item.item_id}: class={item.failure_class.value}, "
                    f"type={item.warning_type}, source={item.source_kind}, "
                    f"severity={item.severity}, "
                    f"recurrences={item.recurrence_count}"
                )
        else:
            lines.append("- none")

        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report_path

    def _register_skill_candidates(
        self,
        *,
        taxonomy_items: list[FailureTaxonomyItem],
        promotion_candidates: tuple[FailureClass, ...],
        generated_at: datetime,
    ) -> tuple[FailureTaxonomySkillCandidate, ...]:
        if not promotion_candidates:
            return ()

        items_by_class: dict[FailureClass, list[FailureTaxonomyItem]] = {}
        for item in taxonomy_items:
            items_by_class.setdefault(item.failure_class, []).append(item)

        candidate_store = JsonPromotionCandidateStore.for_workspace(str(self._workspace_dir))
        registered: list[FailureTaxonomySkillCandidate] = []
        for failure_class in promotion_candidates:
            class_items = items_by_class.get(failure_class, [])
            if not class_items:
                continue
            registered.append(
                self._ensure_skill_candidate(
                    candidate_store,
                    failure_class=failure_class,
                    items=class_items,
                    generated_at=generated_at,
                )
            )
        return tuple(registered)

    def _ensure_skill_candidate(
        self,
        candidate_store: JsonPromotionCandidateStore,
        *,
        failure_class: FailureClass,
        items: list[FailureTaxonomyItem],
        generated_at: datetime,
    ) -> FailureTaxonomySkillCandidate:
        candidate_id = _candidate_id_for_failure_class(failure_class)
        existing = candidate_store.get(candidate_id)
        content = _render_failure_taxonomy_skill(
            failure_class=failure_class,
            items=items,
            generated_at=generated_at,
        )

        if existing is not None:
            pending_path = Path(existing.pending_path)
            if existing.status == "pending_promotion":
                pending_path.parent.mkdir(parents=True, exist_ok=True)
                pending_path.write_text(content, encoding="utf-8")
            return FailureTaxonomySkillCandidate(
                failure_class=failure_class,
                candidate_id=existing.candidate_id,
                status=existing.status,
                pending_path=str(pending_path),
                reused_existing=True,
            )

        pending_dir = candidate_store.path.parent / "pending_skills"
        pending_dir.mkdir(parents=True, exist_ok=True)
        pending_path = pending_dir / f"{candidate_id}.md"
        pending_path.write_text(content, encoding="utf-8")
        candidate = candidate_store.register_skill_candidate(
            candidate_id=candidate_id,
            name=candidate_id,
            description=(
                "Auto-generated failure-taxonomy guardrail candidate for "
                f"{failure_class.value} signals."
            ),
            source_project_id="learning-governance-gc",
            pending_path=pending_path,
        )
        return FailureTaxonomySkillCandidate(
            failure_class=failure_class,
            candidate_id=candidate.candidate_id,
            status=candidate.status,
            pending_path=str(pending_path),
        )


def latest_gc_report_path(workspace_dir: str | Path) -> Path | None:
    """Return the newest GC report for a workspace, if present."""

    report_dir = Path(workspace_dir) / "Docs" / "operations" / "gc_reports"
    if not report_dir.exists():
        return None
    reports = sorted(report_dir.glob("GC_REPORT_*.md"))
    if not reports:
        return None
    return reports[-1]


def _candidate_id_for_failure_class(failure_class: FailureClass) -> str:
    return f"failure-taxonomy-{failure_class.value}"


def _render_failure_taxonomy_skill(
    *,
    failure_class: FailureClass,
    items: list[FailureTaxonomyItem],
    generated_at: datetime,
) -> str:
    warning_types = sorted({item.warning_type for item in items if item.warning_type})
    source_kinds = sorted({item.source_kind for item in items if item.source_kind})
    total_recurrences = sum(item.recurrence_count for item in items)
    sample_messages = _dedupe_messages(item.message for item in items)[:3]
    title = failure_class.value.replace("_", " ").title()
    warning_list = ", ".join(warning_types) or "none"
    source_kind_list = ", ".join(source_kinds) or "none"
    message_block = "\n".join(f"- {message}" for message in sample_messages) or "- none"

    return (
        "---\n"
        f"name: {_candidate_id_for_failure_class(failure_class)}\n"
        "description: "
        f"Auto-generated guardrail candidate for recurring {failure_class.value} signals.\n"
        "category: extracted\n"
        f'tags: ["failure-taxonomy", "{failure_class.value}", "failure-signal", "governance"]\n'
        'version: "1.0.0"\n'
        "author: failure_taxonomy_gc\n"
        "token_estimate: 320\n"
        "source_project_id: learning-governance-gc\n"
        f"extracted_at: {generated_at.strftime('%Y-%m-%d')}\n"
        "promotion_status: pending_promotion\n"
        "---\n\n"
        f"# {title} Guardrail Candidate\n\n"
        "## When to Use\n"
        f"- Failure class: `{failure_class.value}`\n"
        f"- Signal types: `{warning_list}`\n"
        f"- Source kinds: `{source_kind_list}`\n"
        f"- Observed recurrences: `{total_recurrences}`\n\n"
        "## Observed Failure Pattern\n"
        f"{message_block}\n\n"
        "## Guardrail Draft\n"
        "- Escalate repeated signals of this class into explicit operator-visible follow-up.\n"
        "- Consider strengthening the matching hook, verifier checks, or mission requirements.\n"
        "- Use this draft as a starting point for a reviewed shared skill or runbook update.\n\n"
        "## Review Notes\n"
        "- Generated from the weekly learning-governance GC loop.\n"
        "- Requires human review before promotion into active custom skills.\n"
    )


def _dedupe_messages(messages: list[str] | tuple[str, ...] | object) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    if not isinstance(messages, (list, tuple)):
        messages = list(messages) if hasattr(messages, "__iter__") else []
    for message in messages:
        if not isinstance(message, str):
            continue
        normalized = message.strip()
        if not normalized:
            continue
        marker = normalized.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(normalized)
    return ordered
