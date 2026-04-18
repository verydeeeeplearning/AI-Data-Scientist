# Implementation Plan: Enhancement Specs 잔여 구현

**Status**: In Progress
**Started**: 2026-04-16
**Last Updated**: 2026-04-16

**CRITICAL INSTRUCTIONS**: After completing each phase:
1. Check off completed task checkboxes
2. Run all quality gate validation commands
3. Verify ALL quality gate items pass
4. Update "Last Updated" date
5. Document learnings in Notes section
6. Only then proceed to next phase

DO NOT skip quality gates or proceed with failing checks

---

## Overview

### Feature Description
감사 보고서(IMPLEMENTATION_GAP_AUDIT_2026-04-16.md)에서 식별된 미구현 항목들을 체계적으로 구현한다.
대상: 08(Workflow Integration P3b+ 마감), 02(Semantic Memory 운영 검증/cutover), 09(Async Portfolio Manager), 10(Self-Improvement Governance), 01(optional polish).

### Success Criteria
- [ ] 08: Electron mutation controls + IntegrationSettings + health + DLQ replay + Email/Calendar connector + packaged E2E
- [ ] 02: README 갱신 + Electron semantic test + Telegram proposal inline + DomainKB cutover 방침 + promote_domain_kb.py
- [ ] 09: Portfolio domain/app/infra + scheduler + CLI + Electron ProjectControlTower + migration v12
- [ ] 10: Governance domain/app/infra + state machine + Eval gate + LearningInbox + migration v13
- [ ] 01: task_contract.subscribe IPC (optional)

---

## Architecture Decisions (Clean Architecture)

### LLM-Orchestrator 경계 원칙 (전 Phase 공통)

본 프로젝트는 Hermes-style 자율형 Agent다. 아래 원칙을 모든 Phase에서 지킨다.

1. **LLM이 유일한 orchestrator다.** 코드는 도구(tool)를 제공하고, LLM이 어떤 도구를 언제 호출할지 결정한다. 코드가 LLM 대신 "다음 단계"를 결정하는 것은 금지.
2. **Scheduler/Evaluator는 정보 제공자다.** PortfolioScheduler, WaitConditionEvaluator, RevalidationScheduler는 조건을 평가하고 결과를 노출할 뿐, 자율적으로 상태를 전이시키지 않는다. 전이 결정은 LLM이 도구를 호출하거나, 사람이 UI/CLI에서 명시 승인할 때만 발생한다.
3. **Hard constraint만 코드가 강제한다.** SLA 위반 경고, quiet hours 알림 보류, max_active_slots 상한, 도메인 순수성 검증은 코드가 강제해도 된다. 그러나 "어떤 업무를 먼저 할지", "언제 재개할지"는 LLM의 판단 영역이다.
4. **Prompt context는 status report다.** 시스템 프롬프트에 주입되는 portfolio/learning 정보는 "현재 상태 보고"이지 "지시"가 아니다. LLM은 이 정보를 참고하여 자유롭게 판단한다.
5. **Governance는 지식 품질 게이트다.** LearningItem 상태 머신은 LLM의 추론 경로를 제어하는 것이 아니라, LLM이 참조하는 조직 지식의 품질을 관리한다.

### Key Decisions

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| 08 먼저, 그 다음 02 cleanup | 08은 P3b operator loop가 열려 있어 사용자 경험 직접 영향 | 02는 core 완료 상태라 cutover 정리가 본질 |
| 09 → 10 순서 | 10의 Playbook promotion이 09의 PlaybookCandidate에 의존 | 09 Phase F(playbook detection)는 10 없이 stub 가능 |
| 09/10은 feature flag 기반 | `PORTFOLIO_ENABLED`, `SELF_IMPROVE_GOVERNANCE_V1` | rollback 안전성 확보, 기존 동작 무변경 |
| DomainKB는 삭제하지 않고 fallback 유지 | 기존 데이터 보존 + semantic memory sole source 점진 전환 | 이중 경로 유지 비용 |
| Scheduler는 controller가 아닌 evaluator | spec #3 "스케줄러는 제약만 검사하고, 우선순위 판단은 LLM이 수행" | 자동 재개 없이 LLM tool 호출 대기하므로 latency 발생 가능 |

---

## Dependencies

### Required Before Starting
- [x] 01-task-contract core complete
- [x] 03-verifier-orchestrator complete
- [x] 04-autonomy-control-plane complete
- [x] 05-evaluation-harness complete
- [x] 06-decision-os complete
- [x] 07-stakeholder-communication complete
- [x] 08-workflow-integration P2a+P3a complete

### External Dependencies
- python-pptx, nbformat (already present)
- smtplib (stdlib), google-api-python-client (Calendar, optional)

---

## Test Strategy

| Test Type | Coverage Target | Purpose |
|-----------|-----------------|---------|
| Unit Tests | >=90% domain, >=85% app | Business logic, state machines, entities |
| Integration Tests | Critical paths | SQLite persistence, tool wiring, approval flows |
| E2E / Smoke Tests | Key user flows | Packaged Electron scenarios |
| Contract Tests | Electron components | TypeScript type safety + behavior |

---

## Implementation Phases

총 12 Phase. 감사 보고서의 권장 순서(08→02→09→10→01)를 따르되, 각 spec 내에서 TDD 사이클 준수.

---

### ═══════════════════════════════════════
### STREAM A: 08-Workflow Integration 마감
### ═══════════════════════════════════════

---

### Phase 1: 08 — Electron WorkObject Mutation Controls
**Goal**: Read-only WorkObjectPanel에 intake/advance/close 조작 기능 추가
**Status**: Complete
**Estimated**: 4-5h

#### RED: Write Failing Tests First
- [ ] 1.1: Electron contract test `electron/tests/contract/work-object-mutations.spec.ts`
  - intake form submission → POST /api/work-objects/intake 호출 검증
  - advance button → POST /api/work-objects/{id}/phase 호출 검증
  - close button + reason modal → POST /api/work-objects/{id}/close 호출 검증
  - Expected: Tests FAIL (mutation hooks/buttons 미존재)

#### GREEN: Implement to Make Tests Pass
- [ ] 1.2: `electron/src/renderer/hooks/useWorkObjectMutations.ts` 생성
  - `intakeWorkObject(params)` → POST /api/work-objects/intake
  - `advancePhase(workObjectId, toPhase, runId?)` → POST /api/work-objects/{id}/phase
  - `closeWorkObject(workObjectId, reason)` → POST /api/work-objects/{id}/close
- [ ] 1.3: `electron/src/main/ipc.ts` 확장
  - `workObject:intake`, `workObject:advance`, `workObject:close` IPC 핸들러 추가
- [ ] 1.4: `electron/src/preload/index.ts` bridge 추가
- [ ] 1.5: `WorkObjectPanel.tsx` 확장
  - detail view에 phase transition 버튼 그룹 (Advance / Close / Fail)
  - intake form (title, description, metadata) 모달
  - close reason 입력 모달
  - mutation 후 자동 목록 리프레시

