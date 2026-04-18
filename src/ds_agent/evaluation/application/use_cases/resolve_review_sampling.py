"""Use case for deterministic human-review sampling decisions."""

from __future__ import annotations

import hashlib

from ds_agent.evaluation.domain.entities.review_sampling import ReviewSamplingDecision
from ds_agent.evaluation.domain.ports.review_sampling_store import ReviewSamplingStore

_POLICY_VERSION = "domain_hash_v1"


class ResolveReviewSampling:
    """Resolve and persist a stable human-review sampling decision for one run."""

    def __init__(self, store: ReviewSamplingStore) -> None:
        self._store = store

    def execute(
        self,
        *,
        session_id: str,
        run_id: str,
        task_id: str | None = None,
        domain: str | None = None,
        surface: str | None = None,
        target_rate: float = 0.20,
    ) -> ReviewSamplingDecision:
        if not 0.0 <= target_rate <= 1.0:
            raise ValueError("target_rate must be in [0, 1].")
        existing = self._store.latest(session_id=session_id, run_id=run_id)
        if existing is not None:
            return existing

        normalized_domain = _normalize_domain(domain)
        stratum = f"domain:{normalized_domain}"
        bucket = _stable_bucket(
            session_id=session_id,
            run_id=run_id,
            stratum=stratum,
        )
        record = ReviewSamplingDecision(
            session_id=session_id,
            run_id=run_id,
            task_id=task_id,
            domain=normalized_domain,
            surface=surface,
            target_rate=target_rate,
            bucket=bucket,
            sampled=bucket < target_rate,
            stratum=stratum,
            policy_version=_POLICY_VERSION,
        )
        self._store.append(record)
        return record


def _normalize_domain(domain: str | None) -> str:
    value = (domain or "").strip().lower()
    return value or "generic"


def _stable_bucket(*, session_id: str, run_id: str, stratum: str) -> float:
    digest = hashlib.sha256(
        f"{_POLICY_VERSION}|{stratum}|{session_id}|{run_id}".encode()
    ).hexdigest()
    numerator = int(digest[:12], 16)
    denominator = float(16**12)
    bucket = numerator / denominator
    return min(bucket, 0.999999999999)
