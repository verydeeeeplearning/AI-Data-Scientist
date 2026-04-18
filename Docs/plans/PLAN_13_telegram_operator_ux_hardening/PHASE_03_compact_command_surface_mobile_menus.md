# Phase 03: Compact Command Surface and Mobile Menus

**Priority**: P1  
**Status**: Proposed  
**Depends On**: Phase 00-02

---

## 1. Goal

Make Telegram discoverable enough that an operator does not need to memorize the
full command set.

---

## 2. Current Gap

The current `/help` output is functionally correct but dense.

Problems:

- too many commands for casual operators
- little context-driven guidance
- repeated need to type full command names
- limited "what should I do next?" affordance after alerts or approvals

---

## 3. Planned Implementation

Primary files:

- `src/ds_agent/gateway/telegram_runner.py`
- `src/ds_agent/channels/bundled/telegram/plugin.py`

Implementation items:

- add a compact `/ops` or `/menu` summary command
- split help output into:
  - read
  - control
  - policy
  - artifacts
- provide context shortcuts after major replies:
  - after `/project <id>`, show artifact shortcut
  - after `/run`, show stop or inspect shortcut
  - after `/approvals`, show decision shortcut
- prefer Telegram command descriptions and `setMyCommands`-style discoverability first
- use reply-keyboard hints only where they materially help and do not create sticky UI state

Design direction:

- keep the command-first mental model
- reduce cognitive load through guided follow-up

---

## 4. UX Rules

- primary mobile actions should be visible within one or two screens
- help output should be grouped by operator intent, not backend structure
- menus must never hide critical fallbacks
- menu additions should not create ambiguous state
- compact menus should remain additive:
  they improve discoverability, but must not become the only path for action

---

## 5. Verification

Required:

```bash
python -m pytest tests/unit/infrastructure/test_telegram_runner.py -q -p no:cacheprovider
python -m pytest tests/integration/test_telegram_plugin.py -q -p no:cacheprovider
python -m ruff check src/ds_agent/gateway/telegram_runner.py
```

Manual checks:

1. Open `/menu` on a phone and confirm the main actions are obvious
2. Walk through one approval and one artifact flow without using `/help`
3. Confirm command discoverability improved without increasing spam

---

## 6. Exit Criteria

- Telegram is easier to operate without prior command memorization
- the most common workflows expose clear next actions
- the bot remains concise on a phone screen

---

## Review: 실현 가능성 점검 코멘트 (2026-04-13)

### R1. `setMyCommands` — Phase 01 없이 즉시 구현 가능한 부분

Telegram Bot API의 `setMyCommands`를 호출하면 클라이언트 `/` 메뉴에 커맨드가 자동 표시된다.
이것만으로도 발견성이 크게 개선되며, 인라인 키보드(Phase 01)와 무관하게 즉시 할 수 있다.

구현 위치: `TelegramPlugin.start()` 또는 `TelegramGatewayRunner.run()` 시작 시 1회 호출.

```python
from telegram import BotCommand
await bot.set_my_commands([
    BotCommand("status", "Runtime summary"),
    BotCommand("runs", "Recent runs"),
    BotCommand("approvals", "Pending approvals"),
    BotCommand("alerts", "Recent alerts"),
    BotCommand("stop", "Stop current run"),
    BotCommand("resume", "Resume from checkpoint"),
    # ... 최대 100개, description 최대 256자
])
```

`BotCommandScope`를 활용하면 그룹/DM별로 다른 커맨드 세트를 노출할 수도 있다.

### R2. Context shortcuts — Phase 01 의존

"run 결과 후 Stop/Inspect 버튼 표시" 같은 context shortcuts는
인라인 키보드(`InlineKeyboardMarkup`)가 필요하므로 Phase 01 완료 후에�� 가능하다.

Phase 01 없이 할 수 있는 대안:
- 텍스트 기반 힌트: 응답 끝에 `"Use /stop {run_id} or /run {run_id}"` 추가
- 이미 일부 커맨드 응답에 이런 패턴이 있으므로 확장하면 됨

### R3. `ReplyKeyboardMarkup` 사용 시 주의

Telegram의 Reply Keyboard는 한번 표시되면 사용자가 명시적으로 닫거나
`ReplyKeyboardRemove`를 보내야 사라진다. 이것이 "sticky UI state"를 만들 수 있으므로
계획서에서 언급한 대로 신중하게 써야 한다.

인라인 키보드(Phase 01)는 메시지에 첨부되므로 이 문제가 없다. 가능하면 인라인 키보드 우선.