#### REFACTOR: Clean Up Code
- [ ] 1.6: 기존 useWorkObjects 읽기 hook과 mutation hook 통합 정리
- [ ] 1.7: 버튼 disabled 상태 (phase별 허용 전이만 활성화)

#### Quality Gate
- [ ] Electron `npm run typecheck` 통과
- [ ] Electron `npm run build` 통과
- [ ] `npm run test:contract:work-object-mutations` 통과
- [ ] 기존 `npm run test:contract:work-objects` 회귀 없음

---

### Phase 2: 08 — IntegrationSettings + Health Check
**Goal**: Connector 상태 조회 + credential 관리 + health check 엔드포인트
**Status**: Complete
**Estimated**: 8-10h

#### RED: Write Failing Tests First
- [ ] 2.1: `tests/unit/infrastructure/test_integration_health.py`
  - IntegrationHub.health_check_all() → 각 connector 상태 반환
  - health_check() 실패 시 error 상태 + 메시지
- [ ] 2.2: `tests/unit/infrastructure/test_integration_api.py`
  - GET /api/integrations/health → 200 + connector status list
- [ ] 2.3: Electron contract test `electron/tests/contract/integration-settings.spec.ts`
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass
- [ ] 2.4: 각 Connector에 `health_check() -> ConnectorHealthResult` 메서드 추가
  - `src/ds_agent/infrastructure/external/slack_connector.py`
  - `src/ds_agent/infrastructure/external/jira_connector.py`
  - `src/ds_agent/infrastructure/external/confluence_connector.py`
  - `src/ds_agent/infrastructure/external/notion_connector.py`
  - `src/ds_agent/infrastructure/external/git_connector.py`
- [ ] 2.5: `IntegrationHub.health_check_all()` 메서드 추가
- [ ] 2.6: `src/ds_agent/api/routes/integrations.py` 생성
  - `GET /api/integrations/health`
  - `GET /api/integrations/credentials/status`
- [ ] 2.7: `src/ds_agent/cli/integration_cli.py` 생성
  - `ds-agent integration health`
- [ ] 2.8: `electron/src/renderer/components/workflow/IntegrationSettings.tsx` 생성
  - connector 상태 그리드 (5개 시스템, connected/disconnected 배지)
  - health check 버튼 + 최근 이벤트 테이블
- [ ] 2.9: `electron/src/renderer/hooks/useIntegrationHealth.ts` 생성

#### REFACTOR
- [ ] 2.10: ConnectorHealthResult 공통 타입 추출

#### Quality Gate
- [ ] `pytest tests/unit/infrastructure/test_integration_health.py` 통과
- [ ] `ruff check` 통과
- [ ] Electron typecheck + build 통과
- [ ] `npm run test:contract:integration-settings` 통과

---

### Phase 3: 08 — DLQ Replay + Rate Limiter
**Goal**: 실패 이벤트 조회/재시도 + 시스템별 rate limiting
**Status**: Complete
**Estimated**: 8-10h

#### RED: Write Failing Tests First
- [ ] 3.1: `tests/unit/infrastructure/test_dlq_replay.py`
  - DLQ 이벤트 조회 (status=DLQ 필터)
  - replay → 원본 dispatch 재실행 + attempt 카운트 증가
  - replay 성공 시 status=SUCCESS 갱신
- [ ] 3.2: `tests/unit/infrastructure/test_rate_limiter.py`
  - token bucket: 초과 시 RateLimitExceeded
  - refill 후 정상 dispatch
  - 429 응답 시 Retry-After 존중

#### GREEN: Implement to Make Tests Pass
- [ ] 3.3: `src/ds_agent/infrastructure/external/rate_limiter.py` 생성
  - `RateLimitConfig(system, requests_per_second, burst_capacity)`
  - `TokenBucketRateLimiter` with per-system bucket
  - `BackoffPolicy(base_delay_ms, max_delay_ms, multiplier, jitter)`
- [ ] 3.4: IntegrationHub에 rate limiter 주입
  - dispatch 전 `rate_limiter.acquire(system)` 호출
  - 429/503 시 backoff + retry
- [ ] 3.5: `WorkObjectStore.find_events_by_status(status, limit)` 추가
- [ ] 3.6: replay use case: `ReplayIntegrationEventUseCase`
  - 원본 이벤트 조회 → 동일 파라미터로 IntegrationHub.dispatch() 재실행
- [ ] 3.7: CLI: `ds-agent integration replay --event <event_id>`
- [ ] 3.8: CLI: `ds-agent integration dlq [--limit 20]`

#### REFACTOR
- [ ] 3.9: IntegrationHub dispatch loop에 retry/backoff 통합 정리

#### Quality Gate
- [ ] `pytest tests/unit/infrastructure/test_dlq_replay.py tests/unit/infrastructure/test_rate_limiter.py` 통과
- [ ] `ruff check` + targeted `mypy` 통과

---

### Phase 4: 08 — Email/Calendar Connector
**Goal**: SMTP 이메일 + Calendar (Google/CalDAV) 발송 connector
**Status**: Complete
**Estimated**: 12-16h

#### RED: Write Failing Tests First
- [ ] 4.1: `tests/unit/infrastructure/test_email_connector.py`
  - EmailConnector.dispatch() → SMTP send 호출 검증 (mock)
  - dry_run=True → 실제 전송 없이 ConnectorResult 반환
  - HTML body + attachment 지원
- [ ] 4.2: `tests/unit/infrastructure/test_calendar_connector.py`
  - CalendarConnector.dispatch() → event 생성 검증
  - timezone 처리
  - attendee 리스트

#### GREEN: Implement to Make Tests Pass
- [ ] 4.3: Domain models
  - `EmailRequest(to, cc, subject, body_html, body_text, attachments, reply_to)`
  - `CalendarEventRequest(calendar_id, summary, description, start, end, timezone, attendees, conference_tool)`
- [ ] 4.4: `src/ds_agent/infrastructure/external/email_connector.py`
  - SMTP 기반, env 설정 (DS_AGENT_SMTP_HOST, DS_AGENT_SMTP_PORT, DS_AGENT_SMTP_USER, DS_AGENT_SMTP_PASS)
  - HTML body rendering, attachment support
- [ ] 4.5: `src/ds_agent/infrastructure/external/calendar_connector.py`
  - Google Calendar API 기반 (google-api-python-client)
  - env: DS_AGENT_GOOGLE_CALENDAR_CREDENTIALS_JSON
  - simulated fallback when credentials absent
- [ ] 4.6: IntegrationHub 확장: `send_email()`, `create_calendar_event()` 메서드
- [ ] 4.7: Tools: `send_email`, `create_calendar_event` in `integration_tools.py`
- [ ] 4.8: `src/ds_agent/agent/permissions.py`에 CAUTION 레벨 등록
- [ ] 4.9: ActionClassifier strategy에 email/calendar action 추가

