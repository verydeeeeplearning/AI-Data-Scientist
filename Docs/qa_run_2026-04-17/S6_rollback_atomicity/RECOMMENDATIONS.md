# S6 Recommendations — out-of-scope findings

During the REFACTOR-scan step of S6 (per work-order §3.3) we looked for
other learning-governance use cases with the same two-store-write
pattern that motivated this fix. Below are the findings. Per
work-order constraint §3.6 they are **not addressed in S6** and are
recorded here for future stream dispatch.

## R-1 — `PromoteLearningItemUseCase` audit-split risk (MED)

File: `src/ds_agent/application/learning/promote_learning_item.py`
Lines: 94–95

```python
self._store.save_promotion_record(record)
self._store.save_item(updated)
```

Failure mode: if `save_item` fails, a `PromotionRecord` exists for an
item whose `status` is still `approved` (not `promoted`). Readers that
trust the promotion record's existence as proof of promotion will see
a phantom promotion.

Suggested fix: extend the atomic port (or add a sibling method
`save_promotion_and_item`) and wrap both writes in a single transaction.

## R-2 — `DeprecateLearningItemUseCase` audit-split risk (MED)

File: `src/ds_agent/application/learning/deprecate_learning_item.py`
Lines: 81–83

```python
if mode == DeprecationMode.IMMEDIATE:
    updated = item.transition_to(LearningItemStatus.DEPRECATED, now=now)
    self._store.save_item(updated)

self._store.save_deprecation_record(record)
```

Same failure shape as the B11-reported rollback bug, in the immediate-
deprecation path. If `save_deprecation_record` fails after `save_item`,
the item is marked `deprecated` with no audit record.

Suggested fix: reuse `LearningStoreAtomicPort.save_item_and_deprecation`
from S6 — the signature already fits this use case verbatim, so no new
port method is needed.

## R-3 — `ReviewLearningItemUseCase` audit-split risk (LOW/MED)

File: `src/ds_agent/application/learning/review_learning_item.py`
Lines: 73–74

```python
self._store.save_review_event(event)
self._store.save_item(updated)
```

If `save_item` fails, a `ReviewEvent` records a decision for an item
whose status has not actually transitioned. This is less severe than
R-1/R-2 because the review-event stream is treated as append-only
evidence regardless of item state, but it still violates the "audit
trail matches item state" invariant.

Suggested fix: new atomic port method (e.g.
`save_review_event_and_item`) — or, better, a generalised
`begin_txn()` context-manager port that multiple use cases can compose
around.

## R-4 — Architectural follow-up: consider a generalised txn port

S6 takes the "method per atomic unit" approach because it is minimal
and explicit. As R-1 through R-3 accumulate similar methods, the port
surface may grow. A follow-up stream should evaluate whether a
`LearningStoreTxnPort.begin_transaction() -> ContextManager[...]`
shape (returning a thin batch interface) is a cleaner long-term
contract. Key trade-offs:

- Pro: one port method covers all future multi-row patterns.
- Con: harder to type cleanly in Python (`Protocol` + context manager
  + cross-row validation) and gives callers more rope to break
  boundary rules.

Recommend this be scoped as part of a dedicated architecture-review
stream rather than piecewise fixes.

## R-5 — Test-coverage gap in `test_rollback_promotion.py`

The existing `test_rollback_transitions_to_deprecated` was the only
pre-existing test that asserted the **call pattern** of the use case's
write side. None of the other rollback tests asserted a contract about
atomicity. After the S6 assertion update, we now have the new
`test_rollback_atomicity.py` doing that job explicitly — future
breakage will be caught by the new file, and the old test remains a
happy-path sanity check. No action required; recorded for clarity.

---

**Dispatch recommendation**: bundle R-1, R-2, R-3 into a follow-up
stream (e.g. S10 "Audit-trail atomicity for remaining learning
governance use cases"). R-4 warrants an RFC in a later cycle.
