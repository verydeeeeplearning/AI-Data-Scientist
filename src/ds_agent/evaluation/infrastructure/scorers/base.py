"""Shared helpers for evaluation scorers."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ds_agent.evaluation.domain.entities.eval_score import EvalScore
from ds_agent.evaluation.domain.ports.judge_llm import JudgeLLM, JudgeRequest
from ds_agent.evaluation.domain.value_objects.judge_type import JudgeType

_PLACEHOLDER_PATTERN = re.compile(r"\b(?:todo|tbd|placeholder|lorem ipsum)\b", re.IGNORECASE)
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?%?")


def clamp_score(value: float) -> float:
    """Clamp a score to the [0, 1] interval."""

    return max(0.0, min(1.0, value))


def build_score(
    *,
    name: str,
    value: float,
    rationale: str,
    judge_type: JudgeType,
    version: str,
    sub_scores: dict[str, float] | None = None,
    evidence_refs: Iterable[str] | None = None,
) -> EvalScore:
    """Build a normalized score model."""

    return EvalScore(
        name=name,
        value=clamp_score(value),
        rationale=rationale,
        judge_type=judge_type,
        version=version,
        sub_scores={key: clamp_score(item) for key, item in (sub_scores or {}).items()},
        evidence_refs=tuple(evidence_refs or ()),
    )


def maybe_use_judge(
    *,
    judge: JudgeLLM | None,
    request: JudgeRequest | None,
    fallback: EvalScore,
) -> EvalScore:
    """Run the external judge when configured, otherwise return the fallback score."""

    if judge is None or request is None:
        return fallback
    return judge.judge(request)


def contains_placeholder(text: str) -> bool:
    """Return whether the text looks like a placeholder."""

    return bool(_PLACEHOLDER_PATTERN.search(text))


def extract_numbers(text: str) -> tuple[str, ...]:
    """Extract normalized numeric mentions from a block of text."""

    return tuple(_NUMBER_PATTERN.findall(text))