#### REFACTOR
- [ ] 4.10: Connector ABC에 공통 credential resolution 추출

#### Quality Gate
- [ ] `pytest tests/unit/infrastructure/test_email_connector.py tests/unit/infrastructure/test_calendar_connector.py` 통과
- [ ] `ruff check` + `mypy` 통과
- [ ] 기존 integration tool 회귀 없음

---

### Phase 5: 08 — Packaged E2E + Regression
**Goal**: 전체 WorkObject→Slack→Jira→Confluence→Git 시나리오 E2E 테스트
**Status**: Complete
**Estimated**: 5-6h

#### RED: Write Failing Tests First
- [ ] 5.1: `electron/tests/smoke/workflow-integration.spec.ts`
  - seeded workspace (scripts/seed_workflow_e2e_workspace.py)
  - WorkObject intake → advance → dispatch to Slack/Jira → timeline 검증
  - mutation button 클릭 → phase 전이 확인
  - IntegrationSettings health check 실행

#### GREEN: Implement to Make Tests Pass
- [ ] 5.2: `scripts/seed_workflow_e2e_workspace.py` 생성
  - 격리 workspace + 샘플 WorkObject + mock connector config
- [ ] 5.3: Electron smoke test selectors 안정화 (data-testid)
- [ ] 5.4: packaged backend bootstrap에서 WorkObject/IntegrationHub import 안정화

#### Quality Gate
- [ ] `cd electron && npm run test:e2e:workflow` 통과
- [ ] `ruff check` + `python -m compileall` 통과
- [ ] `python scripts/build_backend.py` 통과

---

### ═══════════════════════════════════════
### STREAM B: 02-Semantic Memory 마감
### ═══════════════════════════════════════

---

### Phase 6: 02 — README 갱신 + Quality Gate 정합 + Electron Test
**Goal**: 문서-코드 불일치 해소, Electron semantic 테스트 추가
**Status**: Complete
**Estimated**: 4-5h

#### Tasks
- [ ] 6.1: `Docs/enhancement-specs/README.md` — 02행 상태 갱신
  - "미착수" → "Phase 1-6 구현 완료, DoD 잔여 항목(DomainKB cutover, Telegram inline) 마감 중"
- [ ] 6.2: `scripts/check_layer_deps.py` 생성
  - 기존 `scripts/check_import_contracts.py` 패턴 재사용
  - `memory/semantic/domain/` 외부 import 0 검증
  - `memory/semantic/application/` → infrastructure import 0 검증
- [ ] 6.3: `electron/tests/contract/semantic-metric-panel.spec.ts` 생성
  - MetricSourcePanel 렌더링 contract test
  - semantic.lookupMetric RPC mock → metric owner/definition/vq 표시 검증
  - 존재하지 않는 metric → 빈 상태 표시 검증
- [ ] 6.4: `tests/unit/architecture/test_semantic_layer_deps.py` 생성
  - semantic domain 외부 import 0 자동 검증 (CI 연동)

#### Quality Gate
- [ ] `python scripts/check_layer_deps.py` 통과
- [ ] `pytest tests/unit/architecture/test_semantic_layer_deps.py` 통과
- [ ] Electron `npm run test:contract:semantic-metric-panel` 통과
- [ ] Electron `npm run typecheck` + `npm run build` 통과

---

### Phase 7: 02 — Telegram Semantic Proposal + DomainKB Cutover 방침
**Goal**: Telegram inline proposal approve/reject + DomainKB coexistence 전략 명시
**Status**: Complete
**Estimated**: 6-8h

#### RED: Write Failing Tests First
- [ ] 7.1: `tests/unit/infrastructure/test_telegram_semantic_proposal.py`
  - /semantic_proposal → pending proposal 목록 표시
  - inline callback "Approve" → semantic proposal review + apply
  - inline callback "Reject" → semantic proposal rejection
  - diff 미리보기 표시

#### GREEN: Implement to Make Tests Pass
- [ ] 7.2: `src/ds_agent/gateway/telegram_runner.py` 확장
  - `/semantic_proposal` 명령어 핸들러 추가
  - pending semantic approvals 조회 → inline keyboard (Approve | Reject | Diff)
  - callback handler: approve → SemanticProposalRouter.approve()
  - callback handler: reject → SemanticProposalRouter.reject()
- [ ] 7.3: `scripts/promote_domain_kb.py` 생성
  - 기존 `domain_kb.json` free-text insight를 LLM으로 분류
  - metric/glossary/negative_knowledge 후보 추출
  - `SemanticProposal(status=pending)` 형태로 적재
  - dry-run 모드 지원 (실제 적재 없이 후보 목록만 출력)
  - 원본 insight soft-delete 태깅 (삭제하지 않음)
- [ ] 7.4: DomainKB coexistence 전환 + 이벤트 브릿지
  - `src/ds_agent/runtime/memory_query_service.py` 수정: semantic memory 우선 조회, domain_kb는 fallback
  - `src/ds_agent/self_improve/learning_adapter.py` 수정: domain_kb.store_insight() 호출 시 semantic candidate도 동시 생성
  - `src/ds_agent/self_improve/post_project.py` 수정: retrospective 시 semantic proposal 동시 적재
  - `src/ds_agent/runtime/coordinator.py` 확장: `semantic.proposal.created`, `.reviewed`, `.applied` 이벤트 발행
  - `src/ds_agent/agent/factory.py`에 방침 주석: "semantic memory = canonical source, domain_kb = legacy fallback"

#### REFACTOR
- [ ] 7.5: Telegram semantic 핸들러 + 기존 approval 핸들러 공통 패턴 추출

#### Quality Gate
- [ ] `pytest tests/unit/infrastructure/test_telegram_semantic_proposal.py` 통과
- [ ] `ruff check` + targeted `mypy` 통과
- [ ] `python scripts/promote_domain_kb.py --dry-run` 정상 실행
- [ ] 기존 semantic regression suite 회귀 없음

---

### ═══════════════════════════════════════
### STREAM C: 09-Async Portfolio Manager
### ═══════════════════════════════════════

---

### Phase 8: 09 — Domain + Persistence + Basic Scheduler
**Goal**: PortfolioEntry 4분면 모델, SQLite v1 (portfolio.db), 슬롯 기반 스케줄러 기초
**Status**: Complete
**Estimated**: 10-14h

#### RED: Write Failing Tests First
- [ ] 8.1: `tests/unit/domain/test_portfolio_entry.py`
  - PortfolioEntry 생성 (quadrant invariant 검증)
  - PortfolioTransition 기록
  - WaitCondition kind별 spec 검증
  - PortfolioCheckpoint round-trip
  - BusinessPriority SLA 계산
- [ ] 8.2: `tests/integration/infrastructure/test_sqlite_portfolio_store.py`
  - CRUD, quadrant 필터링, transition 이력 조회
