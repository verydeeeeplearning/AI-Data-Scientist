# CONVENTIONS — 코드·네이밍·테스트 컨벤션

모든 agent가 동일하게 따라야 하는 표준. **변경은 leader만**.

---

## 1. 파일/디렉토리 명명

### 1.1 Frontend (TypeScript)

| 종류 | 규칙 | 예 |
|------|------|----|
| Domain 파일 | camelCase | `mission.ts`, `resultCard.ts` |
| Component 파일 | PascalCase + `.tsx` | `MissionHeader.tsx`, `TrustStrip.tsx` |
| Hook 파일 | camelCase + `use` prefix | `useMissionContext.ts` |
| Test 파일 | source 명 + `.test.ts(x)` | `mission.test.ts`, `MissionHeader.test.tsx` |
| Integration test | source 명 + `.integration.test.tsx` | `MissionHeader.integration.test.tsx` |
| 디렉토리 | kebab-case (또는 단수 도메인) | `result-cards/`, `mission/` |

### 1.2 Backend (Python)

| 종류 | 규칙 | 예 |
|------|------|----|
| 모듈 파일 | snake_case | `mission_pack.py`, `result_card.py` |
| 클래스 | PascalCase | `class MissionContext:` |
| 함수/변수 | snake_case | `def get_mission_context():` |
| Test 파일 | `test_<source>.py` | `test_mission_pack.py` |
| Use case | `<verb>_<noun>_usecase.py` | `get_mission_context_usecase.py` |
| DTO | `<noun>_dto.py` | `mission_context_dto.py` |
| Port interface | `<noun>_port.py` | `card_repository_port.py` |

---

## 2. Clean Architecture 디렉토리

[`../00_overview/02_CLEAN_ARCHITECTURE_MAPPING.md`](../00_overview/02_CLEAN_ARCHITECTURE_MAPPING.md) 참조. 핵심 원칙만:

- **Domain**: 외부 import 금지 (stdlib만). 순수 함수/값 객체.
- **Application**: Domain만 의존. Port interface 정의.
- **Infrastructure**: Application의 port 구현. 외부 lib 사용 OK.
- **Presentation**: 모든 레이어 사용 가능. 비즈니스 로직 금지 (use case 호출만).

---

## 3. 명명 규칙 (식별자)

### 3.1 Boolean

| 패턴 | 의미 | 예 |
|------|------|----|
| `is<X>` | 상태 | `isPinned`, `isLoading` |
| `has<X>` | 보유 | `hasFallback`, `hasError` |
| `should<X>` | 의도 | `shouldShowWarning` |
| `can<X>` | 능력 | `canExport` |
| `<X>Required` | 필수 여부 | `approvalRequired` |

**금지**: `flag`, `enabled` (모호) → 구체적으로

### 3.2 Event handler

`handle<Event>` 또는 `on<Event>`. **컴포넌트 prop은 `on<Event>`, 내부 핸들러는 `handle<Event>`**.

```typescript
function MissionSlot({ onClick }: Props) {
  const handleClick = () => { ... };
  return <button onClick={handleClick}>...</button>;
}
```

### 3.3 Use case 함수

동사로 시작 — `get / list / create / update / delete / pin / promote / branch / rerun / submit / build / preview`.

---

## 4. i18n 키 규칙

### 4.1 키 구조
```
<feature>.<sub_feature>.<element>[.<state>]
```

### 4.2 Namespace 분할
- `mission.json` — Mission 영역
- `chat.json` — Chat 영역
- `onboarding.json`
- `settings.json`
- `common.json` — 공통 버튼/액션
- `area.json` — IA area 라벨
- `cmd.json` — Command Palette
- 등

각 PLAN은 자기 namespace만 추가/수정. 충돌 회피.

### 4.3 키 작성 규칙
- 영어 base key, 모든 locale에 동일 키
- 의미 기반 (백엔드 모듈명 X) — `mission.header.budget.label` ✓ / `runtime.statusBar.cost` ✗
- 동적 값은 ICU MessageFormat — `"5 of {total}"` → `"{current} of {total}"`

---

## 5. Import 순서 (Frontend)

```typescript
// 1. External (npm)
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

// 2. Domain (innermost)
import { Locale } from '@/domain/locale';

// 3. Application
import { detectInitialLocale } from '@/application/locale/detectLocale';

// 4. Infrastructure
import { i18nClient } from '@/infrastructure/i18n/i18nClient';

// 5. Presentation (components, hooks)
import { LocaleSelector } from '@/components/settings/LocaleSelector';

// 6. Style/asset
import './styles.css';
```

