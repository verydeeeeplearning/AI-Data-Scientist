"""Executive summary scorer."""
# mypy: disable-error-code="no-untyped-def"


from __future__ import annotations

from ds_agent.evaluation.domain.entities.eval_run import EvalRun
from ds_agent.evaluation.domain.entities.gold_task import GoldTask
from ds_agent.evaluation.domain.ports.judge_llm import JudgeLLM, JudgeRequest
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType
from ds_agent.evaluation.infrastructure.scorers.base import build_score, maybe_use_judge

_REQUIRED_SECTIONS = {
    "core_finding": ("core finding", "핵심", "finding"),
    "confidence": ("confidence", "신뢰", "확신"),
    "limitations": ("limitations", "limitation", "한계"),
    "recommended_action": ("recommended action", "next action", "권장", "다음 액션"),
}


class ExecSummaryAccuracyScorer:
    """Evaluate whether the executive summary is decision-ready."""

    name = "exec_summary_accuracy"
    version = "0.1.0"
    judge_type = JudgeType.LLM

    def __init__(self, judge: JudgeLLM | None = None) -> None:
        self._judge = judge

    def score(self, run: EvalRun, task: GoldTask):
        summary_lower = run.final_summary.lower()
        explicit_sections = {
            key for key, value in run.summary_sections.items() if str(value).strip()
        }
        section_hits: dict[str, float] = {}
        for section_name, aliases in _REQUIRED_SECTIONS.items():
            if section_name in explicit_sections or any(
                alias in summary_lower for alias in aliases
            ):
                section_hits[section_name] = 1.0
            else:
                section_hits[section_name] = 0.0
        limitations_text = run.summary_sections.get("limitations", run.final_summary)
        value = sum(section_hits.values()) / len(section_hits)
        if len(limitations_text.strip()) < 20:
            value = min(value, 0.5)
        fallback = build_score(
            name=self.name,
            value=value,
            rationale=(
                f"Executive summary covers {int(sum(section_hits.values()))}/"
                f"{len(section_hits)} required sections."
            ),
            judge_type=self.judge_type,
            version=self.version,
            sub_scores=section_hits,
            evidence_refs=explicit_sections,
        )
        request = JudgeRequest(
            scorer_name=self.name,
            rubric_version=self.version,
            task_id=task.id,
            prompt=task.prompt,
            payload={
                "final_summary": run.final_summary,
                "summary_sections": run.summary_sections,
            },
            fallback_score=fallback.value,
            fallback_rationale=fallback.rationale,
        )
        return maybe_use_judge(judge=self._judge, request=request, fallback=fallback)