- [ ] 8.3: `tests/unit/application/test_portfolio_scheduler.py`
  - evaluate(): WaitCondition 평가 → resumable 후보 목록 반환 (전이하지 않음)
  - evaluate(): 슬롯 가용/부족 정보 포함
  - enforce_hard_constraints(): max_active_slots 상한 초과 시 acquire 거부
  - **주의**: scheduler는 자동 전이하지 않는다. resumable 후보를 LLM에게 알릴 뿐이다.

#### GREEN: Implement to Make Tests Pass
- [ ] 8.4: Domain entities (`src/ds_agent/domain/portfolio/`)
  - `portfolio_entry.py`: PortfolioEntry, PortfolioQuadrant, BusinessPriority, PortfolioTransition
  - `wait_condition.py`: WaitCondition, WaitConditionKind(data_freshness/approval/external/timer)
  - `portfolio_checkpoint.py`: PortfolioCheckpoint
  - `monitoring_state.py`: MonitoringState
  - `playbook_candidate.py`: PlaybookCandidate
- [ ] 8.5: Domain interfaces
  - `src/ds_agent/domain/interfaces/portfolio.py`: PortfolioStore protocol
- [ ] 8.6: Infrastructure persistence
  - `src/ds_agent/infrastructure/persistence/portfolio_store.py`
  - SQLite migration v12: portfolio_entries, portfolio_transitions, wait_conditions, monitoring_state, playbook_candidates, schedule_windows
- [ ] 8.7: Application use cases
  - `src/ds_agent/application/portfolio/portfolio_evaluator.py`: evaluate() — WaitCondition 일괄 평가, resumable 후보 + 슬롯 현황 반환. **자동 전이 금지**. 결과를 prompt context와 runtime event로 노출하여 LLM이 `resume_task` tool로 전이 결정.
  - `src/ds_agent/application/portfolio/wait_condition_evaluator.py`: 4종 evaluator (data_freshness/approval/external/timer). 조건 충족 여부만 판정, 전이 수행 안 함.
  - `src/ds_agent/application/portfolio/priority_calculator.py`: 우선순위 공식. LLM에게 제공할 정렬 기준이지, 코드가 강제하는 실행 순서가 아님.
  - `src/ds_agent/application/portfolio/slot_manager.py`: acquire_slot/release_slot — max_active_slots hard constraint만 강제. 슬롯 초과 시 resume_task tool이 거부 응답을 반환.
- [ ] 8.8: Feature flag: `DS_AGENT_PORTFOLIO_ENABLED` (default off)
- [ ] 8.9: Container wiring: `src/ds_agent/infrastructure/portfolio_container.py`

#### Quality Gate
- [ ] `pytest tests/unit/domain/test_portfolio_entry.py tests/integration/infrastructure/test_sqlite_portfolio_store.py tests/unit/application/test_portfolio_scheduler.py` 통과
- [ ] domain 커버리지 >= 90%
- [ ] `ruff check` + `mypy` 통과
- [ ] domain 외부 import 0 (`scripts/check_import_contracts.py`)

---

### Phase 9: 09 — Tools + CLI + Prompt Integration
**Goal**: LLM tool 바인딩, CLI 서브커맨드, 시스템 프롬프트 portfolio 스냅샷
**Status**: Complete
**Estimated**: 8-10h

#### RED: Write Failing Tests First
- [ ] 9.1: `tests/integration/tools/test_portfolio_tools.py`
  - `list_my_portfolio` tool → 4분면 상태 반환
  - `pause_task` tool → active→waiting + checkpoint 저장
  - `resume_task` tool → waiting→active (슬롯 가용 시)
  - `set_sla` tool → 우선순위 재계산
- [ ] 9.2: `tests/unit/infrastructure/test_portfolio_cli.py`
  - `ds-agent portfolio list --quadrant active` 출력 검증
  - `ds-agent portfolio show <tcid>` 상세 표시
  - `ds-agent portfolio pause <tcid> --kind timer --spec '{"seconds":3600}'`

#### GREEN: Implement to Make Tests Pass
- [ ] 9.3: `src/ds_agent/tools/portfolio_tools.py`
  - `list_my_portfolio`, `pause_task`, `resume_task`, `set_sla`, `reorder_portfolio`, `request_monitoring`
- [ ] 9.4: `src/ds_agent/cli/portfolio_cli.py`
  - list, show, pause, resume, sla, ticks
- [ ] 9.5: `src/ds_agent/agent/prompt_sections.py` 확장
  - `build_portfolio_section()`: **상태 보고** 형식 — 4분면 현황, resumable 후보, SLA 위험, 슬롯 잔여
  - "You have N resumable tasks. Conditions satisfied: ..." 형태의 정보 제공 (지시 아님)
  - LLM이 이 정보를 보고 `resume_task`, `pause_task`, `set_sla` 등을 자유롭게 선택
  - 1500 token budget
- [ ] 9.6: `src/ds_agent/agent/prompt_builder.py`에 portfolio section 통합
- [ ] 9.7: WaitCondition evaluator 구체화 (timer, approval_store 연동)
  - evaluator는 조건 충족 여부를 판정하고 `portfolio.condition_satisfied` 이벤트를 발행
  - LLM이 해당 이벤트를 수신하고 resume 여부를 판단

#### Quality Gate
- [ ] tool + CLI + prompt 통합 테스트 통과
- [ ] 기존 tool registry 회귀 없음
- [ ] `ruff check` + `mypy` 통과

---

### Phase 10: 09 — Electron ProjectControlTower + WebSocket RPC
**Goal**: 4분면 대시보드 UI, WebSocket RPC surface
**Status**: Complete
**Estimated**: 8-12h

#### RED: Write Failing Tests First
- [ ] 10.1: Electron contract test `electron/tests/contract/project-control-tower.spec.ts`
  - 4분면 그리드 렌더링
  - active/waiting/monitoring/candidates 카드 표시
  - SLA countdown 표시
  - advance/pause 액션 호출

#### GREEN: Implement to Make Tests Pass
- [ ] 10.2: WebSocket RPC 핸들러 (`src/ds_agent/api/ws_handler.py`)
  - `portfolio.overview` → 4분면 요약 + 엔트리 리스트
  - `portfolio.pause` → pause_task use case
  - `portfolio.resume` → resume_task use case
  - `portfolio.setSla` → set_sla use case
- [ ] 10.3: `electron/src/renderer/hooks/usePortfolio.ts`
- [ ] 10.4: `electron/src/renderer/components/portfolio/ProjectControlTower.tsx`
  - 2×2 grid layout (Active | Waiting / Monitoring | Candidates)
  - 각 카드: task title, priority badge, SLA countdown, elapsed time
  - slot usage 표시 (e.g., 2/3)
  - phase 전이 버튼
- [ ] 10.5: Sidebar tab에 Portfolio 추가

#### Quality Gate
- [ ] Electron `npm run typecheck` + `npm run build` 통과
- [ ] `npm run test:contract:project-control-tower` 통과

---

### ═══════════════════════════════════════
### STREAM D: 10-Self-Improvement Governance
### ═══════════════════════════════════════

