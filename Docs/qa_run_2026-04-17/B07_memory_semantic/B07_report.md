# B07 Memory & Semantic Tester — Report

**Agent**: B07 Memory & Semantic Tester
**Tier**: 2 (Feature Behavior)
**Date**: 2026-04-17
**Code SHA**: `git-unavailable` (repo is not a git checkout)
**Self pass/fail judgment**: Not rendered. Per §4.5 and the B07 prompt, Tier 3 judges this tier — this report is evidence only.

---

## 1. Scope

- 5-layer memory stack (SESSION / PROJECT / DOMAIN / GLOBAL via `MemoryType` enum; physical stores: `ExperimentLog`, `CodeRegistry`, `DomainKB`, `ProjectStore`, `UnifiedMemoryStore`).
- Semantic memory surface (`src/ds_agent/memory/semantic/`: domain entities `Metric`, `GlossaryTerm`, `TableTrust`, `VerifiedQuery`, `SemanticProposal`; application use cases; SQLite repositories).
- Semantic proposal lifecycle (submit → review(approve|reject) → apply).
- `MemoryQueryService` orchestration (semantic-first → domain_kb fallback, dual-write).
- `SemanticReadGuardHook` + `SemanticTrustHook` enforcement.
- `VerifiedQueryStore` injection via `FindVerifiedQueryUseCase`.

Out of scope: v13 migration correctness (owned by S4/A04), tool-registry wiring (B06), hook chain fire matrix (B05).

## 2. Method

1. Scope-isolated pytest run across `tests/unit/domain/test_semantic_*`, `tests/unit/application/test_*semantic*`, `tests/unit/application/test_apply_semantic_proposal.py`, `tests/unit/application/test_check_table_trust.py`, `tests/unit/application/test_find_verified_query.py`, `tests/unit/application/test_resolve_metric.py`, `tests/unit/application/test_record_negative_knowledge.py`, `tests/unit/application/test_load_semantic_pack.py`, `tests/unit/application/test_review_semantic_proposal.py`, `tests/unit/application/test_submit_semantic_proposal.py`, `tests/unit/application/test_sync_semantic_source.py`, `tests/unit/architecture/test_semantic_layer_deps.py`, `tests/integration/semantic/`, `tests/integration/test_memory_modules.py`, `tests/integration/test_unified_memory_integration.py`, `tests/integration/application/test_sync_semantic_source.py`, `tests/integration/runtime/test_semantic_proposal_approval.py`, `tests/integration/tools/test_semantic_query.py`.
   - Command: `pytest <scope> -v --tb=short --junitxml=.tmp/qa_B07/junit.xml`
   - Result: **88 passed, 1 failed** in 8.09 s. The only failure is `tests/unit/application/test_semantic_ports.py::test_semantic_ports_are_runtime_checkable` (explicitly catalogued as **PRE-1** in `HANDOFF §4.6` / `§7`; confirmed not a B07-scope regression).
   - Evidence: `B07_pytest_junit.xml`.
2. Behaviour probe (`.tmp/qa_B07/probe.py`) that exercises the 7 paths from §5.3 against real SQLite repositories and real hook classes. The probe writes to tempdirs only (no `data/` touched). Results captured in `B07_path_results.json`.
3. Fixture corpus of 100 session transcripts (5 clusters of 20 entries each: EN churn, KR 이탈률, EN LTV, KR 매출, noise) loaded into an isolated `UnifiedMemoryStore` for FTS5 precision measurement. Per-query hits persisted to `B07_fts5_precision.csv`.
4. Semantic proposal lifecycle trace persisted line-by-line to `B07_semantic_proposal_trace.jsonl` for dual-write and approve/reject events.

No source files were modified. No `data/` artifacts were touched. No external adapters were called (all repositories were SQLite-in-tempdir; `SemanticReadGuardHook` and `SemanticTrustHook` were exercised with in-process fakes).

## 3. 7-Path Results

