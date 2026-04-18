# Phase 01: Inline Approval and Run Actions

**Priority**: P0  
**Status**: Proposed  
**Depends On**: Phase 00

---

## 1. Goal

Reduce the number of manual commands required for the most common Telegram
operator actions.

---

## 2. Current Gap

The current command-first UX works, but common actions still require typing:

- approve
- reject
- stop run
- resume
- inspect run

That increases operator friction on a phone, especially during incidents.

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/channels/bundled/telegram/plugin.py`
- `src/ds_agent/gateway/telegram_runner.py`

Potentially needed:

- signed action-token helper in `src/ds_agent/runtime/` or `src/ds_agent/gateway/`

Implementation items:

- add callback-query support to the Telegram plugin
- extend the shared channel surface so outbound Telegram messages can carry
  inline reply markup and later correlate callback actions to sent messages
- attach inline buttons to:
  - approval requests
  - active run summaries
  - recovery notices
- support actions such as:
  - approve
  - reject
  - stop
  - resume
  - inspect
- enforce action-token validation:
  - actor scope
  - chat scope
  - short TTL
  - idempotency
- keep callback payloads compact:
  - use short opaque action tokens instead of embedding raw prompt text
  - do not assume arbitrary payload size
- acknowledge every callback query explicitly so Telegram clients do not leave
  the button press in a perpetual loading state

Fallback rule:

- every inline action must still have a text-command equivalent

---

## 4. UX Rules

- inline actions should speed up the common path, not replace explicit control
- destructive actions should still confirm the resulting state in text
- stale buttons must fail safely and explain why
- action labels must stay short enough for Telegram mobile layouts
- group-chat behavior must not assume the bot can always see arbitrary follow-up
  text outside Telegram privacy-mode rules

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/integration/test_telegram_plugin.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py \
  src/ds_agent/channels/bundled/telegram/plugin.py
```

Manual checks:

1. Approve once with a button and once with `/approve`
2. Stop an active run from Telegram without typing a run id
3. Confirm stale or duplicate button presses are rejected cleanly

---

## 6. Exit Criteria

- high-frequency Telegram actions no longer require manual command typing
- inline actions are bounded, auditable, and idempotent
- text-command fallbacks remain intact

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. 현재 코드의 구조적 갭 — 반드시 선행 해결

이 Phase는 현재 코드 구조에서 **즉시 구현할 수 없다**. 아래가 모두 누락되어 있다.

**`TelegramPlugin.poll_updates()` (plugin.py:214~252)**:
```python
# 현재: update.message만 처리
for update in updates:
    if update.message and update.message.text:  # callback_query 완전 무시
        ...
```
인라인 버튼을 눌러도 봇이 아무 반응을 하지 않는다.
`update.callback_query` 분기를 추가하고, `InboundMessage`에 `callback_data`, `callback_query_id` 필드를 넣어야 한다.

**`OutboundMessage` (channels/base.py)**:
인라인 키보드를 메시지에 첨부할 `reply_markup` 필��가 없다.
`send_text()` 호출 시 키보드를 전달할 방법이 현재 없으므로 `OutboundMessage`를 확장하거나
별도 `send_text_with_markup()` 메서드를 추가해야 한다.

**`answerCallbackQuery` 미구현**:
Telegram은 callback query를 받으면 **반드시** `answerCallbackQuery`를 호출해야 한다.
미호출 시 사용자 UI에 로딩 스피너가 영구 회전한다.
→ `TelegramPlugin.answer_callback_query(query_id, text=None)` 메서드 필요.

**`editMessageReplyMarkup` 미구현**:
버튼 클릭 후 해당 버튼을 비활성화하거나 결과 상태로 교체하려면 메시지 편집이 필요하다.
→ `TelegramPlugin.edit_message_reply_markup(chat_id, message_id, markup)` 메서드 필요.

### R2. callback_data 64바이트 제한 — 토큰 설계 필수

Telegram의 `InlineKeyboardButton.callback_data`는 **최대 64바이트**(UTF-8).
approval_id + action + scope + TTL을 모두 담으려면 compact encoding이 필요하다.

권장 설계:
```
# 포맷: {action}:{short_id}:{nonce}
# 예시: "ap:a3f2:x9k1"  (approve approval a3f2, nonce x9k1)
# 예시: "rj:a3f2:x9k1"  (reject approval a3f2)
# 예시: "st:r7b4:y2m3"  (stop run r7b4)
```
- action: 2자 (ap/rj/st/rs/in)
- short_id: approval_id 또는 run_id의 축약형 (server-side lookup 기반)
- nonce: TTL + idempotency 검증용
- 서버에서 nonce → (actor, chat, timestamp, target_id) 매핑 유지

### R3. `python-telegram-bot` Application builder 전환 권장

현재 저수준 `Bot` 클래스를 직접 사용 중이다.
`Application.builder()` 기반으로 전환하면:
- `CallbackQueryHandler` — callback_query 라우팅을 프레임워크가 처리
- `CommandHandler` — 커맨드 파싱을 프레임워크가 처리
- `AIORateLimiter` (v22+) — Telegram 429 에러 자동 재시도
- `ConversationHandler` — 다단계 워크플로우 지원

이 전환은 이 Phase뿐 아니라 PLAN_13 전체, 그리고 PLAN_15의 rate limiting에도 영향을 준다.
별도 선행 작업으로 분리하여 PLAN_13 Phase 00과 병행 진행하는 것을 권장한다.

### R4. 그룹 채팅 privacy mode 주의

Telegram 그룹에서 봇의 privacy mode가 켜져 있으면 봇은 **슬래시 커맨드와 인라인 버튼 콜백만**
수신하고, 일반 텍스트 메시지는 수신하지 못한다.
현재 plain-text approval resolution(일반 텍스트로 승인)이 그룹에서는 동작하지 않을 수 있다.
인라인 버튼이 이 문제를 자연스럽게 해결하므로, 그룹 운영 시나리오에서 이 Phase의 중요성은 더 높다.
