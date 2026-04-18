# B11 Re-Audit Report — Round 2

**Agent**: B11 Portfolio / Learning Governance Re-Auditor (Round 2)
**Date**: 2026-04-17
**Delta scope**: Path 8 (Rollback atomicity) — all other paths regression-only
**Prior round**: `Docs/qa_run_2026-04-17/B11_portfolio_learning/` (Round 1 — Path 8 FAIL)
**Fix under review**: `Docs/qa_run_2026-04-17/S6_rollback_atomicity/` (S6 Fix Sprint Round 3)
**Evidence bundle**: `Docs/qa_run_2026-04-17/B11_portfolio_learning_reaudit/`

---

## 1. Executive summary

| Area | Round 1 verdict | Round 2 verdict |
|------|:---------------:|:---------------:|
| Path 8 — Rollback atomicity | **FAIL** (NON_ATOMIC_PARTIAL) | **PASS** (ATOMIC) |
| Paths 1-7, 9 — regression | PASS (8/8) | PASS (8/8 — no regression) |
| import-linter contracts | 2 kept | 2 kept |
| ruff on S6-modified files | clean | clean |

**Result**: The S6 fix resolves FAIL-B11-8. Path 8 re-audit verdict is **PASS** on the basis of this agent's own probe (three independent adversarial scenarios, none relying on S6's self-reported simulation).

Per HANDOFF §6.3, self-pass is not declared here — final Tier 2 gate disposition is deferred to D18.

---

## 2. Audit posture

* **Auditor ≠ modifier**: no source changes; only probes, test re-runs, static checks.
* **Self-confirmation-bias guard**: this agent authored its own probe
  (`.tmp/qa_B11_reaudit/probe_rollback_atomicity.py`) with three scenarios
  against the real `SqliteLearningStore`. S6's own
  `B11_probe_simulation.json` was **not** used as evidence for the verdict.
* **Stricter pass bar**: atomicity verified under three independent failure
  modes (happy, atomic-port injection, real-connection-level injection).
* **Out of scope**: Paths 1-7, 9 were re-run at regression level only
  (145 tests — same command line as Round 1 §2.1).

---

## 3. S6 changes under review

From `Docs/qa_run_2026-04-17/S6_rollback_atomicity/DIFF_SUMMARY.md`:

| File | Kind | Lines |
|------|------|-------|
| `src/ds_agent/application/ports/learning_store_port.py` | **NEW** | +70 |
| `src/ds_agent/application/learning/rollback_promotion.py` | modified | +15 / -5 |
| `src/ds_agent/infrastructure/persistence/learning_store.py` | modified | +80 / 0 |
| `tests/unit/application/test_rollback_atomicity.py` | **NEW** | +205 |
| `tests/unit/application/test_rollback_promotion.py` | test-only | +7 / -2 |

Reviewed in situ (full file reads, not just diff): all five files match what
`DIFF_SUMMARY.md` claims. Detailed reviewer comments are in §7.

---

## 4. Re-audit probe results (Path 8)

Probe: `.tmp/qa_B11_reaudit/probe_rollback_atomicity.py`
Output: `B11_reaudit_rollback_probe.json`
Transport: real `SqliteLearningStore` against `tempfile.mkdtemp(...)` databases
(no `data/` access). No mocks of the store beyond explicit per-scenario wrappers.

| Scenario | Injection | Expected post-fix | Observed | Verdict |
|----------|-----------|-------------------|----------|:-------:|
| a — Happy path | none | item=deprecated, 1 dep record | item=deprecated, 1 dep record | **PASS** |
| b — Atomic-port failure | wrapper raises at `save_item_and_deprecation(...)` | item stays `promoted`, 0 dep records, exception bubbles | item=promoted, 0 dep records, `RuntimeError` raised | **PASS** |
| c — Real-connection failure | connection proxy raises on 2nd INSERT (`deprecation_records`) inside the atomic method; `BEGIN IMMEDIATE` has already executed the 1st INSERT | real `ROLLBACK` unwinds both rows; item stays `promoted`, 0 dep records, exception bubbles | item=promoted, 0 dep records, `RuntimeError` raised | **PASS** |
| port check | — | `isinstance(store, LearningStoreAtomicPort) is True` | True | **PASS** |

All 4/4 atomic. `path8_verdict = "pass"`.

### 4.1 Why this is stronger than Round 1 evidence alone