| # | Path | Result | Evidence |
|:-:|------|:------:|---------|
| 1 | FTS5 full-text search (KR/EN) | **pass** — mean precision@10 = 1.0 across 8 fixture queries | `B07_fts5_precision.csv`, `B07_path_results.json:path1_fts5_precision` |
| 2 | `MemoryQueryService.search("churn", memory_type="all")` aggregates experiments + code_patterns + domain_knowledge + projects in one call | **pass** — all 4 result types observed in a single response | `B07_path_results.json:path2_unified_aggregate` |
| 3 | Semantic-first + domain_kb fallback on `customer_ltv` | **pass** — `source=semantic_memory` when metric repo returns a match; `source=domain_kb_legacy` when metric repo returns empty | `B07_path_results.json:path3_semantic_first_fallback` |
| 4 | Dual-write: `store(domain_knowledge, ...)` writes domain_kb + queues semantic proposal | **pass** — `domain_kb_delta=1`, `pending_delta=1`, proposal id `SP-auto-*` persisted | `B07_semantic_proposal_trace.jsonl` line 1, `B07_path_results.json:path4_dual_write` |
| 5 | Semantic proposal approve → apply reaches metric catalog | **pass** — `ReviewSemanticProposalUseCase(action="approve")` sets status `approved`; `ApplySemanticProposalUseCase` persists `roi_ads` alias onto `ROAS` metric (synonyms = `["roas", "roi_ads"]`); reject path sets status `rejected` | `B07_semantic_proposal_trace.jsonl` lines 2-3, `B07_path_results.json:path5_semantic_proposal_approve` |
| 6 | `DataTrustRegistry` / `SemanticReadGuardHook` / `SemanticTrustHook` enforcement | **pass** — metric-like sql_query without semantic grounding emits `harness.warning` (type=`semantic_read_guard`) and post-tool-use appends `Semantic memory warning`; `UNTRUSTED`-grade table triggers `HookAction.DENY` with deny_reason including the FQTN and `untrusted table referenced` warning | `B07_path_results.json:path6_data_trust_registry` |
| 7 | `VerifiedQueryStore` — verified SQL injected when available | **pass** — `FindVerifiedQueryUseCase.execute(metric_id="monthly_churn_rate")` returns the stored VQ with placeholders bound (`{{start_date}}`/`{{end_date}}` replaced, `fact_customer_activity` preserved in rendered SQL); non-existent metric returns empty `VerifiedQueryResultDTO` (no phantom injection) | `B07_path_results.json:path7_verified_query_store` |

**Summary: 7/7 paths verified.**

## 4. FTS5 Precision

Fixture: 100 session transcripts (5 clusters × 20). Queries and precision@10:

| Query | Expected cluster | returned | correct | precision@10 |
|-------|------------------|:-------:|:-------:|:-----------:|
| `churn` (EN) | tx-churn- | 10 | 10 | 1.00 |
| `retention cohort` (EN) | tx-churn- | 10 | 10 | 1.00 |
| `이탈률` (KR) | tx-ital- | 10 | 10 | 1.00 |
| `고객 이탈률` (KR) | tx-ital- | 10 | 10 | 1.00 |
| `LTV` (EN) | tx-ltv- | 10 | 10 | 1.00 |
| `lifetime value` (EN) | tx-ltv- | 10 | 10 | 1.00 |
| `매출` (KR) | tx-maeul- | 10 | 10 | 1.00 |
| `분기별 매출` (KR) | tx-maeul- | 10 | 10 | 1.00 |

**Mean precision@10 = 1.00**, clears the Pass bar of ≥0.80 on the fixed fixture.

