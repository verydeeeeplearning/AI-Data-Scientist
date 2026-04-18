# S2 — PII Redaction Diff Summary

**Stream**: S2_pii_redaction (A02 Fix Sprint)
**Date**: 2026-04-17

## Changed files

| File | Kind | Description |
|------|------|-------------|
| `src/ds_agent/infrastructure/observability/sentry_backend.py` | modify | Extended `_SECRET_FIELD_TOKENS` with PII names, added typed `_SECRET_PATTERNS` (email / phone / card), typed masks (`***EMAIL***`, `***PHONE***`, `***CARD***`), Luhn validator, depth-limited `_deep_redact`, `Callable` import for helper factory. |
| `tests/unit/infrastructure/test_observability.py` | modify | Added 10 tests: 8 PII redaction scenarios + 1 existing-token regression + 1 false-positive negative test (UUID / SHA-256 / non-Luhn 16-digit counter). |

## sentry_backend.py — changes in detail

1. Added `from collections.abc import Callable` for the substitutor factory.
2. Introduced module-level constants: `_EMAIL_MASK`, `_PHONE_MASK`, `_CARD_MASK`, `_MAX_REDACT_DEPTH = 8`.
3. Extended `_SECRET_FIELD_TOKENS` with `email`, `phone`, `mobile`, `ssn`, `credit_card`, `card_number`, `pan`.
4. Changed `_SECRET_PATTERNS` shape from `tuple[re.Pattern, ...]` to `tuple[tuple[str, re.Pattern], ...]` where the leading string tags the match kind (`token`, `email`, `phone`, `card`). All existing token patterns tagged `"token"` so the legacy replace behavior is preserved byte-for-byte.
5. Added PII regexes:
   - Email: `\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b`
   - Phone: anchored alternation that requires either a leading `+` country code or parenthesized/dashed area code; refuses pure digit runs to protect UUIDs, hashes, large counters.
   - Card: `\b(?:\d[ -]?){12,18}\d\b` followed by Luhn validation in `_replace_secret_match`.
6. Added `_make_substitutor(kind)` helper to avoid untyped lambdas (mypy clean).
7. Refactored `_replace_secret_match` to dispatch on `kind` and emit typed masks; unmatched card regex hits that fail Luhn are returned unchanged (no false-positive redaction).
8. `_deep_redact` now carries a `depth` counter (default 0) with a hard cap of 8; it also handles `tuple` values (previously unhandled but reachable from Sentry `SamplingContext`-style payloads). Key lookup uses `str(key).lower()` to defend against non-string keys.

## test_observability.py — changes in detail

Added the following tests under a shared `_pii_enabled` fixture that flips `error_reporting_enabled` to `True` so `redact_backend_sentry_event` does not gate the event out:

| Test | Asserts |
|------|---------|
| `test_message_email_is_redacted` | `***EMAIL***` mask replaces `jane.doe@example.com` in `event.message` |
| `test_message_phone_is_redacted` | `***PHONE***` mask replaces `+1-202-555-0199` |
| `test_message_card_with_spaces_is_redacted` | `***CARD***` mask replaces `4111 1111 1111 1111` |
| `test_message_card_no_spaces_is_redacted` | `***CARD***` mask replaces `4111111111111111` |
| `test_extra_notes_pii_are_redacted` | All three PII types scrubbed inside `extra.notes` string |
| `test_customer_email_field_name_triggers_redaction` | Field-name token match redacts `extra.customer_email` to `***REDACTED***` |
| `test_phone_number_field_name_triggers_redaction` | Same for `extra.phone_number` |
| `test_nested_contexts_user_email_is_redacted` | Recursion reaches `contexts.user.email` |
| `test_existing_token_redaction_regression` | `sk-ant-*`, `READY:...`, and field-token redaction still work after PII extensions |
| `test_uuid_and_hash_are_not_false_positively_redacted` | UUID, SHA-256 hex, and a 16-digit non-Luhn counter are left untouched |