`@/` 는 `electron/src/renderer/` alias. tsconfig paths 참조.

---

## 6. 테스트 컨벤션

[`../00_overview/03_TEST_STRATEGY.md`](../00_overview/03_TEST_STRATEGY.md) 참조. 핵심:

- **AAA 패턴** — Arrange / Act / Assert
- **한 테스트에 한 의도**
- **describe**: 클래스/함수 명, **it**: 한국어 동작 서술
- **Fixture**: `tests/fixtures/` 또는 `__fixtures__/`
- **Mock**: 가능한 한 적게. domain은 mock 0.

---

## 7. WS 이벤트 컨벤션

[`../cross_cutting/PLAN_03_event_schema_versioning.md`](../cross_cutting/PLAN_03_event_schema_versioning.md) 참조.

### 7.1 Type 명명
`<area>.<entity>.<verb>` — kebab/dot:
- `mission.context.updated`
- `plan.created`
- `plan.replanned`
- `reasoning.emitted`
- `card.pinned`

### 7.2 Envelope
모든 이벤트는 envelope wrapping (type / version / ts / payload). Source-of-truth:
- TypeScript: `electron/src/renderer/infrastructure/ws/eventEnvelope.ts`
- Python: `src/ds_agent/api/event_envelope.py`

### 7.3 신규 이벤트 추가 체크리스트 (PR 게이트)

새 WS 이벤트를 추가하는 PR 은 다음을 모두 만족:

- [ ] Python 측: `src/ds_agent/api/event_schemas.py` 에 TypedDict 추가 (payload shape)
- [ ] TypeScript 측: `electron/src/renderer/types/events.ts` 에 동일 shape 의 interface 추가
- [ ] TypeScript 측: `electron/src/renderer/infrastructure/ws/eventSchemaRegistry.ts` 에 `registerEventSchema(...)` 호출 추가 (runtime validator)
- [ ] Emit 경로: 백엔드는 `WsAgentCallbacks._emit(...)` 만 사용 (직접 `send_json` 금지) — envelope 자동 부착
- [ ] 새 필드 추가는 optional (minor 버전 호환). 필수 필드는 새 major 만 허용
- [ ] Test: `tests/unit/api/` 에 round-trip 테스트, `electron/tests/contract/eventSchemaRegistry.spec.ts` 의 pre-seed 목록에 type 추가
- [ ] DEVELOPMENT_LOG / INTEGRATION_POINTS 갱신 (WS Event Stream 행)

---

## 8. 에러 처리

### 8.1 Domain 에러
`domain/errors/` 에 정의. 명시적 클래스.

```python
class BudgetExceeded(DomainError): ...
class MissionConstraintViolated(DomainError): ...
```

### 8.2 Application 에러
도메인 에러를 catch + 적절한 응답 코드/메시지 변환.

### 8.3 Presentation 에러
사용자 친화 메시지 (i18n 키). raw 에러 노출 금지.

### 8.4 절대 silent fail 금지
[`pr-review-toolkit:silent-failure-hunter`](../../../../.claude/agents/pr-review-toolkit/silent-failure-hunter) 가 검출. fallback 사용 시 반드시 telemetry/log.

---

## 9. Git Commit / PR

[`../00_overview/06_AGENT_COORDINATION.md §4`](../00_overview/06_AGENT_COORDINATION.md) 참조.

---

## 10. Style (린트/포맷)

| 도구 | 설정 |
|------|------|
| Frontend lint | ESLint (existing config) + 본 PLAN의 custom rules |
| Frontend format | Prettier (existing config) |
| Backend lint | `ruff check` |
| Backend format | `ruff format` |
| Backend type | `mypy` |
| TypeScript type | `tsc --noEmit` |

각 PR은 4종 모두 통과 (CI 자동).

---

## 11. 주석 정책

[`~/.claude/CLAUDE.md`](https://docs.anthropic.com/en/docs/claude-code/memory) 의 "Default to writing no comments" 원칙 따름.

**작성 가능한 주석**:
- 비자명한 비즈니스 제약 ("Verifier 결과는 5분 캐싱 — provider rate limit 회피")
- 외부 lib의 surprising 동작 우회 설명
- TODO with issue 링크 (`// TODO(#123): refactor when ...`)

**작성 금지**:
- 변수/함수가 무엇을 하는지 (이름이 설명)
- 변경 이력 ("added by ...", "fixed bug X")
- 구현 의도 자체 (PR description에)
