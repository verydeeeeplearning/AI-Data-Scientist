# Plan 13: Telegram Operator UX Hardening

**Status**: Proposed  
**Created**: 2026-04-13  
**Scope**: Upgrade Telegram from a command-capable operator bot into a lower-friction daily operations surface

---

## 1. Objective

`PLAN_12` established a practical Telegram command and control surface.
It did not add full live cross-process parity, nor lower-friction mobile UX
primitives such as inline actions or per-chat preference state.

The next gap is operator ergonomics on top of that baseline.

The target of `PLAN_13` is:

- fewer commands to remember
- less notification fatigue
- faster mobile intervention
- clearer operator intent and auditability

This plan is intentionally UI and workflow heavy, not architecture heavy.

Implementation note:

- Telegram itself supports inline keyboards, callback queries, command menus,
  reply keyboards, and topic-aware routing.
- The current codebase does **not** yet expose callback-query handling or a
  generic reply-markup primitive in the shared channel abstraction.
- Therefore Phase 01 and parts of Phase 03 require channel-surface expansion,
  not only `telegram_runner.py` command tweaks.
- Preference state should remain chat-scoped by default; true thread-scoped
  preference semantics should follow `PLAN_14`, not silently precede it.

---

## 2. Why This Plan Exists

Today Telegram is already useful, but it still behaves like a technical bot:

- operators must remember exact commands
- approval and run control are still text-first
- alert noise is only partially managed
- there is no explicit per-chat preference model
- routine mobile actions still take too many steps

That is acceptable for parity. It is not ideal for day-to-day operation.

---

## 3. Phase Order

1. Phase 00: Chat Preferences and Subscription Surface
2. Phase 01: Inline Approval and Run Actions
3. Phase 02: Alert Acknowledge, Mute, and Digest Controls
4. Phase 03: Compact Command Surface and Mobile Menus
5. Phase 04: Operator Safety, Audit, and Recovery Guardrails

---

## 4. Milestones

### Milestone A: Personalized Signal Control

- Phase 00 complete
- each Telegram chat can express alert and digest preferences

### Milestone B: One-Tap Intervention

- Phase 01 complete
- approvals and run control no longer depend entirely on manual command typing

### Milestone C: Noise-Managed Operations

- Phase 02-03 complete
- the operator can acknowledge, mute, or summarize runtime activity from mobile

### Milestone D: Trustworthy Mobile Operations

- Phase 04 complete
- Telegram actions are auditable, bounded, and difficult to misuse

---

## 5. Verification Baseline

Every phase should pass:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/integration/test_telegram_plugin.py -q -p no:cacheprovider
python -m pytest tests/unit/infrastructure/test_api.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py \
  src/ds_agent/channels/bundled/telegram/plugin.py
