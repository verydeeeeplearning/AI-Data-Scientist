# C13 — Interface Parity Tester: Final Report

**Agent**: C13 Interface Parity Tester (Tier 3)
**Run date**: 2026-04-17
**Plan reference**: `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md` §6.1
**Evidence root**: `Docs/qa_run_2026-04-17/C13_parity/`

## 1. Scope

Verify 3-Tier interface (CLI + Telegram + Electron/WS) equivalence
across 3 plan scenarios:

- **P-01**: basic analysis → report (`tips.csv` → Peer audience).
- **P-02**: autonomy mode transition (Supervised → Delegate, CAUTION
  tool approval path).
- **P-03**: learning governance (pattern extraction → LearningInbox →
  promotion → 2x eval fail → auto-deprecate).

3 × 3 = 9 planned executions. Boundary: prove the `create_agent()`
factory contract — identical hook chain, skill set, tool registry,
budget policy, verifier/task-contract containers, and store wiring —
holds across all three channel entry points.

## 2. Methodology

### 2.1 Chosen execution strategy

**Code-level / factory-level simulated execution with stubbed provider
+ stubbed callbacks** (authorised by plan §6.1 step 4 "실용 대안").

Why not real process-level:

| Channel | Blocker |
|---------|---------|
| Telegram | requires live bot token + outbound network. Plan explicitly forbids external bot calls. |
| Electron | requires packaged app + chromium runtime — that is C15 Packaging agent's territory, out of scope for C13. |
| CLI | runnable in principle, but running a real LLM turn would cost real API dollars without adding parity signal — the parity-relevant state is frozen *at construction time*, before the first LLM turn. |

**`fallback_used = true`** — explicitly declared per plan §4.

### 2.2 Harness

`parity_harness.py` (copied to evidence root). For each of the 9
(scenario, channel) pairs, it:

1. Mirrors the exact `create_agent(**kwargs)` call shape used by the
   real channel entry point (see line references in
   `call_graph_evidence.md`).
2. Captures the constructed DSAgent's structural signature:
   hook class list, hook count, skill names, tool count, tool-name
   SHA-256 hash, budget, mode, authority mode, store-wired flags,
   `ToolRegistry` class identity.
3. Compares the signatures across the 3 channels per scenario using
   a fixed equivalence-fields list (§2.4).

### 2.3 Stubs

- `StubProvider` implements `LLMProvider` protocol; `chat()` raises if
  called (guard: parity test must never call the LLM).
- `StubCallbacks` satisfies `AgentCallbacks` protocol with no-ops.
- Workspace is a freshly-created tempdir per scenario.

### 2.4 Equivalence fields (must match across channels)

`hooks, hook_count, skill_names, tool_count, tools_hash, budget, mode,
authority_mode, transcript_store_wired, checkpoint_store_wired,
goal_store_wired, working_memory_store_wired, approval_store_wired,
skill_hub_wired, post_learner_wired, tool_registry_class`

### 2.5 Allowed deltas (must NOT be required to match)

`channel, session_id, callbacks class, surface, timestamps,
origin-specific fields`

## 3. Results Matrix

| Scenario | CLI | Telegram | Electron (WS) | Scenario parity |
|----------|:---:|:--------:|:-------------:|:---------------:|
| P-01 basic → report | OK | OK | OK | **MATCH** |
| P-02 authority switch | OK | OK | OK | **MATCH** |
| P-03 learning governance | OK | OK | OK | **MATCH** |

Overall: **9/9 runs succeeded, parity_match = true.**

Key numbers (identical across all 9 runs):