Notes:
- Query planner wraps each whitespace-split term with quotes and joins with `OR` (see `UnifiedMemoryStore._prepare_fts_query`). This explains why `retention cohort` returns the churn cluster: all churn transcripts contain "Retention cohort investigation" in the `i % 3 == 0` branch and the general "Customer attrition" / "Retention" vocabulary.
- Korean queries succeed on default FTS5 tokenizer because our fixture is whitespace-separated. Real production corpus may exhibit lower recall on agglutinated Korean without an ICU/Unicode61 tokenizer configured; flagging as observational, not scope-failing (fixture-level precision pass is the stated contract).

## 5. Pytest Delta

- Collected: 89.
- Passed: 88.
- Failed: 1 (`test_semantic_ports_are_runtime_checkable` — `ExternalSemanticSource` runtime_checkable protocol fails `isinstance` on a stub lacking the `name` class attribute).
- **Classification**: pre-existing (matches HANDOFF §4.6 / PRE-1). Not introduced by Fix Sprint S1/S5 or B07 scope. Recommended for "별도 유지보수 스프린트" tracking.
- New regressions: **0**.

## 6. Clean Architecture Observations (informational only)

- `tests/unit/architecture/test_semantic_layer_deps.py` passes: semantic domain has no forbidden imports; semantic application has no infrastructure imports.
- `MemoryQueryService._submit_semantic_candidate` catches all exceptions and swallows them — intentional (dual-write failure is non-fatal) but also means silent proposal loss if the SQLite repo is down. Not a B07 pass/fail signal; noted for post-beta reliability review.
- `MemoryQueryService.from_workspace` uses `contextlib.suppress(Exception)` around semantic infra construction. Fallback semantics are explicit (workspaces without semantic DB still work), but failed construction silently proceeds without warning — observational.

## 7. Pre-existing / RC-list

| ID | Description | Source of record | B07 treatment |
|----|-------------|------------------|---------------|
| PRE-1 | `test_semantic_ports_are_runtime_checkable` fails — `ExternalSemanticSource` protocol can't runtime-check stub without `name` attribute | HANDOFF §4.6 / §7 | **Observed, not blocking this tier.** Distinct from B07 7-path contract. |

No new RC items introduced by B07.

## 8. Pass Criteria Audit

- 7/7 paths verified with positive evidence. ✔
- FTS5 precision@10 = 1.00 ≥ 0.80 on the fixed fixture. ✔
- Scope-isolated pytest: 88/89 pass, sole failure is PRE-1. ✔
- No source modification. ✔
- No external adapter calls. ✔
- `data/` untouched (all work in tempdirs under `.tmp/qa_B07/` and `%TEMP%/b07_p*_*`). ✔

## 9. Artifacts

| File | Description |
|------|-------------|
| `START.json` | agent + scope marker |
| `FINAL.json` | per-tier final signal |
| `B07_report.md` | this document |
| `B07_fts5_precision.csv` | 8 fixture queries × precision@10 |
| `B07_semantic_proposal_trace.jsonl` | dual-write + approve/reject event trace |
| `B07_path_results.json` | per-path machine-readable verdicts |
| `B07_pytest_junit.xml` | scope-isolated pytest junit output |

## 10. Recommendation

- **Proceed to Tier 3.** 7 paths verified, FTS5 precision clears the bar, no new regressions. Sole test failure is PRE-1 (already catalogued).
- Tier 3 judge should cross-check that B08 (verifier) and B11 (learning governance) don't regress semantic proposal apply-path. In particular, the `NEGATIVE_KNOWLEDGE` dual-write proposal emitted by `MemoryQueryService._submit_semantic_candidate` constructs a `SemanticProposal` with `payload` carrying raw `{content, source_domain, source_tags}` — this payload is **not** a valid `NegativeKnowledge` entity and will fail `ApplySemanticProposalUseCase.execute` if ever auto-applied (caught because `auto_apply_eligible=False` and approver would have to manually escalate). Calling this out as an **informational risk**, not a B07 failure: the happy-path 7-path contract does not require auto-apply of dual-write proposals, and the submit+queue behaviour was verified in path 4. Recommend post-beta tightening of the dual-write payload schema so an approver-initiated apply doesn't raise.
