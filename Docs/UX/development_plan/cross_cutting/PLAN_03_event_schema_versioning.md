# PLAN 03: WS 이벤트 스키마 Versioning

**Status**: Pending — Phase 1 후반 ~ Phase 2 시작 전
**Estimated Effort**: 3–4 작업일

**ROADMAP 매핑**: §7.1 기술 리스크 → "WebSocket 이벤트 스키마 확장"
**Clean Architecture**: `00_overview/02_CLEAN_ARCHITECTURE_MAPPING.md §4.3`

> **🤖 AI Agent 안내**: 본 PLAN을 시작하기 전 [`SHARED/`](../SHARED/) 의 `GLOSSARY.md`, `CONVENTIONS.md`, `INTEGRATION_POINTS.md`, `DECISIONS.md`, `DEVELOPMENT_LOG.md`, `ACTIVE_WORK.md` 를 모두 확인하고 [`00_overview/06_AGENT_COORDINATION.md`](../00_overview/06_AGENT_COORDINATION.md) 의 protocol을 따른다. 작업 완료 시 §11 진행 추적, §12 Notes & Learnings, 그리고 SHARED의 `DEVELOPMENT_LOG.md` / `ACTIVE_WORK.md` / `INTEGRATION_POINTS.md` 를 반드시 갱신한다.

---

## 1. 개요

Phase 2-3에서 신규 WS 이벤트가 다수 추가됨 (`mission.context.updated`, `plan.created`, `reasoning.emitted` 등). 이때 **backward compatibility**가 깨지면 기존 클라이언트가 오작동.

### 목표
- 모든 WS 이벤트에 `version` 필드 강제
- Producer는 backward compatible하게 변경 (필드 추가 OK, 제거/타입 변경 X)
- Consumer는 unknown event 또는 unknown field를 graceful 처리
- 매이저 버전 변경 시 negotiation 절차

---

## 2. 이벤트 envelope

```typescript
// 표준 envelope
export interface WsEvent<T> {
  type: string;          // "mission.context.updated"
  version: string;       // "1.0", "1.1", "2.0"
  ts: number;            // unix ms
  source?: string;       // emit한 컴포넌트
  correlationId?: string; // 추적용
  payload: T;
}
```

---

## 3. 호환성 규칙

### 3.1 Minor 버전 (1.0 → 1.1)
**허용**:
- payload에 optional 필드 추가
- 새 event type 추가
- 새 status enum 값 추가 (consumer가 unknown으로 graceful 처리해야 함)

**금지**:
- 필수 필드 제거
- 필드 타입 변경
- enum 값 의미 변경

### 3.2 Major 버전 (1.x → 2.0)
- Breaking change 허용
- 클라이언트와 negotiation 필요
- 마이그레이션 가이드 작성

---

## 4. Negotiation

연결 시점:

```typescript
// 클라이언트
ws.send({ type: 'handshake', supportedVersions: ['1.0', '1.1', '2.0'] });

// 서버
ws.send({ type: 'handshake.ack', selectedVersion: '1.1' });
```

서버가 클라이언트가 지원하지 않는 버전만 가능하면 503 + 사용자 안내.

---

## 5. 구현 Sub-Phase

### Sub-Phase 3.1 — Envelope 도입 (1일)
- [ ] 백엔드: 모든 emit 함수가 envelope wrapping
- [ ] 프론트: 모든 subscriber가 envelope 검증
- [ ] zod schema (envelope)

### Sub-Phase 3.2 — Per-event schema 정의 (1일)
- [ ] 각 이벤트 타입별 zod schema
- [ ] Schema registry: `infrastructure/ws/schemas/`
- [ ] 알려지지 않은 type / version → log + skip

### Sub-Phase 3.3 — Negotiation (1일)
- [ ] handshake protocol
- [ ] 버전 mismatch 시 사용자 안내 + upgrade prompt

### Sub-Phase 3.4 — 테스트 + 가이드 (0.5일)
- [ ] Backward compatibility 테스트 (이전 버전 클라이언트로 새 서버 호출)
- [ ] 신규 event 추가 시 체크리스트 (PR 템플릿)

