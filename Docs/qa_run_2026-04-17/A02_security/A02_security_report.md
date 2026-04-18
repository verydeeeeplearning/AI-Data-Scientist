# A02 - Static Security Auditor

**Tier**: 1
**Duration**: 6.4 min
**Status**: fail
**Code SHA**: nogit:BA70BF7326BCA83CC09D5B57C44EE62FFD0DC008C97B8228458BA6100B2F02A3
**Dependencies**: none

## 1. Scope
Tier 1 A02 static security audit covering:
- hard-coded secret scan in source surfaces
- code security checker blocklist and path traversal prevention
- sandbox preamble injection and runtime guard presence
- keyring chunking for Windows credential size limits
- backend Sentry redaction behavior against secret and PII payloads

## 2. Methodology
- Secret scan: rg --pcre2 across src, electron, scripts, config, README.md, pyproject.toml, .env.example, excluding tests, Docs, electron/node_modules.
- Security checker: executed pytest for test_code_security.py and exported an explicit payload matrix to A02_sandbox_blocklist.csv.
- Sandbox preamble: executed targeted sandbox integration tests and an ad-hoc build_preamble() check to confirm guard injection and placeholder removal.
- Secret storage: executed test_secret_storage.py including large-value round-trip, header-last write ordering, stale-chunk cleanup, and rollback-on-failure coverage.
- Observability: executed test_observability.py and a separate ad-hoc _deep_redact() sample with email, phone, and card-number payloads.

## 3. Results Matrix
| Check | Result | Evidence |
|---|---|---|
| Hard-coded secret scan | pass | A02_secret_scan.txt (NO_MATCHES) |
| Malicious payload blocking (os.system, subprocess.Popen, socket, traversal, eval, exec, __import__, urllib) | pass | A02_sandbox_blocklist.csv (8/8 blocked) |
| Core security/preamble/chunking regression suite | pass | junit_a02_core.xml (76 passed, 1 deselected) |
| Sandbox preamble injection present and active | pass | A02_runtime_checks.json (starts_with_guard_header=true, placeholder_removed=true) |
| Keyring chunking round-trip and rollback safety | pass | junit_a02_core.xml; source implementation at secret_storage.py lines 83, 139-174, 221-239 |
| Sentry secret token redaction | partial pass | junit_a02_core.xml; A02_runtime_checks.json shows field_token_redacted=true |
| Sentry PII redaction (email / phone / credit card) | fail | A02_runtime_checks.json shows 7 failed PII checks |

## 4. Failures and Anomalies
1. **Failing hard criterion: Sentry PII redaction is incomplete.**
   - Plan requirement: email, phone number, and credit-card-like values must be removed from event payloads.
   - Reproduction evidence: A02_runtime_checks.json retains jane.doe@example.com, +1-202-555-0199, 4111 1111 1111 1111, and 4111111111111111 in both message and extra.notes.
   - Code cause: src/ds_agent/infrastructure/observability/sentry_backend.py only redacts keys containing _SECRET_FIELD_TOKENS (line 35) and token-oriented regexes in _SECRET_PATTERNS (line 43). There is no email/phone/card regex, and field names such as customer_email are not matched by the current token list.
   - Impact: A02 pass criteria require redaction 100%; this is currently unmet, so Tier 1 A02 status is fail.

2. **Additional anomaly: sandbox ML compatibility was non-deterministic on Windows during the broad audit run.**
   - In the broad suite run recorded in junit.xml, tests/integration/infrastructure/test_subprocess_sandbox.py::TestMLCompatibility::test_pandas_read_write_cycle failed with SandboxViolation(... detail="os.open('nul', flags=2) denied") even though user code only wrote inside workspace.
   - Immediate isolated rerun in A02_additional_anomalies.txt passed.
   - Interpretation: this is not part of the A02 hard pass criteria, but it is a real flake / environment-sensitive sandbox anomaly worth triage before later-tier scenario testing.

## 5. Evidence Index
- Docs/qa_run_2026-04-17/A02_security/START.json
- Docs/qa_run_2026-04-17/A02_security/A02_secret_scan.txt
- Docs/qa_run_2026-04-17/A02_security/A02_sandbox_blocklist.csv
- Docs/qa_run_2026-04-17/A02_security/A02_runtime_checks.json
- Docs/qa_run_2026-04-17/A02_security/junit_a02_core.xml
- Docs/qa_run_2026-04-17/A02_security/junit_targeted.xml
- Docs/qa_run_2026-04-17/A02_security/junit.xml
- Docs/qa_run_2026-04-17/A02_security/A02_additional_anomalies.txt

## 6. Recommendations
- Block Tier 1 A02 sign-off until sentry_backend.py adds deterministic PII redaction for email, phone, and payment-card-like strings in free text and nested payloads.
- Add explicit unit tests for PII redaction alongside existing token-redaction tests so the plan requirement is enforced by CI.
- Investigate the Windows os.open('nul') sandbox false positive before Tier 2 and Tier 3 runtime-heavy validation, because the observed pass-on-rerun behavior suggests flakiness rather than a clean deterministic bug.
