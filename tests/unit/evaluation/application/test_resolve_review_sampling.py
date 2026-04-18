from __future__ import annotations

from ds_agent.evaluation.application.use_cases.resolve_review_sampling import (
    ResolveReviewSampling,
)
from ds_agent.evaluation.infrastructure.persistence.jsonl_review_sampling_store import (
    JsonlReviewSamplingStore,
)


def test_resolve_review_sampling_persists_stable_decision(tmp_path) -> None:
    store = JsonlReviewSamplingStore(tmp_path / "review-sampling.jsonl")
    use_case = ResolveReviewSampling(store)

    first = use_case.execute(
        session_id="session-1",
        run_id="run-1",
        task_id="task-1",
        domain="retail",
        surface="ws",
        target_rate=0.2,
    )
    second = use_case.execute(
        session_id="session-1",
        run_id="run-1",
        task_id="task-1",
        domain="retail",
        surface="ws",
        target_rate=0.2,
    )

    assert first == second
    assert first.stratum == "domain:retail"
    assert len(store.load_all()) == 1


def test_resolve_review_sampling_respects_extreme_target_rates(tmp_path) -> None:
    store = JsonlReviewSamplingStore(tmp_path / "review-sampling.jsonl")
    use_case = ResolveReviewSampling(store)

    always = use_case.execute(
        session_id="session-1",
        run_id="run-always",
        domain="finance",
        target_rate=1.0,
    )
    never = use_case.execute(
        session_id="session-1",
        run_id="run-never",
        domain="finance",
        target_rate=0.0,
    )

    assert always.sampled is True
    assert never.sampled is False
    assert len(store.load_all()) == 2

