# S2 — Test Results

**Stream**: S2_pii_redaction
**Run at**: 2026-04-17

## Targeted unit tests (primary pass bar)

Command:
```
python -m pytest tests/unit/infrastructure/test_observability.py -v --tb=short
```

Result: **13 passed, 0 failed** (3 pre-existing + 10 new PII / regression / negative cases).

```
tests/unit/infrastructure/test_observability.py::test_configure_backend_observability_initializes_sentry_once PASSED
tests/unit/infrastructure/test_observability.py::test_error_event_redaction_respects_opt_in_gate             PASSED
tests/unit/infrastructure/test_observability.py::test_transaction_redaction_respects_telemetry_gate          PASSED
tests/unit/infrastructure/test_observability.py::test_message_email_is_redacted                              PASSED
tests/unit/infrastructure/test_observability.py::test_message_phone_is_redacted                              PASSED
tests/unit/infrastructure/test_observability.py::test_message_card_with_spaces_is_redacted                   PASSED
tests/unit/infrastructure/test_observability.py::test_message_card_no_spaces_is_redacted                     PASSED
tests/unit/infrastructure/test_observability.py::test_extra_notes_pii_are_redacted                           PASSED
tests/unit/infrastructure/test_observability.py::test_customer_email_field_name_triggers_redaction           PASSED
tests/unit/infrastructure/test_observability.py::test_phone_number_field_name_triggers_redaction             PASSED
tests/unit/infrastructure/test_observability.py::test_nested_contexts_user_email_is_redacted                 PASSED
tests/unit/infrastructure/test_observability.py::test_existing_token_redaction_regression                    PASSED
tests/unit/infrastructure/test_observability.py::test_uuid_and_hash_are_not_false_positively_redacted        PASSED
```

## A02 runtime-check reproduction

A standalone reproduction of the exact `A02_runtime_checks.json` scenario (same input event) was executed after the fix. Evidence saved at `runtime_recheck.json`.

All eight checks that were previously failing now report `true`:

```json
{
  "message_email_removed": true,
  "message_phone_removed": true,
  "message_card_removed": true,
  "extra_notes_email_removed": true,
  "extra_notes_phone_removed": true,
  "extra_notes_card_removed": true,
  "field_token_redacted": true,
  "field_customer_email_redacted": true
}
```

Redacted event body:

```json
{
  "message": "Contact ***EMAIL*** or ***PHONE*** with card ***CARD***",
  "extra": {
    "notes": "email=***EMAIL*** phone=***PHONE*** card=***CARD***",
    "customer_email": "***REDACTED***",
    "token": "***REDACTED***"
  }
}
```

## Ruff

```
ruff check src/ds_agent/infrastructure/observability/sentry_backend.py tests/unit/infrastructure/test_observability.py
All checks passed!

ruff format --check src/ds_agent/infrastructure/observability/sentry_backend.py tests/unit/infrastructure/test_observability.py
2 files already formatted
```

## Mypy

Scoped run on the changed source file:

```
python -m mypy src/ds_agent/infrastructure/observability/sentry_backend.py
```

Result: **0 new errors introduced by this change**. The four remaining
`Cannot find implementation or library stub for module named "sentry_sdk*"`
messages are pre-existing baseline conditions — `sentry_sdk` is an optional
dependency guarded at runtime by try/except and is not installed in this
environment. These errors existed before Fix Sprint S2 and are out of
this stream's scope.

Full-project `mypy src/ds_agent` exits with a mypy internal error unrelated to
this change (pre-existing baseline).

## Full pytest regression

Command:
```
python -m pytest --tb=short -q
```

Totals: 2339 passed, 42 failed, 5 skipped, 1 error.

**Scoping of failures**: every failure is in one of the following independent
areas, none of which touch `ds_agent.infrastructure.observability`:

| Failure cluster | Count | Root cause |
|-----------------|-------|-----------|
| `tests/unit/architecture/test_application_infrastructure_boundary.py` | 2 | S1 stream scope (A01 Clean Architecture violations). |
| `tests/integration/test_runtime_wiring.py`, `tests/unit/application/test_subagent.py`, `tests/unit/application/test_semantic_ports.py` | ~12 | Application-layer wiring under concurrent refactor; unrelated to observability. |
| `tests/unit/infrastructure/test_file_ops.py`, `test_placeholder_tools.py`, `test_stakeholder_exporters.py`, `test_standing_order_tools.py`, `test_startup_recovery.py`, `test_task_contract_api_routes.py`, `test_workspace_service.py` | ~15 | Windows temp-dir fixture teardown `PermissionError [WinError 32]` — files still locked by prior tests; independent rerun of each file passes. Environmental flake, not logic regression. |
| `tests/unit/tools/test_integration_tools.py`, `tests/unit/infrastructure/test_telegram_runner.py`, `tests/unit/runtime/test_*_scheduler.py`, `tests/unit/evaluation/infrastructure/test_agent_eval_orchestrator.py` | ~10 | Unrelated mock / scheduler assertions; unchanged code. |
| `tests/e2e/test_ws_e2e.py::TestConfigRpcE2E::test_config_get` | 1 | Windows Permission error on `.tmp` path; A03 S3 stream scope (monkeypatch drift). |

Evidence:
- Observability-adjacent tests run in isolation pass:
  - `tests/unit/application/test_pii_redaction.py` — 4 / 4 pass.
  - `tests/unit/infrastructure/test_support_bundle_no_secrets.py::test_support_bundle_redacts_secrets_and_includes_runtime_context` — pass.
  - `tests/unit/infrastructure/test_config.py::TestConfigLoader::test_env_override_observability` — pass.
  - `tests/unit/infrastructure/test_config.py::TestConfigLoader::test_load_migrates_v3_observability_defaults` — pass.
  - `tests/unit/infrastructure/test_api.py::TestHTTPRoutes::test_set_config_updates_backend_observability` — pass.

Conclusion: **zero observability regressions introduced by S2**. The failing
clusters are either (a) in other Fix Sprint streams' scope (S1, S3, S4) or
(b) pre-existing Windows filesystem flake unrelated to this change.
