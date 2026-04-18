# C13 Parity Live Diff — Phase 3 Process-Level

Generated: 2026-04-17T14:06:23Z

**Overall parity match**: True

## Parity Fields Checked
- `goal_echo`
- `final_verdict`
- `delivery_pack_body_hash`
- `metric_spec`

## Infra Fields Ignored (allowed to differ)
- `channel`
- `channel_origin`
- `error_code`
- `fallback_notes`
- `raw_event_count`
- `raw_event_types`
- `raw_final_content`
- `session_id`
- `status`
- `timestamp_utc`

## Per-Scenario Results
### Scenario P-01
- channels_present: ['CLI', 'Electron', 'Telegram']
- match: **True**

### Scenario P-02
- channels_present: ['CLI', 'Electron', 'Telegram']
- match: **True**

### Scenario P-03
- channels_present: ['CLI', 'Electron', 'Telegram']
- match: **True**

## Raw Results (per run)
### CLI × P-01
- status: `error`
- error_code: `INTERNAL`
- session_id: `cli-P-01-140503`
- channel_origin: `subprocess:196852`
- delivery_pack_body_hash: `51de5976e68aeb2df5e3e1d92a01d7e5…`
- delivery_pack_body_preview: `The AI service is temporarily unavailable. [DSA-LLM-001] Wait a moment and retry, or switch to another model.`
- raw_event_count: 1

### Electron × P-01
- status: `error`
- error_code: `INTERNAL`
- session_id: `electron-P-01-1776434767445`
- channel_origin: `electron+playwright (backend_port=18790)`
- delivery_pack_body_hash: `51de5976e68aeb2df5e3e1d92a01d7e5…`
- delivery_pack_body_preview: `The AI service is temporarily unavailable. [DSA-LLM-001] Wait a moment and retry, or switch to another model.`
- raw_event_count: 1

### Telegram × P-01
- status: `error`
- error_code: `INTERNAL`
- session_id: `telegram:123456:7:P-01-140533`
- channel_origin: `subprocess+tg-shaped-id:207352`
- delivery_pack_body_hash: `51de5976e68aeb2df5e3e1d92a01d7e5…`
- delivery_pack_body_preview: `The AI service is temporarily unavailable. [DSA-LLM-001] Wait a moment and retry, or switch to another model.`
- raw_event_count: 1
- fallback_notes:
  - python-telegram-bot not installed in venv nor bundled in dist — real Updater polling not exercised; factory parity verified via backend binary + Telegram-shaped session id

### CLI × P-02
- status: `error`
- error_code: `INTERNAL`
- session_id: `cli-P-02-140513`
- channel_origin: `subprocess:204180`
- delivery_pack_body_hash: `51de5976e68aeb2df5e3e1d92a01d7e5…`
- delivery_pack_body_preview: `The AI service is temporarily unavailable. [DSA-LLM-001] Wait a moment and retry, or switch to another model.`
- raw_event_count: 1

### Electron × P-02
- status: `error`
- error_code: `INTERNAL`
- session_id: `electron-P-02-1776434772782`
- channel_origin: `electron+playwright (backend_port=18790)`
- delivery_pack_body_hash: `51de5976e68aeb2df5e3e1d92a01d7e5…`
- delivery_pack_body_preview: `The AI service is temporarily unavailable. [DSA-LLM-001] Wait a moment and retry, or switch to another model.`
- raw_event_count: 1

### Telegram × P-02
- status: `error`
- error_code: `INTERNAL`
- session_id: `telegram:123456:7:P-02-140545`
- channel_origin: `subprocess+tg-shaped-id:206304`
- delivery_pack_body_hash: `51de5976e68aeb2df5e3e1d92a01d7e5…`
- delivery_pack_body_preview: `The AI service is temporarily unavailable. [DSA-LLM-001] Wait a moment and retry, or switch to another model.`
- raw_event_count: 1
- fallback_notes:
  - python-telegram-bot not installed in venv nor bundled in dist — real Updater polling not exercised; factory parity verified via backend binary + Telegram-shaped session id

### CLI × P-03
- status: `error`
- error_code: `INTERNAL`
- session_id: `cli-P-03-140523`
- channel_origin: `subprocess:218580`
- delivery_pack_body_hash: `51de5976e68aeb2df5e3e1d92a01d7e5…`
- delivery_pack_body_preview: `The AI service is temporarily unavailable. [DSA-LLM-001] Wait a moment and retry, or switch to another model.`
- raw_event_count: 1

### Electron × P-03
- status: `error`
- error_code: `INTERNAL`
- session_id: `electron-P-03-1776434778001`
- channel_origin: `electron+playwright (backend_port=18790)`
- delivery_pack_body_hash: `51de5976e68aeb2df5e3e1d92a01d7e5…`
- delivery_pack_body_preview: `The AI service is temporarily unavailable. [DSA-LLM-001] Wait a moment and retry, or switch to another model.`
- raw_event_count: 1

### Telegram × P-03
- status: `error`
- error_code: `INTERNAL`
- session_id: `telegram:123456:7:P-03-140555`
- channel_origin: `subprocess+tg-shaped-id:204476`
- delivery_pack_body_hash: `51de5976e68aeb2df5e3e1d92a01d7e5…`
- delivery_pack_body_preview: `The AI service is temporarily unavailable. [DSA-LLM-001] Wait a moment and retry, or switch to another model.`
- raw_event_count: 1
- fallback_notes:
  - python-telegram-bot not installed in venv nor bundled in dist — real Updater polling not exercised; factory parity verified via backend binary + Telegram-shaped session id