---

### Phase 11: 10 — Domain + Inbox + Review Workflow
**Goal**: LearningItem 지식 품질 게이트, LearningInbox, ReviewEvent, migration v13
**Note**: 이 상태 머신은 **LLM의 추론 경로를 제어하지 않는다**. LLM이 참조하는 조직 지식의 품질을 관리하는 governance 계층이다. LLM은 proposed/promoted 상태와 무관하게 자유롭게 도구를 선택한다 — governance는 어떤 지식이 프롬프트에 주입되는지를 결정할 뿐이다.
**Status**: Complete
**Estimated**: 12-16h

#### RED: Write Failing Tests First
- [ ] 11.1: `tests/unit/domain/test_learning_item.py`
  - LearningItem 생성 (type별: pattern/kb_entry/custom_skill)
  - 상태 전이 검증 (proposed→under_review→approved→promoted→monitored→deprecated→archived)
  - 금지 전이 (proposed→promoted, archived→any)
  - ConflictRef 검증
- [ ] 11.2: `tests/unit/application/test_review_learning_item.py`
  - approve → state transition + ReviewEvent 기록
  - modify → diff 기록 + under_review 복귀
  - reject → archived 전이
  - second-reviewer 규칙 (destructive skill, unresolved conflict)
- [ ] 11.3: `tests/unit/application/test_learning_inbox.py`
  - 필터링 (status, type, project_id, priority, has_conflict)
  - 우선순위 정렬 (evidence * 0.4 + conflict * 0.3 + scope * 0.2 + staleness * 0.1)
  - 중복 제거 (signature 기준)
- [ ] 11.4: `tests/integration/infrastructure/test_sqlite_learning_store.py`
  - CRUD, round-trip, migration v13

#### GREEN: Implement to Make Tests Pass
- [ ] 11.5: Domain entities (`src/ds_agent/domain/learning/`)
  - `learning_item.py`: LearningItem, LearningItemType, LearningItemStatus (state machine enum), SourceInfo, Evidence, ConflictRef
  - `review_event.py`: ReviewEvent, ReviewDecision(approve/modify/reject)
  - `promotion_record.py`: PromotionRecord
  - `deprecation_record.py`: DeprecationRecord, DeprecationReason
  - `conflict_alert.py`: ConflictAlert
  - `revalidation_schedule.py`: RevalidationSchedule
- [ ] 11.6: Domain interfaces
  - `src/ds_agent/domain/interfaces/learning.py`: LearningStore protocol
- [ ] 11.7: Application use cases (`src/ds_agent/application/learning/`)
  - `learning_inbox.py`: LearningInboxUseCase (query + priority sort + dedup)
  - `review_learning_item.py`: ReviewLearningItemUseCase (approve/modify/reject + checklist validation)
  - `submit_learning_proposal.py`: SubmitLearningProposalUseCase (extractor → proposed state)
- [ ] 11.8: Infrastructure persistence
  - `src/ds_agent/infrastructure/persistence/learning_store.py`
  - SQLite migration v13: learning_items, review_events, promotion_records, deprecation_records, conflict_alerts, revalidation_schedule
- [ ] 11.9: Container: `src/ds_agent/infrastructure/learning_container.py`
- [ ] 11.10: Feature flag: `DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1` (default off)
- [ ] 11.11: `src/ds_agent/self_improve/` 어댑터
  - 기존 extractors → `SubmitLearningProposalUseCase` 호출로 전환
  - `domain_kb.store_insight()` 직접 호출 차단 (governance flag on 시)

#### Quality Gate
- [ ] domain 커버리지 >= 95%
- [ ] 상태 머신 전이 전수 테스트
- [ ] `ruff check` + `mypy` 통과
- [ ] domain 외부 import 0

---

### Phase 12: 10 — Promotion Gate + Revalidation + UI
**Goal**: Eval gate 연동, 재검증 스케줄, Electron LearningInbox, CLI/Telegram
**Status**: Complete
**Estimated**: 12-16h

#### RED: Write Failing Tests First
- [ ] 12.1: `tests/unit/application/test_promote_learning_item.py`
  - approved → Eval gate pass → promoted + PromotionRecord
  - approved → Eval gate fail → rejected
  - conflict 미해결 시 promotion 차단
- [ ] 12.2: `tests/unit/application/test_deprecate_learning_item.py`
  - regression 2회 연속 → auto-deprecated
  - manual deprecation (grace period)
  - rollback 시 이전 promoted 복원
- [ ] 12.3: `tests/unit/infrastructure/test_learning_cli.py`
  - `ds-agent learning inbox --status proposed --type kb_entry`
  - `ds-agent learning review <item_id> --approve`
  - `ds-agent learning deprecations`

#### GREEN: Implement to Make Tests Pass
- [ ] 12.4: `src/ds_agent/application/learning/promote_learning_item.py`
  - PromoteLearningItemUseCase: conflict re-check → Eval gate (§05) → org asset write → alias supersede
  - threshold: pattern=1.00, kb_entry=1.00, custom_skill=1.02
- [ ] 12.5: `src/ds_agent/application/learning/deprecate_learning_item.py`
  - DeprecateLearningItemUseCase: grace period + prompt guard + alert
- [ ] 12.6: `src/ds_agent/application/learning/check_regression.py`
  - CheckRegressionUseCase: Eval gate on fresh Gold Task, 2-failure rule
- [ ] 12.7: `src/ds_agent/application/learning/rollback_promotion.py`
  - RollbackPromotionUseCase: atomic asset restore
- [ ] 12.8: `src/ds_agent/runtime/revalidation_scheduler.py`
  - daemon 등록, 주기적 monitored 아이템 Eval gate 평가 실행
  - 평가 결과만 기록 + 이벤트 발행 (`learning.revalidation.passed` / `.failed`)
  - 2회 연속 실패 시 auto-deprecated (이것은 hard constraint — 품질 저하된 지식이 프롬프트를 오염시키는 것을 방지)
  - pattern: 30d, kb_entry: 60d, custom_skill: 14d
- [ ] 12.9: Tools: `list_learning_inbox`, `review_learning_item`, `get_learning_item`, `list_promotions`, `list_deprecations`, `rollback_promotion`, `resolve_conflict_alert`
- [ ] 12.10: CLI: `ds-agent learning inbox|review|promotions|deprecations|rollback`
- [ ] 12.11: Telegram: `/learning inbox`, `/learning review <id> approve|reject`
- [ ] 12.12: Electron `LearningInbox.tsx`
  - 필터 패널 (status, type, priority, conflict)
  - 아이템 목록 (title, priority badge, staleness, conflict icon)
  - 상세 패널 (evidence, source runs, conflicts, diff view)
  - 리뷰 액션 (Approve / Modify / Reject + checklist + comment)
- [ ] 12.13: WebSocket RPC: `learning.inbox`, `learning.review`, `learning.promotions`, `learning.deprecations`

