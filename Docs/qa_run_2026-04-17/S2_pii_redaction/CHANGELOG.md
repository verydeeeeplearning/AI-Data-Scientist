# S2 — CHANGELOG

## 2026-04-17

- 19:21 UTC — START.json recorded; inputs hashed
  (`A02_security_report.md` sha256 `e0933fa6...f88c`,
  `A02_runtime_checks.json` sha256 `76c1b480...72c3`).
- RED: added 10 tests to `tests/unit/infrastructure/test_observability.py`
  covering 8 PII scenarios (email / phone / card with & without spaces,
  extra.notes aggregate, field-name match on `customer_email` and
  `phone_number`, nested `contexts.user.email`), 1 existing-token
  regression guard, and 1 false-positive negative test (UUID, SHA-256 hex,
  non-Luhn 16-digit counter). Initial run: 8 failed, 5 passed (expected RED).
- GREEN:
  - Extended `_SECRET_FIELD_TOKENS` with `email`, `phone`, `mobile`,
    `ssn`, `credit_card`, `card_number`, `pan`.
  - Reshaped `_SECRET_PATTERNS` to `(kind, regex)` tuples and added
    email / phone / card regexes. Preserved all legacy token patterns
    under `kind="token"` so existing redaction behavior is byte-identical.
  - Introduced typed masks `***EMAIL***`, `***PHONE***`, `***CARD***`
    and a Luhn validator to suppress false positives on 16-digit
    non-card numerics (UUID fragments, hashes, counters).
  - `_deep_redact` now depth-limited (max 8), handles `tuple` values,
    and defends against non-string keys by coercing with `str(key)`.
  - Added `_make_substitutor(kind)` to avoid an untyped lambda and
    satisfy mypy.
  - Added `from collections.abc import Callable`.
- Verification:
  - `pytest tests/unit/infrastructure/test_observability.py -v` —
    13 / 13 pass.
  - Ad-hoc reproduction of the exact `A02_runtime_checks.json` sample —
    all 8 PII checks now `true`; evidence saved at `runtime_recheck.json`.
  - `ruff check` + `ruff format --check` — clean for both changed files.
  - `mypy` on the changed file — 0 new errors introduced; pre-existing
    `sentry_sdk` stub-not-found warnings are baseline (optional dep).
  - Full `pytest` — 2339 pass, 42 fail. Every failure is in an unrelated
    cluster (other Fix Sprint streams or Windows temp-dir fixture flake);
    adjacent observability / redaction tests pass in isolation.
- FINAL.json written.
