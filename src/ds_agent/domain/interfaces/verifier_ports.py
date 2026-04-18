"""Verifier port interfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.dtos.verifier_context import VerifierContext
from ds_agent.domain.entities.review_verdict import (
    CheckResult,
    ConfidenceBand,
    LayerResult,
    ReviewVerdict,
)
from ds_agent.domain.entities.shadow_comparison import ShadowComparisonRecord


@runtime_checkable
class StatisticalCheck(Protocol):
    """Single deterministic statistical check."""

    name: str
    version: str

    def run(self, ctx: VerifierContext) -> CheckResult: ...


@runtime_checkable
class DataCheck(Protocol):
    """Single deterministic data-quality check."""

    name: str
    version: str

    def run(self, ctx: VerifierContext) -> CheckResult: ...


@runtime_checkable
class PolicyCheck(Protocol):
    """Single deterministic policy check."""

    name: str
    version: str

    def run(self, ctx: VerifierContext) -> CheckResult: ...


@runtime_checkable
class NarrativeCheck(Protocol):
    """Single deterministic or judge-backed narrative check."""

    name: str
    version: str

    def run(self, ctx: VerifierContext) -> CheckResult: ...


@runtime_checkable
class StatisticalVerifierPort(Protocol):
    """Layer adapter for statistical verification."""

    async def run(self, ctx: VerifierContext) -> LayerResult: ...


@runtime_checkable
class DataVerifierPort(Protocol):
    """Layer adapter for data verification."""

    async def run(self, ctx: VerifierContext) -> LayerResult: ...


@runtime_checkable
class PolicyVerifierPort(Protocol):
    """Layer adapter for policy verification."""

    async def run(self, ctx: VerifierContext) -> LayerResult: ...


@runtime_checkable
class NarrativeVerifierPort(Protocol):
    """Layer adapter for narrative verification."""

    async def run(self, ctx: VerifierContext) -> LayerResult: ...


@runtime_checkable
class LLMJudgePort(Protocol):
    """Provider-backed judge that scores narrative checks via structured JSON."""

    async def evaluate(self, ctx: VerifierContext) -> list[CheckResult]: ...


@runtime_checkable
class VerdictRepository(Protocol):
    """Persistence boundary for verifier verdicts."""

    def save(self, verdict: ReviewVerdict) -> None: ...

    def get(self, verdict_id: str) -> ReviewVerdict | None: ...

    def list_for_task(self, task_id: str) -> list[ReviewVerdict]: ...


@runtime_checkable
class ConfidenceScorerPort(Protocol):
    """Score a verdict into a confidence band."""

    def score(self, verdict: ReviewVerdict) -> ConfidenceBand: ...

    def explain(self, verdict: ReviewVerdict) -> str: ...


@runtime_checkable
class ShadowComparatorPort(Protocol):
    """Compare legacy hook signals against one verifier verdict."""

    def compare(
        self,
        ctx: VerifierContext,
        verdict: ReviewVerdict,
    ) -> ShadowComparisonRecord | None: ...


@runtime_checkable
class ShadowComparisonRepository(Protocol):
    """Persistence boundary for verifier shadow diff logs."""

    def save(self, record: ShadowComparisonRecord) -> None: ...

    def get(self, comparison_id: str) -> ShadowComparisonRecord | None: ...

    def list_for_task(self, task_id: str) -> list[ShadowComparisonRecord]: ...

    def list_for_verdict(self, verdict_id: str) -> list[ShadowComparisonRecord]: ...