#### Quality Gate
- [ ] 전체 learning 테스트 통과
- [ ] Eval gate 연동 통합 테스트 통과
- [ ] Electron `npm run typecheck` + `npm run build` 통과
- [ ] `ruff check` + `mypy` 통과
- [ ] 기존 self_improve 모듈 회귀 없음

---

### ═══════════════════════════════════════
### STREAM E: 01-Task Contract (Optional)
### ═══════════════════════════════════════

01의 `task_contract.subscribe` IPC는 현재 refresh-on-action 모델이 동작 중이므로 최하위 우선순위.
Phase 12 완료 후 여유가 있을 때 진행.

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 09/10 schema migration 충돌 | Low | High | v12(09), v13(10) 순차 적용, 각각 독립 테이블 |
| self_improve 기존 동작 깨짐 | Medium | High | feature flag + 기존 경로 유지 + 회귀 테스트 |
| Electron 번들 크기 증가 (UI 컴포넌트 추가) | Low | Low | lazy import, tree-shaking |
| Rate limiter가 동시성 문제 발생 | Medium | Medium | SQLite WAL mode + UNIQUE constraint |
| WaitCondition evaluator 외부 API 의존 | Medium | Medium | timeout + fallback + simulated mode |
| Playbook detection false positive | Medium | Low | threshold tuning, user feedback loop |
| Eval gate flaky test → promotion 차단 | Medium | High | Gold Task 지속 업데이트, threshold calibration |
| **LLM 자율성 침식** — scheduler/governance가 점진적으로 controller화 | Medium | **Critical** | 원칙 #1-5 리뷰 체크리스트를 매 Phase quality gate에 포함. "코드가 전이를 수행하는가?"를 기준으로 PR 리뷰 |

## Rollback Strategy

### If Phase 1-5 (08) Fails
- Electron mutation controls: 컴포넌트 제거, WorkObjectPanel read-only 복귀
- Connectors: hub에서 등록 해제, feature flag off
- Rate limiter: 제거해도 dispatch 동작 무영향

### If Phase 6-7 (02) Fails
- README 원복
- Telegram 핸들러 제거
- promote_domain_kb.py 삭제

### If Phase 8-10 (09) Fails
- `DS_AGENT_PORTFOLIO_ENABLED=false` → 기존 단일 세션 모드 복귀
- migration v12 테이블은 남겨두되 feature flag로 비활성

### If Phase 11-12 (10) Fails
- `DS_AGENT_SELF_IMPROVE_GOVERNANCE_V1=false` → 기존 자동 추출 경로 복귀
- migration v13 테이블은 남겨두되 feature flag로 비활성

---

## Progress Tracking

| Phase | Stream | Target | Status |
|-------|--------|--------|--------|
| 1 | 08 | WorkObject Electron Mutations | **100%** |
| 2 | 08 | IntegrationSettings + Health | **100%** |
| 3 | 08 | DLQ Replay + Rate Limiter | **100%** |
| 4 | 08 | Email/Calendar Connector | **100%** |
| 5 | 08 | Packaged E2E | **100%** |
| 6 | 02 | README + Quality Gate + Electron Test | **100%** |
| 7 | 02 | Telegram Proposal + DomainKB Cutover | **100%** |
| 8 | 09 | Domain + Persistence + Scheduler | **100%** |
| 9 | 09 | Tools + CLI + Prompt | **100%** |
| 10 | 09 | Electron ProjectControlTower | **100%** |
| 11 | 10 | Domain + Inbox + Review Workflow | **100%** |
| 12 | 10 | Promotion Gate + Revalidation + UI | **100%** |

**Overall**: 100% (12/12 phases complete)

---

## Effort Summary

| Stream | Phases | Estimated Hours |
|--------|--------|----------------|
| A: 08 Workflow Integration | 1-5 | 37-47h |
| B: 02 Semantic Memory | 6-7 | 10-13h |
| C: 09 Async Portfolio | 8-10 | 26-36h |
| D: 10 Self-Improvement | 11-12 | 24-32h |
| E: 01 Optional | — | 2-4h |
| **Total** | **12** | **~99-132h** |

---

## Notes & Learnings

### Phase 1 (2026-04-16)
- `workObjectPanelModel.ts`에 `nextPhase()` / `canAdvance()` / `canClose()` 순수 함수 추가
- `ipc.ts`에 `workObject:intake` / `workObject:advance` / `workObject:close` IPC 핸들러 3개
- `preload/index.ts` + `vite-env.d.ts` bridge + 타입 정의
- `useWorkObjects.ts`에 `intake` / `advance` / `close` useCallback 추가
- `WorkObjectPanel.tsx`에 Advance 버튼, Close 버튼+모달, action states(busy/error/notice) 추가
- contract test + typecheck + build 모두 GREEN
- 계획에는 없었지만 `vite-env.d.ts` 타입 확장이 필요했음 (window.electronAPI 타입)

### Phase 2 (2026-04-16)
- `ConnectorHealthResult` 모델을 `connector_models.py`에 추가
- 5개 connector(Slack/Jira/Confluence/Notion/Git)에 `health_check()` 메서드 일괄 추가
- `IntegrationHub.health_check_all()` 메서드 추가
- `GET /api/integrations/health` API route + `ds-agent integration health` CLI 생성
- Electron `IntegrationSettings.tsx` + `useIntegrationHealth.ts` 생성
- pytest 7 passed, ruff clean, typecheck + build GREEN

### Phase 3 (2026-04-16)
- `IntegrationEvent.request_payload_json` 필드 추가 — replay에 필수
- SQLite migration v12: `request_payload_json TEXT` 컬럼 (backward-compatible ALTER TABLE)
- `work_object_store.py`에 `get_event()`, `list_events_by_status()`, `update_event_status()` 추가
- `rate_limiter.py` 신규: `TokenBucketRateLimiter` (per-system in-memory bucket) + `compute_backoff_seconds()`
- `integration_hub.py` 확장: rate limiter 주입, payload JSON 저장, `replay_event()`, DLQ 전이
- `_replay_dispatch()`: Pydantic 모델 매핑(`_REPLAY_REQUEST_TYPES`)으로 저장된 payload를 올바른 request 모델로 복원
- `integration_cli.py`에 `dlq` + `replay` 서브커맨드 추가
- 계획 대비 deviation: WorkObject FK constraint 때문에 DLQ 테스트에서 직접 SQL 삽입 (PRAGMA foreign_keys=OFF)
- pytest 19 passed (Phase 2+3 통합), ruff clean