Round 1's probe only exercised a single failure site (legacy
`save_deprecation_record`). Round 2 scenario (c) additionally verifies that
the *real* sqlite3 `ROLLBACK` actually unwinds the first INSERT when a
mid-transaction exception fires — the most adversarial case, where a
mis-ordered `commit()` would leave the item row visible. Observing both
rows absent after the failure confirms the `BEGIN IMMEDIATE` / `ROLLBACK`
envelope in `save_item_and_deprecation` is wired correctly.

### 4.2 Note on the Round 1 probe script against HEAD

Running the literal Round 1 probe `.tmp/qa_B11/probe_rollback_sqlite.py`
against the fixed code now raises:

```
AttributeError: 'FailingStore' object has no attribute 'save_item_and_deprecation'
```

This is because the Round 1 `FailingStore` duck-typed only the legacy
two-method surface. The fixed use case now requires the atomic port. This
is a probe-script staleness artefact, **not** a regression — the Round 1
probe file is Round 1 evidence and is intentionally left untouched. Round 2
scenario (b) is the forward-compatible equivalent and demonstrates the
same revert semantics.

---

## 5. Regression re-run (Paths 1-7, 9)

### 5.1 Round 1 B11 scoped pytest replay

Command (verbatim from `B11_report.md` §2.1):

```
pytest tests/unit/domain/test_portfolio_entry.py \
       tests/unit/domain/test_learning_item.py \
       tests/unit/application/test_portfolio_scheduler.py \
       tests/unit/application/test_learning_inbox.py \
       tests/unit/application/test_review_learning_item.py \
       tests/unit/application/test_promote_learning_item.py \
       tests/unit/application/test_deprecate_learning_item.py \
       tests/unit/application/test_rollback_promotion.py \
       tests/unit/application/test_revalidation_scheduler.py \
       tests/unit/application/test_promotion_gate_usecases.py \
       tests/unit/application/test_self_improve_promotion_gate.py \
       tests/unit/infrastructure/test_promotion_decision_store.py \
       tests/integration/infrastructure/test_sqlite_portfolio_store.py \
       tests/integration/infrastructure/test_sqlite_learning_store.py \
       --junitxml=Docs/qa_run_2026-04-17/B11_portfolio_learning_reaudit/junit_b11_regression.xml
```

**Result: 145 passed in 0.73s** — identical to Round 1's 145 passed
(same pass count, same tests). **Regression count: 0**.

Junit: `junit_b11_regression.xml`.

### 5.2 S6-specified pytest set (scoped to FAIL-B11-8)

Per FIX_SPRINT_R3_WORK_ORDER §3.4:

```
pytest tests/unit/application/test_rollback_atomicity.py \
       tests/unit/application/test_rollback_promotion.py \
       tests/unit/application/test_promote_learning_item.py \
       tests/unit/application/test_deprecate_learning_item.py \
       tests/integration/infrastructure/test_sqlite_learning_store.py \
       --junitxml=Docs/qa_run_2026-04-17/B11_portfolio_learning_reaudit/junit_s6_rerun.xml
```

**Result: 33 passed in 0.30s**. Junit: `junit_s6_rerun.xml`.

All five tests introduced by S6 (new file
`test_rollback_atomicity.py`) pass independently of S6's own reporting.

---

## 6. Static & architectural checks

| Check | Command | Result |
|-------|---------|:------:|
| Import contracts (project script) | `python scripts/check_import_contracts.py` | `import contracts: ok` |
| Import-linter (CLI) | `lint-imports` | 2 contracts kept, 0 broken |
| Layer dependencies | `python scripts/check_layer_deps.py` | `semantic layer deps: ok` |
| ruff (S6 scope) | `ruff check src/ds_agent/application/ports/learning_store_port.py src/ds_agent/application/learning/rollback_promotion.py src/ds_agent/infrastructure/persistence/learning_store.py tests/unit/application/test_rollback_atomicity.py tests/unit/application/test_rollback_promotion.py` | `All checks passed!` |

Both named import-linter contracts are specifically verified intact:
`Domain must not depend on outer layers` and `Application must not depend
on infrastructure` — both KEPT. The new port sits in
`application.ports.learning_store_port`, imports only domain types
(`LearningItem`, `DeprecationRecord`), and the infrastructure adapter
implements it via duck-typing (no application → infrastructure import).

