# A02 - Static Security Auditor (Re-Audit, Round 2)

**Tier**: 1
**Round**: 2 (post-Fix-Sprint S2)
**Status**: pass
**Baseline**: `Docs/qa_run_2026-04-17/A02_security/FINAL.json` (status=fail, 7/8 PII checks failing)
**Fix sprint input**: `Docs/qa_run_2026-04-17/S2_pii_redaction/FINAL.json` (self-reported pass; adjudicated independently here)
**Code SHA**: `nogit:C5CEB225F7C821B036DC03245FF5D625717A6D77D60FCEF7A5A9A87FBDB35C86`

## 1. Scope

Tier 1 A02 re-audit covering:
- hard-coded secret scan in source surfaces (regression check vs baseline)
- code security checker blocklist, 8-payload matrix (regression check)
- sandbox preamble injection and runtime guard presence (regression check)
- keyring chunking (regression check)
- backend Sentry redaction for **PII** — the specific failing item in baseline — and regression of existing token redaction
- false-positive negative guard (new in re-audit, verifying S2's Luhn validator)
- scope conformance: did S2 touch only `sentry_backend.py` + `test_observability.py`

## 2. Methodology

- Re-ran every A02 procedure defined in `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md §4.2 A02`.
- Secret scan: same PCRE patterns as baseline across src/, electron/, scripts/, config/, README.md, pyproject.toml, .env.example; tests/ and Docs/ excluded.
- Blocklist matrix: instantiated `CodeSecurityChecker` directly; ran 8 payloads; path-traversal via `validate_path("../../../etc/passwd")`.
- Preamble: `build_preamble()` with a synthetic `SandboxPolicy`; asserted guard header start, policy object presence, placeholder substitution, user-code presence.
- Keyring: full `tests/unit/infrastructure/test_secret_storage.py` (22 tests, includes `TestKeyringChunking` round-trip + rollback).
- Sentry redaction: rebuilt the *exact* baseline sample from `A02_runtime_checks.json` and called `redact_backend_sentry_event()` directly with the gate enabled; recorded 8 PII checks, nested `contexts.user.email`, `phone_number` field redaction, and the existing token-redaction regression test. Saved evidence to `A02_runtime_checks_reaudit.json`.
- False-positive guard: three payloads known to not be PII (UUID, SHA-256 hex, 16-digit non-Luhn counter) asserted *not* redacted.
- Scope check: filesystem `mtime` window inspection, cross-referenced with S2 CHANGELOG + DIFF_SUMMARY claims; no git, so this is the strongest independent check available.

## 3. Results Matrix

| Check | Baseline | Re-audit | Evidence |
|---|---|---|---|
| Hard-coded secret scan | pass (0 matches) | pass (0 matches) | `A02_secret_scan.txt` |
| Malicious payload blocking (8/8) | pass | pass | `A02_sandbox_blocklist.csv` |
| Core security/preamble/chunking regression suite | 76 passed, 1 deselected | 87 passed, 0 failed | `junit_a02_core_full.xml` |
| Sandbox preamble injection present and active | pass | pass | `A02_runtime_checks_reaudit.json` |
| Keyring chunking round-trip and rollback safety | pass | pass | `junit_secret_storage.xml` (22/22) |
| Sentry secret token redaction | pass | pass (no regression) | `junit_observability.xml`; `A02_runtime_checks_reaudit.json` field_token_redacted=true |
| Sentry PII redaction (email / phone / card, msg + extra.notes) | **fail (7/8)** | **pass (8/8)** | `A02_runtime_checks_reaudit.json`; `junit_observability.xml` |
| Nested `contexts.user.email` redacted | n/a (baseline did not test) | pass | `A02_runtime_checks_reaudit.json`; `junit_observability.xml::test_nested_contexts_user_email_is_redacted` |
| `phone_number` field-name redacted | n/a (baseline did not test) | pass | `A02_runtime_checks_reaudit.json`; `junit_observability.xml::test_phone_number_field_name_triggers_redaction` |
| False-positive guard (UUID / SHA-256 / non-Luhn 16-digit) not redacted | n/a | pass (3/3) | `A02_runtime_checks_reaudit.json::false_positive_checks` |
| PII-redaction application layer (`tests/unit/application/test_pii_redaction.py`) | not in baseline | pass (4/4) | `junit_pii_redaction_app.xml` |

## 4. Delta from Baseline

### 4.1 PII check key-by-key diff (`sentry_pii_redacted`)

| Key | Baseline | Re-audit | Status |
|---|---|---|---|
| `message_email_removed` | false | true | **RESOLVED** |
| `message_phone_removed` | false | true | **RESOLVED** |
| `message_card_removed` | false | true | **RESOLVED** |
| `extra_notes_email_removed` | false | true | **RESOLVED** |
| `extra_notes_phone_removed` | false | true | **RESOLVED** |
| `extra_notes_card_removed` | false | true | **RESOLVED** |
| `field_token_redacted` | true | true | unchanged (no regression) |
| `field_customer_email_redacted` | false | true | **RESOLVED** |

**Prior failures resolved: 7 / 7**. Remaining failures: 0.

### 4.2 Preamble checks key-by-key diff

All five keys unchanged from baseline (`starts_with_guard_header=true`, `contains_policy_object=true`, `placeholder_removed=true`, `user_code_present=true`, `commented_policy_guard_found=false`). No regression.

### 4.3 Baseline advisory anomaly — Windows `os.open('nul')` flake

Baseline noted a non-deterministic failure of `tests/integration/infrastructure/test_subprocess_sandbox.py::TestMLCompatibility::test_pandas_read_write_cycle` in a broad run; an isolated rerun passed. Re-audit rerun also **passes** (1.59s). Still advisory — the failure mode is environmental and not reproducible here.

## 5. Scope Conformance

S2 claims in `FINAL.json`: modified only `src/ds_agent/infrastructure/observability/sentry_backend.py` and `tests/unit/infrastructure/test_observability.py`.

Independent verification (no git, so `mtime` + content inspection):
- `sentry_backend.py` mtime 2026-04-16T19:23:53Z; `test_observability.py` mtime 2026-04-16T19:23:32Z — both inside S2's 19:21–19:45 UTC window (display offset between CLAUDE.md "today" and local filesystem noted).
- All other files modified in that window (learning_tools, portfolio_tools, application/ports/\*, services/\*, scheduler_service, reproducibility_exporter, infrastructure/migration, learning_store, agent/factory, tests/unit/runtime/\*, tests/e2e/\*, tests/integration/infrastructure/\*, tests/unit/architecture/\*, scripts/check_import_contracts) are attributable to the parallel S1/S3/S4 streams, each with its own FINAL.json and DIFF_SUMMARY — not S2.
- Current `sentry_backend.py` content matches S2 CHANGELOG's claimed additions byte-for-byte (`_EMAIL_MASK`, `_PHONE_MASK`, `_CARD_MASK`, `_MAX_REDACT_DEPTH`, extended `_SECRET_FIELD_TOKENS`, `(kind, regex)` pattern tuple, `_luhn_valid`, `_make_substitutor`, `Callable` import).
- No other file under `src/ds_agent/infrastructure/observability/` nor any application-layer redaction hook file was modified by S2.

**Scope respected: yes.**

## 6. Evidence Index

- `Docs/qa_run_2026-04-17/A02_security_reaudit/START.json`
- `Docs/qa_run_2026-04-17/A02_security_reaudit/A02_secret_scan.txt`
- `Docs/qa_run_2026-04-17/A02_security_reaudit/A02_sandbox_blocklist.csv`
- `Docs/qa_run_2026-04-17/A02_security_reaudit/A02_runtime_checks_reaudit.json`
- `Docs/qa_run_2026-04-17/A02_security_reaudit/junit_code_security.xml` (38 passed)
- `Docs/qa_run_2026-04-17/A02_security_reaudit/junit_secret_storage.xml` (22 passed)
- `Docs/qa_run_2026-04-17/A02_security_reaudit/junit_observability.xml` (13 passed)
- `Docs/qa_run_2026-04-17/A02_security_reaudit/junit_pii_redaction_app.xml` (4 passed)
- `Docs/qa_run_2026-04-17/A02_security_reaudit/junit_a02_core.xml` (77 passed — core + app PII)
- `Docs/qa_run_2026-04-17/A02_security_reaudit/junit_a02_core_full.xml` (87 passed — core + integration sandbox)
- `Docs/qa_run_2026-04-17/A02_security_reaudit/junit_sandbox_flake_check.xml` (1 passed — flake recheck)

## 7. Conclusion & Recommendation

- All 7 previously-failing PII redaction checks are resolved.
- No regressions in the previously-passing areas (secret scan, sandbox blocklist, preamble, keyring chunking, token redaction).
- False-positive negative guard confirms S2's Luhn validator correctly skips UUIDs, SHA-256 hashes, and non-card 16-digit counters.
- Scope was respected: S2 modified only the two declared files.
- The Windows `os.open('nul')` sandbox flake remains advisory; it did not reproduce in re-audit.

**Recommendation: A02 Tier 1 gate passes.** Proceed with Tier 1 release readiness.