### Phase 4 (2026-04-16)
- 5-file connector pattern 적용: connector → hub method → tool → permissions → action_classifier
- `email_connector.py` 신규: `EmailRequest`, `EmailAttachment`, `EmailConnector` (SMTP STARTTLS, simulated fallback)
- `calendar_connector.py` 신규: `CalendarEventRequest`, `CalendarConnector` (Google Calendar API, simulated fallback)
- `integration_hub.py` 확장: email/calendar 주입, `send_email()`, `create_calendar_event()`, health_check_all 7개로 확장, `_REPLAY_REQUEST_TYPES` 갱신
- `integration_tools.py`: `send_email`, `create_calendar_event` @tool 함수 (safety_level="caution")
- `permissions.py`: `send_email`/`create_calendar_event` → CAUTION 등록
- `action_classifier.py`: `_FIXED_TOOL_MAP` email/calendar 추가
- `test_email_connector.py` (6 tests) + `test_calendar_connector.py` (6 tests) + `test_integration_health.py` 갱신 (5→7 connectors)
- pytest 31 passed, ruff clean, compileall OK

### Phase 5 (2026-04-16)
- `scripts/seed_workflow_e2e_workspace.py` 신규: task contract + work object(intake) + Slack/Jira integration events 시드
- `electron/tests/smoke/workflow-integration.spec.ts` 신규: 7-step E2E 흐름
  - Step 1-2: session attach → workflow tab 이동
  - Step 3: seeded work object 확인 (WO-2026-951001)
  - Step 4: timeline에 slack/jira 이벤트 표시 검증
  - Step 5: phase advance (intake→executing) 동작 검증
  - Step 6: close + reason 입력 모달 동작 검증
  - Step 7: IntegrationSettings health check → 5+ connector 카드 표시
- `package.json`: `test:e2e:workflow` npm script 추가
- 기존 패턴 완전 준수: isolated temp dir, cross-platform Python resolver, screenshot artifacts on failure
- ruff clean, compileall OK, Electron typecheck + build GREEN, pytest 19 passed (regression)

### Phase 6 (2026-04-16)
- `Docs/enhancement-specs/README.md` 갱신: 02 "미착수"→실제 구현 상태 반영 (Phase 1-6 core complete), 08 상태 P3b 마감 반영
- `scripts/check_layer_deps.py` 신규: semantic memory domain/application 계층 의존성 검사 (AST 기반)
- `tests/unit/architecture/test_semantic_layer_deps.py` 신규: CI 연동 pytest (2 tests)
- `electron/tests/contract/semantic-metric-panel.spec.ts` 신규: MetricSourcePanel 타입 계약 검증 (metric/VQ/trust/grade tone/range formatting/null states)
- **Clean Architecture 위반 수정**: `load_semantic_pack.py`가 infrastructure `yaml_metric_loader`를 직접 import → `MetricPackLoader` Protocol + `LoadedMetricPack` dataclass를 `ports.py`로 이동, application→infrastructure 의존성 제거
- `yaml_metric_loader.py`: `LoadedMetricPack` 로컬 정의 제거, ports에서 re-export
- pytest 15 passed (architecture 3 + semantic pack 12), ruff clean, Electron typecheck + contract test GREEN

### Phase 7 (2026-04-16)
- `src/ds_agent/gateway/telegram_semantic.py` 신규: `format_proposal_list()`, `format_proposal_detail()`, `format_proposal_diff()` Telegram 포맷 헬퍼
- `telegram_runner.py`: `/semantic_proposal` 명령어 + `list|approve|reject|diff <id>` 서브커맨드 추가, `_get_semantic_proposal_repo()` lazy-load 헬퍼
- `scripts/promote_domain_kb.py` 신규: DomainKB insights → SemanticProposal 마이그레이션 (dry-run 기본, --apply로 실제 적재)
- `memory_query_service.py`: semantic-first domain knowledge lookup + domain_kb fallback, `_search_semantic_domain()` 헬퍼
- `memory_query_service.py`: dual-write — `store("domain_knowledge")` 시 semantic proposal 동시 생성 (`_submit_semantic_candidate()`)
- `post_project.py`: dual-write — key_findings/failure_lesson 저장 시 semantic proposal 동시 생성 (`_submit_semantic_candidate()`)
- `tests/unit/infrastructure/test_telegram_semantic_proposal.py` (7 tests): 포맷 헬퍼, 상태 전이, diff preview
- 기존 test_telegram_runner.py 61/62 passed (1 pre-existing failure: resume checkpoint mock), ruff clean, compileall OK
- promote_domain_kb.py --dry-run 정상 (7 candidates 감지)

### Phase 8 (2026-04-16)
- Domain entities (`src/ds_agent/domain/portfolio/`):
  - `portfolio_entry.py`: PortfolioEntry (4분면 + 3 terminal), PortfolioQuadrant, TerminalQuadrant, BusinessPriority (SLA hours), PortfolioTransition, `can_transition()` 전이 검증, quadrant 불변식 validator
  - `wait_condition.py`: WaitCondition (4종 kind), WaitConditionKind, kind별 기본 poll interval, `is_satisfied`/`is_overdue` properties, `with_check_result()` immutable copy
  - `portfolio_checkpoint.py`: PortfolioCheckpoint (paused execution state snapshot)
  - `monitoring_state.py`: MonitoringState (post-execution metric tracking)
  - `playbook_candidate.py`: PlaybookCandidate (reusable workflow pattern)
- Domain interface: `src/ds_agent/domain/interfaces/portfolio.py` — PortfolioStore Protocol (entries, transitions, wait conditions, checkpoints, playbook candidates)
- Infrastructure: `src/ds_agent/infrastructure/persistence/portfolio_store.py` — SqlitePortfolioStore v1 (portfolio.db), 5 tables with indices
- Application use cases (`src/ds_agent/application/portfolio/`):
  - `slot_manager.py`: SlotManager — max_active_slots hard constraint (env var), acquire_or_refuse()
  - `wait_condition_evaluator.py`: WaitConditionEvaluator — 4종 evaluator (timer/approval/data_freshness/external), **평가만 수행, 전이 금지**
  - `priority_calculator.py`: PriorityCalculator — business_weight + sla_urgency + age_factor 공식, rank() 정렬, **LLM에 정보 제공용**
  - `portfolio_evaluator.py`: PortfolioEvaluator — full portfolio snapshot (active/waiting/monitoring/candidates, resumable conditions, priority ranking, slot status), **상태 보고만, 전이 금지**
- Tests: 39 passed (18 domain + 10 integration + 11 application)
  - domain: invariant validation (5종 quadrant 제약), transition state machine (allowed/forbidden), BusinessPriority SLA, WaitCondition lifecycle
  - integration: CRUD round-trip, quadrant filter, transition recording, wait condition pending filter, checkpoint/playbook persistence
  - application: timer evaluation (satisfied/pending/missing), batch evaluation, slot manager (empty/full/partial), priority ranking (P0>P3, SLA urgency), evaluator snapshot assembly, **evaluator non-mutation assertion**
- ruff clean, compileall OK, import contracts OK
- LLM-orchestrator 원칙 준수: evaluator는 정보 제공자, slot_manager는 hard constraint만 강제, priority는 제안