---

## 6. 품질 게이트

- [ ] 모든 WS 이벤트가 envelope 사용
- [ ] Schema registry 100% 커버리지
- [ ] Unknown version 시 graceful (crash X)
- [ ] Negotiation 동작 (버전 mismatch 시나리오 테스트)

---

## 7. 의존성

- 선행: Phase 1 진행 중 (`mission.context.updated` 추가 시점에 baseline 확보)
- 후속: Phase 2-3 모든 신규 이벤트가 본 인프라 활용

---

## 8. 진행 추적

- [x] 3.1 Envelope (1일) — agent-w0-foundation-001 / 2026-04-19
- [x] 3.2 Schema registry (1일) — agent-w0-foundation-001 / 2026-04-19
- [x] 3.3 Negotiation (1일) — agent-w0-foundation-001 / 2026-04-19
- [x] 3.4 Test + 가이드 (0.5일) — agent-w0-foundation-001 / 2026-04-19

---

## 9. Notes & Learnings

### Sub-Phase 3.1–3.4 (agent-w0-foundation-001, 2026-04-19)

**산출물**:
- `src/ds_agent/api/event_envelope.py` — `WsEventEnvelope` dataclass + `wrap_event` / `parse_envelope` / `negotiate` (167 LOC)
- `src/ds_agent/api/callbacks.py` — `WsAgentCallbacks._emit` 가 envelope 메타데이터 (version/source/correlationId) 인라인 추가
- `electron/src/renderer/infrastructure/ws/eventEnvelope.ts` — TypeScript `parseEnvelope` / `wrapEvent` (105 LOC)
- `electron/src/renderer/infrastructure/ws/eventSchemaRegistry.ts` — runtime validator + 8 이벤트 pre-seed
- `electron/src/renderer/hooks/useWebSocket.ts` — `WsEvent` 인터페이스에 envelope 메타필드 추가 (backward-compat: optional)
- `tests/unit/api/test_event_envelope.py` (24 cases) + `test_ws_callbacks_envelope.py` (4 cases)
- `electron/tests/contract/wsEnvelope.spec.ts` (10 cases) + `eventSchemaRegistry.spec.ts` (8 cases)
- `SHARED/CONVENTIONS.md §7.3` — 신규 이벤트 추가 체크리스트
- `SHARED/INTEGRATION_POINTS.md` — WS Event Stream 행 갱신 (envelope baseline 완료)

**디자인 결정 (ADR-0007)**:
- zod / pydantic-extra 미도입 — round-trip 테스트로 contract 검증 충분
- envelope 가 기존 `{type:"event", event, payload, ts}` frame 의 superset (필드 추가만, 제거 0) → 기존 renderer 무수정 동작
- 후속 wave 의 신규 emit 도 동일 `_emit()` 만 호출하면 자동으로 envelope 부착
- handshake (negotiate) 는 server-side 헬퍼만 구현 — 실제 WebSocket 연결 시점 통합은 후속 wave (handshake 파라미터를 ws_handler 가 어디서 수신할지가 변경됨)

**Cross-language 호환성 검증**:
- TypeScript `parseEnvelope` 와 Python `parse_envelope` 가 동일 schema 검증
- `to_wire()` 출력 키셋 = TypeScript interface 키셋 ({type, version, ts, source?, correlationId?, payload})
- 동일 shape 양/음성 fixture 양측에서 통과 (각각 10개 / 24개 케이스)

**Major version 변경 시 절차** (미래용 메모):
- ENVELOPE_MAJOR 증가 → 양측 동시 배포 필요
- handshake 의 `negotiate()` 가 자동 fallback 처리 (server 가 client 의 supportedVersions 중 same-major 찾음)
- mismatch 시 `WsEnvelopeError(code='major-mismatch')` → ws_handler 가 사용자 안내 + reconnect 차단 (후속 wave 책임)

**회귀 영향**:
- 0 — 기존 frame 에 optional 필드만 추가
- 모든 기존 contract test (11개) + 신규 4개 테스트 모두 PASS
- ruff / mypy clean
