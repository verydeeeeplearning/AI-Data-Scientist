"""Port: ``LearningStoreAtomicPort`` — application-layer contract for
multi-row learning-governance writes that must commit as a single unit.

Why this port lives in the application layer
---------------------------------------------
The general CRUD contract for learning-governance entities is already
declared by :class:`ds_agent.domain.interfaces.learning.LearningStore`
(domain layer). That Protocol only speaks about *individual* row
operations (``save_item``, ``save_deprecation_record`` …), each of which
is free to commit independently.

Certain use cases, however, have an application-level invariant that
requires two rows to land together — in particular,
:class:`ds_agent.application.learning.rollback_promotion.RollbackPromotionUseCase`
must never leave a :class:`LearningItem` in the ``deprecated`` state
without a matching :class:`DeprecationRecord` (the "audit trail split"
described in the B11 probe evidence, see
``Docs/qa_run_2026-04-17/B11_portfolio_learning/B11_rollback_atomicity_sqlite_probe.json``).

Rather than pushing this concern into the domain Protocol (which is
shared by many callers and must stay minimal), we define the atomicity
contract here, at the application boundary. Concrete stores in
``ds_agent.infrastructure.persistence`` implement it next to their
regular ``LearningStore`` surface — typically inside a single SQLite
transaction (``BEGIN ... COMMIT`` with automatic rollback on failure).

The ``application_independence_from_infrastructure`` import-linter
contract remains satisfied: the use case imports only this Protocol,
and wiring happens at the composition root.

Contract
--------
See :class:`LearningStoreAtomicPort` below.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ds_agent.domain.learning.deprecation_record import DeprecationRecord
from ds_agent.domain.learning.learning_item import LearningItem
from ds_agent.domain.learning.promotion_record import PromotionRecord
from ds_agent.domain.learning.review_event import ReviewEvent


@runtime_checkable
class LearningStoreAtomicPort(Protocol):
    """Atomic persistence contract for multi-row learning-governance writes.

    All methods MUST commit the two passed artefacts inside a single
    storage transaction:

    * On success, both rows are durably persisted.
    * On failure of either write, neither row is persisted — the
      caller sees an exception and the storage is byte-for-byte
      indistinguishable from the pre-call state with respect to these
      two rows. No partial "item in new status but audit record missing"
      state is ever observable by other readers.

    The methods intentionally take only the two artefacts that must be
    co-committed; identity/validation checks remain the caller's
    responsibility.

    Raises:
        Exception: any storage-layer exception is re-raised verbatim
            after the transaction has been rolled back.
    """

    def save_item_and_deprecation(
        self,
        *,
        item: LearningItem,
        deprecation: DeprecationRecord,
    ) -> None:
        """Atomic unit for rollback / deprecate-immediate paths.

        Co-commits a deprecated LearningItem together with its
        DeprecationRecord. Originally introduced by S6 (FAIL-B11-8).
        Reused by the IMMEDIATE branch of
        :class:`~ds_agent.application.learning.deprecate_learning_item.DeprecateLearningItemUseCase`
        (S9, R-2).
        """
        ...

    def save_promotion_and_item(
        self,
        *,
        promotion: PromotionRecord,
        item: LearningItem,
    ) -> None:
        """Atomic unit for promote path (S9, R-1).

        Co-commits a PromotionRecord and the promoted LearningItem so
        that a reader can never see a PromotionRecord referring to an
        item whose status is still ``approved`` (the phantom-promotion
        audit split described in S6 RECOMMENDATIONS §R-1).
        """
        ...

    def save_review_event_and_item(
        self,
        *,
        event: ReviewEvent,
        item: LearningItem,
    ) -> None:
        """Atomic unit for review path (S10, R-3).

        Co-commits a ReviewEvent and the (possibly transitioned)
        LearningItem. The review-event stream is treated as append-only
        evidence, so the risk here is subtler than R-1/R-2: a reviewer
        decision could be durably recorded while the item's state
        transition is lost, violating the "audit trail matches item
        state" invariant. See S6 RECOMMENDATIONS §R-3 for the original
        finding.
        """
        ...