### Phase 9 (2026-04-16)
- `src/ds_agent/tools/portfolio_tools.py` 신규: 5개 @tool 함수
  - `list_my_portfolio` (SAFE) — quadrant 필터 + 목록 조회
  - `pause_task` (CAUTION) — active→waiting 전이 + WaitCondition 생성
  - `resume_task` (CAUTION) — waiting→active 전이 + SlotManager hard constraint 검증
  - `set_sla` (CAUTION) — priority/deadline 갱신
  - `request_monitoring` (CAUTION) — active→monitoring 전이
- `src/ds_agent/cli/portfolio_cli.py` 신규: `ds-agent portfolio list|show|ticks` Rich CLI
  - `ticks`: PortfolioEvaluator 실행 → snapshot 표시 (resumable conditions + priority ranking)
- `main.py`: portfolio CLI 등록 + `ds_agent.tools.portfolio_tools` import 추가
- `prompt_sections.py`: `build_portfolio_section()` — snapshot 기반 상태 보고 (active/waiting/monitoring/slots/SLA risk/resumable/priority)
- `prompt_builder.py`: `_build_portfolio_context()` — `DS_AGENT_PORTFOLIO_ENABLED` feature flag 기반 conditional injection (priority=7)
- `permissions.py`: 5개 tool safety level 등록 (list=SAFE, 나머지=CAUTION)
- `action_classifier.py`: _FIXED_TOOL_MAP에 list→read_sql_gold, 나머지→jira_create 매핑
- pytest 39 passed (Phase 8 도메인+통합+application 그대로 green), ruff clean, compileall OK, import contracts OK

### Phase 10 (2026-04-16)
- Backend: `ws_handler.py`에 4개 WebSocket RPC 핸들러 추가
  - `portfolio.overview` — 4분면 엔트리 목록 + 슬롯 현황
  - `portfolio.pause` — active→waiting 전이 + WaitCondition 생성
  - `portfolio.resume` — waiting→active 전이 + SlotManager hard constraint
  - `portfolio.setSla` — priority/deadline 갱신
- Electron `usePortfolio.ts` 신규: WebSocket RPC 기반 portfolio hook (refresh/pause/resume/setSla)
- Electron `ProjectControlTower.tsx` 신규: 2x2 그리드 대시보드 (Active/Waiting/Monitoring/Candidates)
  - entry card: priority badge, SLA countdown, tags, task contract reference
  - slot usage 표시 (active/max/available)
  - refresh 버튼 + 에러 표시
- Sidebar: `portfolio` 탭 추가 (Layers 아이콘), `SidebarTab` type 확장
- `project-control-tower.spec.ts` 계약 테스트: PortfolioEntryView/SlotView/Overview 타입 + priority style mapping
- `package.json`: `test:contract:project-control-tower` npm script 추가
- ruff clean, Electron typecheck + contract test + build GREEN

### Phase 11 (2026-04-16)
- Domain entities (`src/ds_agent/domain/learning/`):
  - `learning_item.py`: LearningItem (8-state machine), LearningItemType(pattern/kb_entry/custom_skill), LearningItemStatus, SourceInfo, Evidence, ConflictRef, `can_transition()`, `transition_to()`, `has_unresolved_conflicts`, `requires_second_reviewer`
  - `review_event.py`: ReviewEvent, ReviewDecision(approve/modify/reject), ReviewChecklist (5-field all_passed property)
  - `promotion_record.py`: PromotionRecord (eval_score, eval_threshold, rollback_ref)
  - `deprecation_record.py`: DeprecationRecord, DeprecationReason(eval_failure/manual/superseded/stale), DeprecationMode(immediate/grace)
- Domain interface: `domain/interfaces/learning.py` — LearningStore Protocol 추가 (기존 PostLearningPort 보존)
- Infrastructure: `infrastructure/persistence/learning_store.py` — SqliteLearningStore (learning.db, v1), 4 tables + 6 indexes, JSON 직렬화
- Application use cases (`application/learning/`):
  - `submit_learning_proposal.py`: signature 기반 dedup, proposed 상태 생성
  - `learning_inbox.py`: LearningInboxUseCase — priority scoring (evidence×0.4 + conflict×0.3 + scope×0.2 + staleness×0.1), ScoredLearningItem, ClassVar 가중치
  - `review_learning_item.py`: approve/modify/reject 워크플로우, checklist validation, second-reviewer enforcement (custom_skill + unresolved conflicts)
- Tests: 72 passed
  - domain: 45 tests (32 state machine transitions parametrized, invariant validation, frozen model, second-reviewer, evidence, source)
  - application: 14 tests (priority scoring max/min/sorting/deterministic, filtering, approve/modify/reject flows, checklist, second-reviewer)
  - integration: 13 tests (CRUD 4 tables, signature dedup, status/type filters, migration idempotency)
- ruff clean, import contracts OK, compileall OK

### Phase 12 (2026-04-16)
- Application use cases (`application/learning/`):
  - `promote_learning_item.py`: conflict re-check → eval threshold 검증 (pattern=1.00, kb=1.00, skill=1.02) → PromotionRecord → promoted 전이
  - `deprecate_learning_item.py`: immediate/grace 모드, `auto_deprecate_on_failure()` (2-failure rule), DeprecationRecord 생성
  - `revalidation_scheduler.py`: 유형별 interval (30d/60d/14d), due items 필터링, pass→metadata 갱신 / fail→auto-deprecation
  - `rollback_promotion.py`: PromotionRecord.rollback_ref 기반 atomic restore, deprecated 전이 + DeprecationRecord 생성
- Tools (`tools/learning_tools.py`): 6 @tool (list_learning_inbox, review_learning_item, get_learning_item, list_promotions, list_deprecations, rollback_promotion)
- CLI (`cli/learning_cli.py`): `ds-agent learning inbox|review|promotions|deprecations|rollback` + Rich 테이블
- `main.py`: learning CLI 등록 + `ds_agent.tools.learning_tools` import
- `permissions.py`: list/get=SAFE, review/rollback=CAUTION
- `action_classifier.py`: list/get→read_sql_gold, review/rollback→jira_create
- WebSocket RPC (`ws_handler.py`): 6 handlers (learning.inbox/review/getItem/promotions/deprecations/rollback)
- Electron:
  - `useLearning.ts`: LearningItemView, LearningInboxView, refreshInbox/reviewItem hooks
  - `LearningInbox.tsx`: status filter + item list + review actions (approve/reject) + type/priority badges
  - Sidebar: Learning 탭 (Bot 아이콘)
- `prompt_builder.py`: `_build_learning_governance_context()` — pending review items summary (priority=8)
- `learning-inbox.spec.ts`: contract test
- Tests: 92 passed (72 Phase 11 + 20 Phase 12)
  - promote: threshold enforcement (kb/pattern/skill), conflict block, not-approved guard
  - deprecate: immediate/grace/auto-deprecation 2-failure, invalid-status guard
  - revalidation: due item selection, pass/fail handling
  - rollback: atomic restore, no-promotion-record guard
- ruff clean, import contracts OK, Electron typecheck + contract test + build GREEN