```

If a phase introduces shared stores or callback-query flows, also run:

```bash
python -m pytest tests/integration/test_runtime_wiring.py -q -p no:cacheprovider
python -m pytest tests/e2e/test_ws_e2e.py -q -p no:cacheprovider
```

---

## 6. Phase Summary

| Phase | Goal | Priority | Status |
|------|------|----------|--------|
| 00 | add per-chat notification and subscription preferences | P0 | proposed |
| 01 | make approval and run control low-friction via inline actions | P0 | proposed |
| 02 | support acknowledge, mute, snooze, and digest controls | P1 | proposed |
| 03 | reduce command burden with compact menus and context shortcuts | P1 | proposed |
| 04 | add operator audit, stale-action protection, and explicit guardrails | P1 | proposed |

---

## 7. Notes

- `PLAN_13` should stay compatible with the current chat-scoped Telegram session model.
- If thread-level session isolation becomes mandatory, that belongs in `PLAN_14`.
- Inline actions should always preserve text-command fallbacks.
- Preference logic should be reusable across future channels, but Telegram remains the first target.
- Telegram-specific hard limits must shape the design:
  callback actions require `answerCallbackQuery`, callback payloads are size-limited,
  and privacy-mode behavior in groups can still restrict which free-form messages the bot sees.

---

## 8. Detailed Documents

- [PHASE_00_chat_preferences_subscription_surface.md](./PHASE_00_chat_preferences_subscription_surface.md)
- [PHASE_01_inline_approval_run_actions.md](./PHASE_01_inline_approval_run_actions.md)
- [PHASE_02_alert_ack_mute_digest_controls.md](./PHASE_02_alert_ack_mute_digest_controls.md)
- [PHASE_03_compact_command_surface_mobile_menus.md](./PHASE_03_compact_command_surface_mobile_menus.md)
- [PHASE_04_operator_safety_audit_guardrails.md](./PHASE_04_operator_safety_audit_guardrails.md)

---

## 9. Review: 실현 가능성 점검 코멘트 (2026-04-13)

### 9.1 구조적 선행작업: Phase 01 착수 전 반드시 해결

Phase 01(인라인 버튼)은 현재 채널 추상화 계층이 **텍스트 전용**이라 즉시 구현할 수 없다.
아래 네 가지가 선결되어야 한다.

| 선행작업 | 변경 대상 | 상세 |
|---------|----------|------|
| 1. `OutboundMessage`에 `reply_markup` 필드 추가 | `channels/base.py` | `reply_markup: dict \| None = None` — InlineKeyboardMarkup JSON을 채널별로 전달 |
| 2. `InboundMessage`에 callback 필드 추가 | `channels/base.py` | `callback_data: str \| None`, `callback_query_id: str \| None` |
| 3. `TelegramPlugin.poll_updates()`에 callback_query 분기 | `plugin.py:214~252` | 현재 `update.message`만 처리 — `update.callback_query` 완전히 무시됨 |
| 4. `TelegramPlugin.answer_callback_query()` 메서드 | `plugin.py` | Telegram 필수: 호출 안 하면 버튼 로딩 스피너가 영구 회전 |

추가 권장:
- `TelegramPlugin.edit_message_reply_markup()` — 버튼 상태 업데이트용 (눌린 버튼 비활성화 등)
- `python-telegram-bot`의 `Application` builder 전환 검토 — `CallbackQueryHandler`, `AIORateLimiter` 등 프레임워크 수준 지원 획득

### 9.2 Telegram Bot API 하드 제한

Phase 설계 시 아래 수치를 반드시 준수해야 한다.

| 제한 | 값 | 영향받는 Phase |
|------|---|--------------|
| `callback_data` 최대 크기 | **64바이트** (UTF-8) | Phase 01: action token compact encoding 필수 |
| 1:1 채팅 전송 한도 | ~1 msg/sec | Phase 02 digest, 전체 알림 전송 |
| 그룹 전송 한도 | ~20 msg/min | Phase 02 그룹 운영 시 |
| 전체 broadcast 한도 | ~30 msg/sec | 다수 operator chat 동시 push |
| 메시지 최대 길이 | 4096자 | 이미 chunk_text()로 대응됨 |
| 커맨드 description 최대 | 256자 | Phase 03 setMyCommands |
| 봇당 최대 커맨드 수 | 100개 | Phase 03 커맨드 메뉴 |

### 9.3 Phase별 실현 가능성 요약

| Phase | 가능성 | 비고 |
|-------|--------|------|
| 00 | **즉시 가능** | 순수 백엔드 상태 관리, Telegram API 추가 불필요 |
| 01 | **구조적 리팩터 후 가능** | 9.1의 네 가지 선행작업 완료 필요 |
| 02 | **즉시 가능** | 텍스트 커맨드만으로 동작; 인라인 버튼은 Phase 01 이후 점진 추가 |
| 03 | **부분 즉시 가능** | `setMyCommands` 등록은 Phase 01 없이 가능; context shortcuts는 Phase 01 의존 |
| 04 | **즉시 가능** | 순수 백엔드 감사 로직 |

### 9.4 권장 착수 순서 수정

현재 순서(00→01→02→03→04)에서 01이 가장 무거운 선행작업을 가지므로,
실제 착수는 아래 순서가 효율적이다:

1. **Phase 00** — 즉시 착수 가능
2. **채널 추상화 확장** (선행작업) — Phase 01 준비
3. **Phase 02** — Phase 00 완료 후 즉시, Phase 01과 병행 가능
4. **Phase 01** — 선행작업 완료 후
5. **Phase 03** — `setMyCommands` 부분은 Phase 01과 병행, context shortcuts는 Phase 01 이후
6. **Phase 04** — 마지막