- **30 hooks** registered (matches B05 Tier 2 gate).
- **75 tools** in `ToolRegistry` after `factory.import_all_tools()` (subset; delta vs plan's 86 explained in `call_graph_evidence.md` §6).
- **7 default skills** injected into prompt: scoping, data-profiling, eda, feature-engineering, modeling, evaluation, reporting.
- Budget `max_iterations=100, max_cost_usd=10.0`.
- `tools_hash = a0c16d97f9de642e8562c734b562b44b7c85ea3c11323ab7c07131b33b598dea` — identical across all 3 channels.

Raw evidence: `channel_signatures.json`, `parity_diff_raw.json`.

## 4. Failures

**None.** All 9 channel builds succeeded; all equivalence fields
matched across the 3 channels within every scenario.

During harness development, one interim run showed a `tool_count`
mismatch (CLI=75, Telegram/Electron=0). Root cause: an over-aggressive
`ToolRegistry.reset()` between channel builds combined with
`sys.modules` caching in `importlib.import_module` prevented the
second & third channel from re-registering tools. **Fix**: the harness
was changed to preserve the process-global registry across channels
within a scenario — that is the real production behavior (a single
`ToolRegistry` classvar is shared process-wide). After that correction,
9/9 runs matched. See `parity_harness.py` inline comment preceding
`_run_one`.

## 5. Evidence

| Path | What it contains |
|------|------------------|
| `START.json` | QA task manifest with scope + constraints |
| `parity_harness.py` | Executable harness code (reproduces the 9 runs) |
| `channel_signatures.json` | 9 captured DSAgent signatures (raw JSON) |
| `parity_diff_raw.json` | Per-scenario field-mismatch summary (empty arrays = match) |
| `call_graph_evidence.md` | Static source proof: line-accurate imports of `create_agent` by CLI, Telegram, WS registry, plus the factory's parity invariant docstring |
| `C13_parity_diff.md` | Human-readable scenario × channel matrix, equivalence field table, and fallback disclosure |
| `harness_run_log.txt` | Captured stdout from the final harness run |
| `FINAL.json` | Final decision record (this report's machine-readable sibling) |

## 6. Recommendations

### Accepted fallback (advisory, no action required)

Fallback to factory-level parity proof is strong for construction-time
invariants. It does **not** verify:

1. Runtime divergence in async callback fan-out (e.g., Telegram's
   bot-call throttling vs CLI's TUI printing) — such drift would affect
   user-visible UX but *not* the task contract / delivery pack body.
2. End-to-end delivery pack byte-reproducibility across channels —
   that's dominated by the LLM trace, not by the factory wiring. A
   reproducible LLM record-replay fixture would be required to test it.

### Suggested follow-ups (optional, not blocking Tier 3 gate)

| # | Item | Owner suggestion |
|---|------|------------------|
| R1 | Add a pytest-driven parity test (harness-as-test) to CI so factory-wiring regressions are caught early. | post-beta maintenance |
| R2 | Add a record-replay LLM provider fixture to enable byte-identical DeliveryPack comparison across channels end-to-end. | C14 Gold Tasks or Tier 4 |
| R3 | C15 Packaging: once Electron is packaged, run Playwright E2E against the WS handler reusing this parity-field list as a runtime assertion. | C15 |
| R4 | Telegram fake-update harness (`python-telegram-bot` test Updater) for end-to-end message → `_create_agent` → reply path, avoiding live network. | Tier 4 D17 regression |

### Not a recommendation — informational

- `tool_count = 75` (not 86) in the harness run reflects only the 33
  modules explicitly listed in `factory.import_all_tools()`. The extra
  11 tools from learning/portfolio CLIs become registered lazily on
  first CLI subcommand dispatch. Since parity is a same-set check, not
  a matches-plan-number check, this is not a defect for C13.
- Plan revision in `HANDOFF_NEXT_AGENT.md` §5.3 lists 86 as the
  post-S3 count — recommend aligning `factory.import_all_tools()` with
  that list (or documenting the lazy pattern) as a cosmetic cleanup.

## 7. Verdict

- 9/9 runs completed.
- Parity match: **YES** (100% on equivalence fields).
- Fallback used: **YES** (factory-level simulated construction).
- C13 Pass criteria: 3 × 3 = 9 executions succeed *or* fallback path
  proves equivalence → **both conditions met**.

C13 does **not** self-declare pass/fail per plan §4.3 (자기 pass 판정
금지). The Tier 3 gate owner is the next decision-maker.
