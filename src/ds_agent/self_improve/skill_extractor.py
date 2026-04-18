"""SkillExtractor — converts successful ProjectOutcome into custom skill markdown.

When a project completes successfully with meaningful steps, persists a
reusable skill at `src/ds_agent/skills/custom/<slug>.md`. The custom
directory is auto-discovered by SkillHub in `factory.build_skill_hub`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from ds_agent.self_improve.post_project import ProjectOutcome
    from ds_agent.self_improve.promotion_candidates import JsonPromotionCandidateStore

logger = structlog.get_logger()

_DEFAULT_CUSTOM_DIR = Path(__file__).resolve().parent.parent / "skills" / "custom"


@dataclass
class ExtractedSkill:
    name: str
    path: Path
    content: str
    candidate_id: str
    promotion_status: str = "pending_promotion"


class SkillExtractor:
    """Extract reusable skills from successful project outcomes.

    Success criteria (all must hold):
      - outcome.success is True
      - outcome.steps_taken has at least `min_steps` entries
      - outcome.primary_metric_value exceeds `min_metric_value` (if provided)
    """

    def __init__(
        self,
        custom_dir: Path | None = None,
        min_steps: int = 3,
        min_metric_value: float | None = None,
        candidate_store: JsonPromotionCandidateStore | None = None,
    ) -> None:
        self._custom_dir = Path(custom_dir) if custom_dir else _DEFAULT_CUSTOM_DIR
        self._min_steps = min_steps
        self._min_metric_value = min_metric_value
        self._candidate_store = candidate_store

    def extract(self, outcome: ProjectOutcome) -> ExtractedSkill | None:
        """Write a skill markdown if the outcome qualifies. Returns None otherwise."""
        if not self._qualifies(outcome):
            logger.debug(
                "skill_extraction_skipped",
                pid=outcome.project_id,
                success=outcome.success,
                steps=len(outcome.steps_taken),
            )
            return None

        slug = self._build_slug(outcome)
        content = self._render(outcome, slug)
        description = self._description(outcome)

        self._custom_dir.mkdir(parents=True, exist_ok=True)
        path = self._custom_dir / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        candidate_id = slug
        if self._candidate_store is not None:
            self._candidate_store.register_skill_candidate(
                candidate_id=candidate_id,
                name=slug,
                description=description,
                source_project_id=outcome.project_id,
                pending_path=path,
            )

        logger.info(
            "custom_skill_candidate_created",
            pid=outcome.project_id,
            skill=slug,
            candidate_id=candidate_id,
            path=str(path),
        )
        return ExtractedSkill(
            name=slug,
            path=path,
            content=content,
            candidate_id=candidate_id,
        )

    def _qualifies(self, outcome: ProjectOutcome) -> bool:
        if not outcome.success:
            return False
        if len(outcome.steps_taken) < self._min_steps:
            return False
        return not (
            self._min_metric_value is not None
            and outcome.primary_metric_value < self._min_metric_value
        )

    def _build_slug(self, outcome: ProjectOutcome) -> str:
        parts = [outcome.task_type or "analysis"]
        if outcome.domain:
            parts.append(outcome.domain)
        parts.append(outcome.project_id)
        raw = "-".join(parts).lower()
        slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
        return slug or f"custom-skill-{outcome.project_id}"

    @staticmethod
    def _description(outcome: ProjectOutcome) -> str:
        return (
            f"Auto-extracted workflow from a successful "
            f"{outcome.task_type} project "
            f"(metric {outcome.primary_metric}={outcome.primary_metric_value:.4f})."
        )

    @staticmethod
    def _render(outcome: ProjectOutcome, slug: str) -> str:
        generated_at = datetime.now(UTC).strftime("%Y-%m-%d")
        tags = _yaml_string_list(
            [
                outcome.task_type,
                outcome.domain or "general",
                "extracted",
                "post-project",
            ]
        )
        description = SkillExtractor._description(outcome)
        steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(outcome.steps_taken))
        findings = "\n".join(f"- {f}" for f in outcome.key_findings) or "- (none)"
        models = ", ".join(outcome.models_tried) or "n/a"

        return (
            "---\n"
            f"name: {slug}\n"
            f"description: {description}\n"
            "category: extracted\n"
            f"tags: {tags}\n"
            'version: "1.0.0"\n'
            "author: skill_extractor\n"
            f"token_estimate: {max(200, len(steps) * 30)}\n"
            f"source_project_id: {outcome.project_id}\n"
            f"extracted_at: {generated_at}\n"
            "promotion_status: pending_promotion\n"
            "---\n\n"
            f"# {slug.replace('-', ' ').title()}\n\n"
            "## When to Use\n"
            f"- Task type: `{outcome.task_type}`\n"
            f"- Domain: `{outcome.domain or 'general'}`\n"
            f"- Target metric: `{outcome.primary_metric}` "
            f"(proven value: {outcome.primary_metric_value:.4f})\n\n"
            "## Proven Workflow\n"
            f"{steps}\n\n"
            "## Model Choices\n"
            f"- Models tried: {models}\n"
            f"- Best model: {outcome.best_model or 'n/a'}\n\n"
            "## Key Findings\n"
            f"{findings}\n\n"
            "## Notes\n"
            f"- Extracted from project `{outcome.project_id}`.\n"
            "- Validate assumptions on new datasets before reuse.\n"
        )


def _yaml_string_list(values: list[str]) -> str:
    items = ", ".join(f'"{v}"' for v in values if v)
    return f"[{items}]"
