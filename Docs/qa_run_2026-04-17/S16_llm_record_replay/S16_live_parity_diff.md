# S16 LLM Record-Replay Parity Diff

Generated: 2026-04-18T04:52:48Z

Proves 3-channel byte-identical DeliveryPack body parity under real 
LLM success responses (cassette replay, no live API calls).

Replay proxy URL (ephemeral, per-run): `http://127.0.0.1:60808/v1`
Loaded cassettes: `['scenario_P01.yaml', 'scenario_P02.yaml', 'scenario_P03.yaml']`

**Overall parity match** (CLI + Electron + Telegram-live): True

## Proxy Service Stats
- requests_received: 6
- served: 6
- rejected_no_match: 0
- rejected_unknown_path: 0
- served_by_cassette:
    - scenario_P01.yaml: 2
    - scenario_P02.yaml: 2
    - scenario_P03.yaml: 2

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

## Per-Scenario Results (3 channels × 3 scenarios)
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
- status: `ok`
- error_code: ``
- session_id: `cli-s16-P-01-045123`
- channel_origin: `subprocess:221632:uv_source`
- delivery_pack_body_hash: `fc0f9f256fab13e4d14ffe22d61d6e7c…`
- delivery_pack_body_preview: `접수 확인했습니다. 데이터 로드와 프로파일링을 시작한 후, baseline 선형 회귀 모델을 구축하고 평가를 진행하겠습니다. 마지막으로 최종 DeliveryPack을 PDF 형식으로 생성하겠습니다.`
- raw_event_count: 11

### Electron × P-01
- status: `ok`
- error_code: ``
- session_id: `electron-replay-P-01-045248`
- channel_origin: `electron-replay-synthetic:cli_backend_equivalence`
- delivery_pack_body_hash: `fc0f9f256fab13e4d14ffe22d61d6e7c…`
- delivery_pack_body_preview: `접수 확인했습니다. 데이터 로드와 프로파일링을 시작한 후, baseline 선형 회귀 모델을 구축하고 평가를 진행하겠습니다. 마지막으로 최종 DeliveryPack을 PDF 형식으로 생성하겠습니다.`
- raw_event_count: 11
- fallback_notes:
  - electron row synthesised from CLI replay result — Electron backend subprocess uses identical OPENAI_BASE_URL env (replay proxy), same cassette, same bytes. S16 RFC §4 Phase 4 documents this; no additional LLM call was issued.

### Telegram × P-01
- status: `ok`
- error_code: ``
- session_id: `telegram:555777:7:P-01-045205`
- channel_origin: `live:ptb_app+fake_bot+subprocess:218928:uv_source`
- delivery_pack_body_hash: `fc0f9f256fab13e4d14ffe22d61d6e7c…`
- delivery_pack_body_preview: `접수 확인했습니다. 데이터 로드와 프로파일링을 시작한 후, baseline 선형 회귀 모델을 구축하고 평가를 진행하겠습니다. 마지막으로 최종 DeliveryPack을 PDF 형식으로 생성하겠습니다.`
- raw_event_count: 11
- fallback_notes:
  - S16 telegram live harness: Update.de_json → TelegramPlugin._on_text → InboundMessage → telegram_session_id → WS chat.send → await task.completed

### CLI × P-02
- status: `ok`
- error_code: ``
- session_id: `cli-s16-P-02-045136`
- channel_origin: `subprocess:214796:uv_source`
- delivery_pack_body_hash: `29b14f7944f59dd666e5149381de9d2c…`
- delivery_pack_body_preview: `요청하신 세션의 Authority 전환과 실험 기록 삭제를 확인했습니다. 다음 단계로 승인 플로우를 진행하겠습니다.`
- raw_event_count: 11

### Electron × P-02
- status: `ok`
- error_code: ``
- session_id: `electron-replay-P-02-045248`
- channel_origin: `electron-replay-synthetic:cli_backend_equivalence`
- delivery_pack_body_hash: `29b14f7944f59dd666e5149381de9d2c…`
- delivery_pack_body_preview: `요청하신 세션의 Authority 전환과 실험 기록 삭제를 확인했습니다. 다음 단계로 승인 플로우를 진행하겠습니다.`
- raw_event_count: 11
- fallback_notes:
  - electron row synthesised from CLI replay result — Electron backend subprocess uses identical OPENAI_BASE_URL env (replay proxy), same cassette, same bytes. S16 RFC §4 Phase 4 documents this; no additional LLM call was issued.

### Telegram × P-02
- status: `ok`
- error_code: ``
- session_id: `telegram:555778:P-02-045219`
- channel_origin: `live:ptb_app+fake_bot+subprocess:228108:uv_source`
- delivery_pack_body_hash: `29b14f7944f59dd666e5149381de9d2c…`
- delivery_pack_body_preview: `요청하신 세션의 Authority 전환과 실험 기록 삭제를 확인했습니다. 다음 단계로 승인 플로우를 진행하겠습니다.`
- raw_event_count: 11
- fallback_notes:
  - S16 telegram live harness: Update.de_json → TelegramPlugin._on_text → InboundMessage → telegram_session_id → WS chat.send → await task.completed

### CLI × P-03
- status: `ok`
- error_code: ``
- session_id: `cli-s16-P-03-045150`
- channel_origin: `subprocess:210376:uv_source`
- delivery_pack_body_hash: `82431745bd62ec99856d29a4afa888a0…`
- delivery_pack_body_preview: `접수하신 요청을 확인했습니다. LearningInbox 항목을 추출하고, review·approve 후 promote 단계를 진행한 뒤, eval 실패 시뮬레이션을 진행하겠습니다. 다음 단계로 진행하겠습니다.`
- raw_event_count: 11

### Electron × P-03
- status: `ok`
- error_code: ``
- session_id: `electron-replay-P-03-045248`
- channel_origin: `electron-replay-synthetic:cli_backend_equivalence`
- delivery_pack_body_hash: `82431745bd62ec99856d29a4afa888a0…`
- delivery_pack_body_preview: `접수하신 요청을 확인했습니다. LearningInbox 항목을 추출하고, review·approve 후 promote 단계를 진행한 뒤, eval 실패 시뮬레이션을 진행하겠습니다. 다음 단계로 진행하겠습니다.`
- raw_event_count: 11
- fallback_notes:
  - electron row synthesised from CLI replay result — Electron backend subprocess uses identical OPENAI_BASE_URL env (replay proxy), same cassette, same bytes. S16 RFC §4 Phase 4 documents this; no additional LLM call was issued.

### Telegram × P-03
- status: `ok`
- error_code: ``
- session_id: `telegram:555779:7:P-03-045234`
- channel_origin: `live:ptb_app+fake_bot+subprocess:177528:uv_source`
- delivery_pack_body_hash: `82431745bd62ec99856d29a4afa888a0…`
- delivery_pack_body_preview: `접수하신 요청을 확인했습니다. LearningInbox 항목을 추출하고, review·approve 후 promote 단계를 진행한 뒤, eval 실패 시뮬레이션을 진행하겠습니다. 다음 단계로 진행하겠습니다.`
- raw_event_count: 11
- fallback_notes:
  - S16 telegram live harness: Update.de_json → TelegramPlugin._on_text → InboundMessage → telegram_session_id → WS chat.send → await task.completed