---

## 7. S6 change review comments

| File | Status | Comment |
|------|:------:|---------|
| `application/ports/learning_store_port.py` | OK | New `@runtime_checkable` Protocol. Only depends on domain types. Docstring explains why it lives in the application layer (not domain). No behaviour, pure data contract. LLM=orchestrator principle preserved. |
| `application/learning/rollback_promotion.py` | OK | Control flow replaces the pair `save_item` + `save_deprecation_record` with a single `save_item_and_deprecation` call. The cast `atomic: LearningStoreAtomicPort = self._store  # type: ignore[assignment]` is the pragmatic choice — the constructor keeps the broader `LearningStore` type so existing wiring isn't disturbed. |
| `infrastructure/persistence/learning_store.py` | OK | `save_item_and_deprecation` uses `BEGIN IMMEDIATE` + explicit `rollback()` via `contextlib.suppress(sqlite3.Error)`. Holds the existing `self._lock` for the whole envelope. Legacy single-row methods are untouched so other callers are unaffected. |
| `tests/unit/application/test_rollback_atomicity.py` | OK | Five tests; the SQLite-level `test_atomic_failure_rolls_back_both_rows` is the key invariant. Uses `tmp_path` (no `data/` writes). |
| `tests/unit/application/test_rollback_promotion.py` | OK | Adjustment is test-only: the assertion `store.save_item_and_deprecation.assert_called_once_with(...)` replaces the pre-fix pair. Behaviour-level assertions (`status == DEPRECATED`, `notes` content) unchanged. |

### 7.1 Minor (non-blocking) observations

1. **Broad exception catch**: the `except BaseException:` block in
   `save_item_and_deprecation` is unusually broad. The trade-off: `BaseException`
   ensures `KeyboardInterrupt`/`SystemExit` mid-transaction still triggers
   `ROLLBACK` before propagation. Given that this is a transactional guard
   (not swallowing), the choice is defensible — but `Exception` would be
   the more conventional catch and would be adequate for the atomicity
   contract. Not a failure, just a style note.

2. **Duck-typed port on the use case**: the use case still accepts the
   wider `LearningStore` type in its constructor and casts to
   `LearningStoreAtomicPort` at call time. A more explicit constructor
   signature (e.g. accepting both `LearningStore` and
   `LearningStoreAtomicPort`) would be type-safer, but would require
   wiring changes beyond S6's scope — correctly deferred.

3. **Out-of-scope double-write patterns (RECOMMENDATIONS.md)**: S6 notes
   three additional double-write sites (`PromoteLearningItemUseCase`,
   `DeprecateLearningItemUseCase`, `ReviewLearningItemUseCase`). Each was
   Round 1 PASS at the functional level (no failure injection was run),
   but the same atomicity class applies. Recommended as a follow-up
   stream — confirmed here as outside Path 8 scope.

None of the above is a blocker.

---

## 8. Deliverables checklist

- [x] `START.json` — written at start of round.
- [x] `.tmp/qa_B11_reaudit/probe_rollback_atomicity.py` — own probe.
- [x] `B11_reaudit_rollback_probe.json` — probe output (a/b/c + port).
- [x] `junit_s6_rerun.xml` — S6 pytest scope re-run.
- [x] `junit_b11_regression.xml` — Round 1 scope replay.
- [x] `B11_reaudit_report.md` — this file.
- [x] `FINAL.json` — see separate file.

---

## 9. Metrics

| Metric | Value |
|--------|:-----:|
| Path 8 re-audit verdict | **pass** |
| Adversarial scenarios passed | 3 / 3 (+ port check 1/1) |
| Regression test delta (Round 1 → Round 2) | 0 |
| Round 1 scoped pytest pass rate | 145 / 145 |
| S6-specified pytest pass rate | 33 / 33 |
| Import-linter contracts kept / broken | 2 / 0 |
| ruff errors in S6 scope | 0 |
| S6 review notes (informational) | 3 (non-blocking) |

---

## 10. Final determination (advisory)

Path 8 atomicity is **enforced** under the three most relevant failure modes.
No regressions introduced in Paths 1-7 or 9. Architectural contracts
intact.

**Advisory**: B11 re-audit Round 2 recommends FAIL-B11-8 be closed.
Final Tier 2 gate decision is reserved for D18 per the stated principle of
no self-pass.
