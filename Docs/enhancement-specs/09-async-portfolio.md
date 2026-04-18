# 09 — Async Portfolio Manager 상세 구현 스펙

> 본 문서는 `Docs/ds-agent-enhancement-roadmap.md` §9 "Async Portfolio Manager — 비동기 업무 큐" 항목을 실제 구현 가능한 수준으로 구체화한 스펙이다. 기존 `src/ds_agent/runtime/` 하위의 `task_ledger`, `run_registry`, `standing_order_tools`, `delivery_policy_store`, `background_task_manager`, `checkpoint_store` 모듈을 확장하는 방향으로 기술되며, Clean Architecture와 LLM orchestrator 원칙을 따른다.

---

## 1. 배경 및 문제 정의

현재 DS Agent는 "채팅 세션 하나를 잘 도는" 구조에 가깝다. `Coordinator`가 사용자 입력을 받아 도구를 호출하고, `RunRegistry`가 단일 실행 단위를 추적하며, `BackgroundTaskManager`가 장시간 작업을 스레드/프로세스로 분리한다. 그러나 Hermes-style 자율 에이전트의 본질은 **한 번에 하나의 응답을 생성하는 것이 아니라, 여러 업무를 동시에 소유하고 각 업무의 상태·기한·종속성·재개 시점을 스스로 관리하는 것**이다.

현실적 시나리오:

- TC-042 (Churn 분석, 23분째 러닝 중) 와 TC-043 (매출 예측 리프레시) 이 동시에 활성 상태.
- TC-044 (Pricing AB Test) 는 원천 데이터 도착을 기다리는 중.
- TC-045 (Fraud 모델 재학습) 은 사람의 승인 대기 상태.
- TC-038 (Churn 모델 v2) 은 배포 후 7일째 성능 모니터링 중.
- 사용자는 quiet hours(22:00~08:00) 동안 긴급하지 않은 알림을 원치 않음.
- Change window(화~목 10:00~16:00) 외에는 프로덕션 배포 금지.

현 구조로는 위 상태들을 일관된 모델로 표현할 수 없다. `task_ledger.py`는 단일 작업의 lifecycle을 기록하지만, "여러 업무 간 우선순위", "SLA 기반 스케줄링", "대기 조건 평가", "동시 실행 슬롯 관리"는 명시적 도메인 개념이 아니다. `standing_order_tools.py`는 모니터링을 위한 기반이지만 포트폴리오 전체 관점에서 사용되지 않는다.

이 스펙은 이 격차를 메우기 위해 **PortfolioState** 도메인과 **PortfolioScheduler** 유스케이스를 도입한다.

## 2. 핵심 테제

1. **에이전트는 세션이 아니라 포트폴리오를 운영한다.** 단위는 TaskContract이며, 포트폴리오는 TaskContract 집합의 상태 뷰.
2. **상태는 4분면으로 환원된다.** Active / Waiting / Monitoring / Playbook Candidates. 모든 업무는 정확히 하나의 분면에 속한다.
3. **스케줄러는 제약만 검사하고, 우선순위 판단은 LLM이 수행한다.** SLA·quiet hours·change window·동시 실행 상한은 결정론적 규칙 엔진으로 처리하되, "어느 업무를 먼저 진행할지"의 미세 조정은 LLM orchestrator의 권한이다. 규칙 엔진은 후보를 필터링하고, LLM이 정책 컨텍스트 하에서 선택한다.
4. **대기 → 재개는 일급 시민이다.** WaitCondition은 타이머·이벤트·외부 상태 체크 등으로 명시적으로 표현되며, 평가기가 주기적으로 검사하여 재개 가능 여부를 반환한다.
5. **모든 상태 전이는 감사 가능하다.** 분면 전이, 우선순위 재계산, 스케줄러 결정은 `runtime_event_log` 및 `task_ledger`에 구조화되어 남는다.
6. **체크포인트는 대기 진입의 필수 절차다.** 상태 저장 없이 Waiting으로 전이할 수 없다. 크래시 복구 시 동일 지점에서 재개 가능해야 한다.

## 3. 포트폴리오 상태 모델

포트폴리오는 TaskContract의 상태를 네 분면으로 분할한다.

```
            +----------------------+----------------------+
            | Active               | Waiting              |
            | (실행 중 / 슬롯 점유) | (조건 충족 대기)      |
            +----------------------+----------------------+
            | Monitoring           | Playbook Candidates  |
            | (배포 후 관찰)        | (패턴 승격 후보)      |
            +----------------------+----------------------+
```

### 3.1 분면 정의

| 분면 | 의미 | 점유 자원 | 종료 조건 |
|------|------|----------|-----------|
| Active | TaskContract가 현재 실행 중. `RunRegistry`에 러닝 run이 연결됨. | 동시 실행 슬롯 1개 | 성공/실패/중단/일시정지 |
| Waiting | 실행은 중단되었으나 업무는 살아있음. WaitCondition이 붙어 있음. | 슬롯 미점유 | WaitCondition 충족 시 Active 복귀, 또는 취소 |
| Monitoring | 주요 작업(배포·모델 릴리스 등) 완료 후 지정 기간 동안 결과 지표를 관찰. `standing_order_tools`가 주기적 체크 수행. | 슬롯 미점유, 체크 틱마다 단기 Active 전이 | 관찰 기간 만료 또는 이슈 발생(→ Active 복귀) |
| Playbook Candidates | 반복 패턴이 감지되어 MissionPack 승격 검토 중. 실행 주체가 아니라 메타 작업. | 슬롯 미점유 | 승격 승인(→ MissionPack 생성) 또는 거부 |

### 3.2 전이 조건

허용되는 전이(방향성 그래프):

- `Draft` → `Active`: 최초 실행 시작. TaskContract가 승인되고 슬롯이 확보될 때.
- `Active` → `Waiting`: `pause_task`, wait_for_data, wait_for_approval 호출.
- `Active` → `Monitoring`: 배포/릴리스 완료 후 관찰 요청.
- `Active` → `Completed`: 최종 산출물 전달 완료.
- `Waiting` → `Active`: WaitCondition 충족 + 슬롯 가용.
- `Waiting` → `Cancelled`: 타임아웃 또는 명시 취소.
- `Monitoring` → `Active`: 이상 징후 감지.
- `Monitoring` → `Completed`: 관찰 기간 종료, 안정 확인.
- `*` → `Playbook Candidates`: 패턴 감지기가 반복 패턴을 발견.
- `Playbook Candidates` → `Archived`: 승격 또는 기각.

금지 전이(예시):

- `Completed` → `Active` (재실행은 새 TaskContract로 처리).
- `Monitoring` → `Waiting` (모니터링 중단은 Completed 또는 Active로 복귀 후 재설계).

모든 전이는 `PortfolioTransition` 이벤트로 기록된다.

## 4. PortfolioEntry 스키마

도메인 엔티티. Pydantic v2로 정의. 외부 라이브러리 의존은 Pydantic 한정(도메인 내부 허용 표준).

```python
# src/ds_agent/domain/portfolio/portfolio_entry.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field

class PortfolioQuadrant(str, Enum):
    ACTIVE = "active"
    WAITING = "waiting"
    MONITORING = "monitoring"
    PLAYBOOK_CANDIDATE = "playbook_candidate"

class BusinessPriority(str, Enum):
    P0 = "P0"   # SLA 4h
    P1 = "P1"   # SLA 1 business day
    P2 = "P2"   # SLA 3 business days
    P3 = "P3"   # best-effort

class PortfolioEntry(BaseModel):
    entry_id: str                       # ULID
    task_contract_id: str               # §01 TaskContract 참조
    quadrant: PortfolioQuadrant
    business_priority: BusinessPriority
    sla_deadline: Optional[datetime]    # business calendar 반영된 절대 시각
    parent_run_id: Optional[str]        # RunRegistry run_id (Active/Monitoring 시)
    wait_condition_id: Optional[str]    # WaitCondition 참조 (Waiting 시)
    monitoring_metric_ref: Optional[str]  # MonitoringState 참조 (Monitoring 시)
    playbook_candidate_ref: Optional[str] # Playbook 후보 참조
    created_at: datetime
    updated_at: datetime
    last_transition_at: datetime
    transition_history: list["PortfolioTransition"] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

class PortfolioTransition(BaseModel):
    from_quadrant: Optional[PortfolioQuadrant]
    to_quadrant: PortfolioQuadrant
    reason: str
    actor: Literal["scheduler", "llm", "user", "system"]
    at: datetime
```

불변식(invariants):

- `quadrant == ACTIVE` 이면 `parent_run_id` 필수.
- `quadrant == WAITING` 이면 `wait_condition_id` 필수이고 `parent_run_id`는 None.
- `quadrant == MONITORING` 이면 `monitoring_metric_ref` 필수.
- `quadrant == PLAYBOOK_CANDIDATE` 이면 `playbook_candidate_ref` 필수.
- SLA deadline이 존재하면 현재 시각과 비교 가능해야 함(타임존은 UTC 저장, 표시 시 변환).

## 5. WaitCondition 유형

Waiting 분면의 업무는 하나의 WaitCondition을 갖는다. 각 유형은 평가기(evaluator)를 통해 "충족 여부"를 반환한다.

```python
class WaitConditionKind(str, Enum):
    DATA_FRESHNESS = "data_freshness"
    APPROVAL = "approval"
    EXTERNAL_RESOURCE = "external_resource"
    TIMER = "timer"

class WaitCondition(BaseModel):
    condition_id: str
    kind: WaitConditionKind
    spec: dict                         # kind별 payload
    created_at: datetime
    deadline: Optional[datetime]       # 이후에도 미충족이면 escalate
    last_checked_at: Optional[datetime]
    last_check_result: Optional[str]   # "pending" | "satisfied" | "failed"
    poll_interval_s: int               # 기본: kind별 기본값
```

### 5.1 유형별 체크 메커니즘

| 유형 | spec 필드 예 | 체크 메커니즘 | 기본 poll 주기 |
|------|-------------|--------------|----------------|
| data_freshness | `{"dataset":"fact_orders","min_freshness":"PT15M"}` | 데이터 카탈로그 어댑터에 최신 파티션 timestamp 질의, 기준 충족 시 satisfied | 5분 |
| approval | `{"approval_id":"apr_abc","approver_roles":["ds_lead"]}` | `approval_store`의 상태 조회 | 30초(이벤트 driven 우선, 폴링은 보완) |
| external_resource | `{"kind":"warehouse_ready","cluster":"dw-prod"}` | 외부 헬스체크 어댑터 호출 | 1분 |
| timer | `{"resume_at":"2026-04-16T09:00:00Z"}` | 현재 시각 비교 | 60초 |

이벤트 기반 notify 경로(예: `approval_store`의 콜백)가 있다면 WaitConditionEvaluator는 폴링과 독립적으로 즉시 재평가를 트리거한다.

### 5.2 타임아웃 및 에스컬레이션

- `deadline` 경과 후에도 미충족이면 해당 Entry는 `Cancelled` 또는 `Escalated` 상태로 이동.
- Escalation 정책은 §14 알림 정책과 연동: P0 업무의 approval 미응답 시 critical 채널로 재전송.

## 6. 스케줄링 규칙

PortfolioScheduler는 **결정론적 제약 검사기**이다. 무엇을 "얼마나 하라"는 LLM이 말하지만, 무엇을 "해도 되는지"는 스케줄러가 결정한다.

### 6.1 규칙 목록

1. **SLA 규칙**
   - P0: `sla_deadline = created_at + 4h`
   - P1: `sla_deadline = created_at + 1 business day` (영업일 기준, 주말/공휴일 제외)
   - P2: `+ 3 business days`
   - P3: 없음
2. **Quiet hours**: 로컬 시간 22:00~08:00. 실행은 계속되되 **알림 전송은 critical이 아니면 큐잉**. 실행 자체를 막지는 않는다(§14 참조).
3. **Change window**: 화·수·목 10:00~16:00 현지 시각에만 "deploy" 태그가 붙은 TaskContract가 Active 전이 가능. 외 시간대는 Waiting 유지.
4. **동시 실행 상한**: `max_active_slots = 3` (설정 가능). Active 분면의 Entry 수가 상한을 초과할 수 없다.
5. **우선순위 존중**: 슬롯 경합 시 §7의 우선순위 점수가 높은 Entry부터 Active 진입.
6. **Monitoring 체크 틱**: Monitoring Entry는 체크 주기(기본 24h) 도래 시 단기 Active 전이하여 `standing_order_tools.run_standing_check`를 실행하고 즉시 복귀. 이 단기 전이는 슬롯을 점유하지 않는다(별도 queue).

### 6.2 규칙 엔진 설계

```python
# src/ds_agent/application/portfolio/scheduler_rules.py
class SchedulerRule(Protocol):
    name: str
    def evaluate(
        self, entry: PortfolioEntry, context: SchedulerContext
    ) -> RuleDecision: ...

@dataclass
class RuleDecision:
    allow: bool
    reason: str
    next_eval_hint: Optional[datetime] = None
```

규칙은 순서가 있다: 하드 제약(change window, 동시 실행) → 소프트 힌트(quiet hours, priority). 하나라도 `allow=False`이면 전이 불가이며, 이유가 `transition_history.reason`에 기록된다.

## 7. Priority Queue

Waiting→Active 전이 후보가 여럿일 때 스케줄러는 우선순위 점수로 정렬한다.

### 7.1 우선순위 공식

```
priority_score =
    w_deadline * deadline_urgency(entry)
  + w_business * business_weight(entry.business_priority)
  + w_depchain * dependency_chain_score(entry)
  - w_starvation_penalty * recent_preemptions(entry)
```

- `deadline_urgency`: `max(0, 1 - time_remaining / sla_window)` 클리핑 [0,1].
- `business_weight`: P0=1.0, P1=0.6, P2=0.3, P3=0.1.
- `dependency_chain_score`: 이 Entry를 기다리는 다른 Entry 수 / 총 Entry 수.
- `recent_preemptions`: 최근 1시간 내 선점된 횟수(기아 방지).

기본 가중치: `w_deadline=0.5, w_business=0.3, w_depchain=0.2, w_starvation_penalty=0.1`. 설정 가능.

### 7.2 재정렬 트리거

- 새 Entry 생성/완료 시.
- SLA deadline 경과 시(매분 타이머).
- WaitCondition 충족 시.
- `set_sla` 도구 호출로 우선순위 변경 시.
- LLM orchestrator가 `reorder_portfolio` 도구로 명시적 재정렬 요청 시(LLM의 판단을 반영하는 공식 경로).

## 8. Monitoring 상태 처리

Monitoring 분면은 배포/릴리스 후 일정 기간 동안 모델·파이프라인을 관찰하기 위한 분면이다.

### 8.1 관찰 파라미터

- `watch_duration_days`: 기본 14일.
- `check_cadence`: cron 표현식. 기본 `0 9 * * *` (매일 09:00 로컬).
- `metrics`: 관찰 지표 목록 + 임계값(§03 Verifier가 제공한 계약 기반).
- `exit_conditions`: (1) duration 만료 + 이상 없음 → Completed. (2) 이상 감지 → Active 복귀하여 인시던트 TaskContract 생성.

### 8.2 standing_order_tools와의 관계

기존 `standing_order_tools.py`는 일반적 정기 작업을 위한 모듈이다. Monitoring 분면은 그 위에 "포트폴리오 인식(aware)" 얇은 어댑터를 얹는다.

- 신규 파일: `src/ds_agent/runtime/portfolio_monitoring.py`
- 책임: MonitoringState ↔ StandingOrder 바인딩, 체크 결과를 PortfolioEvent로 변환.
- StandingOrder에 `origin_portfolio_entry_id` 필드를 추가한다.

### 8.3 정기 체크 흐름

1. 스케줄러 타이머가 MonitoringEntry의 `next_check_at`에 도달.
2. `run_monitoring_check(entry)` → standing order 실행.
3. 결과 메트릭을 Verifier 계약과 비교.
4. 위반 시 → Active 복귀, 인시던트 TaskContract 스폰.
5. 통과 시 → `last_check_at`, `next_check_at` 갱신. Entry는 Monitoring 유지.

## 9. Playbook Candidate 승격

반복 패턴을 감지하여 MissionPack 초안으로 승격한다. §04 MissionPack 및 §10 Self-Improvement Governance와 연계.

### 9.1 감지 메커니즘

- `PatternDetector` 유스케이스: 완료된 TaskContract 스트림을 입력으로 받아, (a) 유사한 요청 문장, (b) 유사한 도구 호출 시퀀스, (c) 유사한 산출물 템플릿을 찾는다.
- 유사도 임계값 초과 + 최근 N=30일 동안 K=3회 이상 반복 시 Playbook Candidate 생성.
- 감지는 비동기 배치(일 1회) + 트리거 기반(업무 완료 직후 경량 체크).

### 9.2 승격 파이프라인

1. 감지기 → `PlaybookCandidate` 생성 (분면: Playbook Candidates).
2. 에이전트가 MissionPack **초안**을 자동 생성(도구 시퀀스, 입력 파라미터 템플릿, 체크리스트).
3. 사용자/리드에게 제안 알림(§14 정책 준수).
4. 승인 시 §04 MissionPack 등록 + 커스텀 스킬 등록(§10 governance 절차 경유).
5. 거부/유보 시 Archived 상태로 이동하고 감지 차단 해시를 기록하여 재제안 과잉 방지.

### 9.3 §10과의 연계

MissionPack 승격은 "학습 결과의 조직 표준화"이므로 §10에서 정의하는 거버넌스 절차(리뷰어, 테스트 배드 통과, 버전 태그)를 따른다. Playbook Candidate는 §10의 "Promotion Queue" 단일 엔트리로 투입된다.

## 10. 체크포인트 및 재개

대기 상태 진입 또는 장시간 Active 유지 시, `checkpoint_store`를 활용해 재개 가능한 스냅샷을 저장한다.

### 10.1 저장되는 것

```python
class PortfolioCheckpoint(BaseModel):
    checkpoint_id: str
    entry_id: str
    at: datetime
    run_id: Optional[str]
    working_memory_snapshot_ref: str   # working_memory blob 포인터
    last_tool_call_idx: int
    pending_tool_args: Optional[dict]
    wait_condition_id: Optional[str]
    resumption_hint: str               # LLM이 재개 시 참조할 short note
```

### 10.2 체크포인트 트리거

- Active → Waiting 전이 전에 필수.
- Active 30분 경과 시 자동(장시간 run 보호).
- 명시적 `checkpoint_task` 도구 호출.
- 프로세스 종료 신호(SIGTERM) 수신 시.

### 10.3 재개 흐름

1. WaitCondition 충족 또는 크래시 복구 트리거.
2. `checkpoint_store.load(entry_id)` → 최신 체크포인트 획득.
3. Working memory 복원 → 새 run_id 할당 → Coordinator에 "resumption" 프레임으로 주입.
4. LLM에게 `resumption_hint` + 직전 도구 호출 결과를 시스템 컨텍스트로 제공.
5. 첫 번째 액션이 "재개 확인" 요약이 되도록 프롬프트 지시.

### 10.4 크래시 복구 흐름

- 프로세스 부팅 시 `startup_recovery`가 `task_ledger`에서 "dangling Active" Entry를 탐지.
- 각 Entry에 대해 가장 최근 체크포인트 로드 후 Waiting(kind=external_resource, spec="awaiting_recovery")로 이동.
- 관리자 또는 정책에 따라 Active 재진입 여부 결정.

## 11. Clean Architecture 매핑

| 레이어 | 모듈 | 기존/신규 | 역할 |
|--------|------|----------|------|
| Domain | `domain/portfolio/portfolio_entry.py` | 신규 | PortfolioEntry, PortfolioQuadrant, Transition |
| Domain | `domain/portfolio/wait_condition.py` | 신규 | WaitCondition 타입 |
| Domain | `domain/portfolio/monitoring_state.py` | 신규 | MonitoringState |
| Domain | `domain/portfolio/playbook_candidate.py` | 신규 | PlaybookCandidate |
| Domain | `domain/portfolio/errors.py` | 신규 | InvalidTransitionError 등 |
| Application | `application/portfolio/scheduler.py` | 신규 | PortfolioScheduler 유스케이스 |
| Application | `application/portfolio/wait_evaluator.py` | 신규 | WaitConditionEvaluator 유스케이스 |
| Application | `application/portfolio/priority.py` | 신규 | 우선순위 계산 순수 함수 |
| Application | `application/portfolio/promotion.py` | 신규 | Playbook 승격 파이프라인 |
| Application | `application/portfolio/ports.py` | 신규 | Repository/Clock/ApprovalGateway 포트 |
| Infrastructure (runtime 확장) | `runtime/task_ledger.py` | 확장 | quadrant·transition 기록 |
| Infrastructure | `runtime/run_registry.py` | 확장 | 동시 실행 슬롯 관리, 슬롯 이벤트 발행 |
| Infrastructure | `runtime/standing_order_tools.py` | 확장 | `origin_portfolio_entry_id` 추가 |
| Infrastructure | `runtime/delivery_policy_store.py` | 확장 | quiet hours/change window 정책 저장 |
| Infrastructure | `runtime/background_task_manager.py` | 확장 | scheduler tick 스레드 호스트 |
| Infrastructure | `runtime/checkpoint_store.py` | 확장 | PortfolioCheckpoint 포맷 추가 |
| Infrastructure | `runtime/portfolio_monitoring.py` | 신규 | Monitoring ↔ standing_order 어댑터 |
| Infrastructure | `infrastructure/portfolio/sqlite_repo.py` | 신규 | PortfolioRepository 구현 |
| Presentation (tools) | `ds_agent/tools/portfolio_tools.py` | 신규 | @tool 함수들(§13) |
| Presentation | `ds_agent/cli/portfolio_cmd.py` | 신규 | CLI subcommand |
| Presentation | Electron `ProjectControlTower` | 신규 | 4분면 대시보드 |

의존 규칙 요점:

- Domain은 외부 라이브러리(Pydantic 제외) 및 `runtime`/`infrastructure`에 의존하지 않는다.
- Application은 Domain과 포트 인터페이스에만 의존한다. `runtime` 모듈을 직접 import하지 않는다.
- Runtime(Infrastructure)은 Application 포트를 구현한다.

## 12. SQLite 스키마 (migration v12)

기존 마이그레이션(`migrations/` 관례)에 v12를 추가한다. 모든 테이블은 WAL 모드 가정, 인덱스는 최소 조회 패턴 기준.

```sql
-- portfolio_entries
CREATE TABLE portfolio_entries (
    entry_id TEXT PRIMARY KEY,
    task_contract_id TEXT NOT NULL,
    quadrant TEXT NOT NULL CHECK(quadrant IN ('active','waiting','monitoring','playbook_candidate','archived','completed','cancelled')),
    business_priority TEXT NOT NULL CHECK(business_priority IN ('P0','P1','P2','P3')),
    sla_deadline TEXT,
    parent_run_id TEXT,
    wait_condition_id TEXT,
    monitoring_metric_ref TEXT,
    playbook_candidate_ref TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_transition_at TEXT NOT NULL
);
CREATE INDEX ix_portfolio_entries_quadrant ON portfolio_entries(quadrant);
CREATE INDEX ix_portfolio_entries_deadline ON portfolio_entries(sla_deadline);
CREATE INDEX ix_portfolio_entries_task ON portfolio_entries(task_contract_id);

-- portfolio_transitions (감사용)
CREATE TABLE portfolio_transitions (
    transition_id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES portfolio_entries(entry_id),
    from_quadrant TEXT,
    to_quadrant TEXT NOT NULL,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE INDEX ix_portfolio_transitions_entry ON portfolio_transitions(entry_id, at);

-- wait_conditions
CREATE TABLE wait_conditions (
    condition_id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES portfolio_entries(entry_id),
    kind TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    deadline TEXT,
    last_checked_at TEXT,
    last_check_result TEXT,
    poll_interval_s INTEGER NOT NULL DEFAULT 60
);
CREATE INDEX ix_wait_conditions_entry ON wait_conditions(entry_id);
CREATE INDEX ix_wait_conditions_next_check ON wait_conditions(last_checked_at, poll_interval_s);

-- schedule_windows (quiet hours, change window)
CREATE TABLE schedule_windows (
    window_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('quiet_hours','change_window','custom')),
    name TEXT NOT NULL,
    cron_expr TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    tz TEXT NOT NULL,
    applies_to_tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);

-- monitoring_state
CREATE TABLE monitoring_state (
    state_id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES portfolio_entries(entry_id),
    standing_order_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    watch_duration_days INTEGER NOT NULL,
    last_check_at TEXT,
    last_check_status TEXT,
    last_check_payload_json TEXT,
    next_check_at TEXT
);
CREATE INDEX ix_monitoring_state_next ON monitoring_state(next_check_at);

-- playbook_candidates
CREATE TABLE playbook_candidates (
    candidate_id TEXT PRIMARY KEY,
    pattern_hash TEXT NOT NULL,
    sample_task_contract_ids_json TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    proposed_mission_pack_draft_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('proposed','reviewing','approved','rejected','archived')),
    decided_at TEXT,
    decided_by TEXT
);
CREATE UNIQUE INDEX ux_playbook_candidates_hash ON playbook_candidates(pattern_hash);
```

## 13. 주요 도구 / 유스케이스

### 13.1 @tool 함수

```python
# src/ds_agent/tools/portfolio_tools.py

@tool
def list_my_portfolio(quadrant: Optional[str] = None) -> list[dict]:
    """현재 포트폴리오의 Entry들을 4분면별로 반환. LLM이 상황 파악/계획에 사용."""

@tool
def pause_task(
    task_contract_id: str,
    wait_condition_kind: str,
    wait_condition_spec: dict,
    deadline: Optional[str] = None,
    reason: str = "",
) -> dict:
    """Active → Waiting 전이. 체크포인트 자동 저장."""

@tool
def resume_task(task_contract_id: str, reason: str = "") -> dict:
    """Waiting → Active 강제 재개. WaitCondition을 satisfied로 마킹하고 슬롯 확보 시도."""

@tool
def set_sla(task_contract_id: str, business_priority: str, note: str = "") -> dict:
    """Entry의 business_priority 변경 → sla_deadline 재계산, 우선순위 재정렬."""

@tool
def reorder_portfolio(
    preferred_order: list[str], reason: str
) -> dict:
    """LLM이 명시적으로 우선순위 조정 의도를 표명하는 경로. 스케줄러는 제약 위배가 없는 범위에서 반영."""

@tool
def request_monitoring(
    task_contract_id: str,
    watch_duration_days: int = 14,
    check_cadence_cron: str = "0 9 * * *",
    metrics: list[dict] = [],
) -> dict:
    """Active → Monitoring 전이 요청."""
```

### 13.2 PortfolioScheduler 유스케이스

```python
class PortfolioScheduler:
    def __init__(
        self, repo: PortfolioRepository, clock: Clock,
        run_slots: RunSlotGateway, rules: Sequence[SchedulerRule],
        wait_evaluator: WaitConditionEvaluator,
        event_log: PortfolioEventLogPort,
    ): ...

    def tick(self) -> SchedulerTickReport:
        """주기 호출. WaitCondition 평가 → 후보 정렬 → 슬롯 할당 → 전이 실행."""

    def request_transition(
        self, entry_id: str, to: PortfolioQuadrant, reason: str, actor: str
    ) -> TransitionResult:
        """도구 호출 진입점. 규칙 검사 후 전이."""
```

### 13.3 WaitConditionEvaluator 유스케이스

```python
class WaitConditionEvaluator:
    def __init__(self, adapters: Mapping[WaitConditionKind, WaitConditionAdapter], clock: Clock): ...

    def evaluate(self, condition: WaitCondition) -> EvaluationOutcome:
        """adapter 호출 → satisfied/pending/failed 반환."""

    def evaluate_due(self, now: datetime) -> list[EvaluationOutcome]:
        """last_checked_at + poll_interval_s <= now 인 조건만 평가."""
```

## 14. 알림 정책 (quiet hours 및 critical)

`delivery_policy_store`를 확장하여 다음 정책을 수용한다.

### 14.1 정책 모델

```python
class DeliveryPolicy(BaseModel):
    policy_id: str
    quiet_hours: Optional[QuietHoursSpec]
    change_window: Optional[ChangeWindowSpec]
    critical_bypass: list[str]         # 이벤트 종류 목록 (예: "sla_breach","incident")
    batch_digest_cron: Optional[str]   # quiet 시간대 동안 큐잉된 알림 요약 발송 시각
```

### 14.2 동작 규칙

- quiet hours 중 알림 요청 → `critical_bypass`에 해당하면 즉시 발송, 아니면 **queue** 테이블에 기록.
- quiet hours 종료 직후 batch digest로 일괄 요약 발송(§16 참조).
- change window 외 deploy 시도 → 도구 호출 단계에서 거부되며 "다음 change window까지 대기" Waiting으로 전환.
- 알림 우선순위: critical > P0 SLA 임박 > approval 요청 > 일반.

## 15. Prompt 통합

LLM이 "내가 지금 무엇을 들고 있는지" 항상 인식하도록, 시스템 프롬프트에 **포트폴리오 컨텍스트 블록**이 주입된다.

```
# Portfolio Context (refreshed at each turn)
Active (2/3 slots):
  - TC-042 Churn Analysis  P1  SLA in 52m  (run rn_001, running 23m)
  - TC-043 Revenue Forecast P1  SLA in 3h12m
Waiting (2):
  - TC-044 Pricing AB Test  P0  awaiting data freshness (dataset=fact_pricing)
  - TC-045 Fraud Retrain    P1  awaiting approval (apr_abc, 8m since request)
Monitoring (2):
  - TC-038 Churn v2  day 7/14  last check OK at 09:00
  - TC-039 Pricing v1.3 day 14/14  closing window tomorrow
Playbook Candidates (1):
  - weekly-kpi-triage draft (based on TC-042 pattern, 3 repeats)
Now: 2026-04-15 14:32 KST   Quiet: 22:00~08:00   Change window: CLOSED (Mon)
```

### 15.1 주입 규칙

- 매 turn 시작 시 `list_my_portfolio(compact=True)` 결과를 `<portfolio_snapshot>` 블록으로 시스템 프롬프트에 삽입.
- 스냅샷은 <= 1500 토큰으로 truncate. Entry 수가 많으면 분면별 top-K만, 나머지는 카운트로 요약.
- 전이가 발생한 turn에는 `<portfolio_delta>` 블록도 추가(새 Active, 새 Waiting 등).
- LLM은 포트폴리오를 직접 수정할 수 없고, 반드시 도구(pause/resume/set_sla/reorder)를 통해 의사를 표명.

## 16. UX

### 16.1 Electron — ProjectControlTower 대시보드

- 메인 뷰: 4분면 그리드. 각 타일에는 Entry 카드(제목, priority 배지, 남은 SLA, 소요시간, mini 차트).
- 상단 바: 활성 슬롯 사용량(2/3), quiet/change window 상태, 현재 우선순위 상위 3.
- Entry 카드 클릭 → 우측 drawer에 TaskContract 상세, 최근 도구 호출 로그, transition history.
- 드래그&드롭은 **의도 표명만**: 사용자가 Active로 끌면 `resume_task`/`reorder_portfolio` 도구 호출이 발행되고, 최종 결정은 스케줄러 규칙이 수행.
- Playbook Candidates 분면에서 "승격" 버튼 → §10 거버넌스 플로우 진입.

### 16.2 Telegram — 일일 요약

- 매일 09:00 로컬 시간에 digest 발송:
  - 전일 완료 Entry 수 / SLA 준수율
  - 오늘 SLA 임박 Entry
  - Waiting 중 데드라인 임박 조건
  - Monitoring 중 이슈 감지 여부
  - 신규 Playbook Candidate
- quiet hours 동안 큐잉된 비critical 알림은 morning digest 앞부분에 통합.

### 16.3 CLI — portfolio subcommand

```
ds-agent portfolio list [--quadrant active|waiting|monitoring|candidates]
ds-agent portfolio show <task_contract_id>
ds-agent portfolio pause <tcid> --kind data_freshness --spec '{"dataset":"..."}'
ds-agent portfolio resume <tcid>
ds-agent portfolio sla <tcid> --priority P0
ds-agent portfolio ticks --watch          # 스케줄러 tick 로그 실시간 조회
```

## 17. 기존 모듈과의 관계 (확장 포인트)

### 17.1 `runtime/task_ledger.py`

- 현재: TaskContract 단일 lifecycle 기록.
- 확장: `quadrant`, `portfolio_entry_id` 필드 연결. `record_transition()` API 추가. PortfolioEntry와 1:1 매핑.

### 17.2 `runtime/run_registry.py`

- 현재: run_id 생성 및 상태 기록.
- 확장: 슬롯 개념 도입. `acquire_slot(entry_id) -> slot_token`, `release_slot(slot_token)`. 동시 실행 상한 enforce는 여기서.
- 이벤트 발행: `slot_acquired`, `slot_released` → 스케줄러가 구독.

### 17.3 `runtime/standing_order_tools.py`

- 현재: 사용자 정의 정기 작업.
- 확장: `origin_portfolio_entry_id` 선택 필드. `portfolio_monitoring` 어댑터가 생성·관리하는 standing order는 이 필드로 구분되며, 사용자가 임의로 수정하지 못하도록 보호.

### 17.4 `runtime/delivery_policy_store.py`

- 현재: 알림 정책.
- 확장: `QuietHoursSpec`, `ChangeWindowSpec`, `critical_bypass` 필드 및 마이그레이션. 정책 변경 이벤트 발행.

### 17.5 `runtime/background_task_manager.py`

- 현재: 백그라운드 작업 러너.
- 확장: 스케줄러 tick 스레드 호스트. 기본 1초 간격. tick 구현은 application 레이어의 `PortfolioScheduler.tick()` 호출을 wrap.

### 17.6 `runtime/checkpoint_store.py`

- 현재: 체크포인트 저장.
- 확장: `PortfolioCheckpoint` 포맷 추가. `save_for_entry(entry_id, …)` API. GC 정책: Entry가 Completed/Archived면 30일 후 정리.

## 18. 구현 Phases (TDD)

### Phase P3.A — 포트폴리오 기초 (8~12시간)

**Goal**: PortfolioEntry 도메인 + 4분면 + 최소 스케줄러(동시 실행 상한만).

- RED: 도메인 엔티티 불변식 테스트, 규칙 엔진 단위 테스트(동시 실행 상한), scheduler.tick 시뮬레이션 테스트.
- GREEN: `domain/portfolio/*`, `application/portfolio/scheduler.py` 최소 구현, `infrastructure/portfolio/sqlite_repo.py`, migration v12 (entries/transitions만).
- REFACTOR: 포트 분리 정리, 이벤트 스키마 문서화.
- 도구: `list_my_portfolio`, `pause_task`(kind=timer only), `resume_task`.
- Quality gate: 도메인 레이어 외부 import 없음 확인, 단위 테스트 90% 이상.

### Phase P3.B — WaitCondition (6~8시간)

- RED: 각 WaitCondition 유형 평가기 테스트(가짜 어댑터), deadline/escalation 테스트.
- GREEN: `wait_evaluator.py`, WaitCondition repo, approval/data/external/timer 어댑터.
- 도구: `pause_task` 전 유형 지원.

### Phase P3.C — SLA & Priority (6~8시간)

- RED: 우선순위 공식 속성 기반 테스트(priority 단조성, starvation 방지), SLA 계산 영업일 테스트.
- GREEN: `priority.py`, `set_sla` 도구, 재정렬 트리거.

### Phase P3+.D — Quiet Hours & Change Window (4~6시간)

- RED: delivery policy 결정 테이블, change window enforce 테스트.
- GREEN: delivery_policy_store 확장, scheduler rules 추가, deploy 태그 전이 차단.
- 통합 테스트: 알림 큐잉 + morning digest.

### Phase P3+.E — Monitoring (6~8시간)

- RED: monitoring state 전이, standing order 연동 테스트.
- GREEN: `portfolio_monitoring.py`, Verifier 연동, 이상 감지 시 인시던트 TaskContract 스폰 훅.

### Phase P3+.F — Playbook Candidate 감지 & 승격 (8~12시간)

- RED: PatternDetector 단위 테스트(긍/부정 케이스), 승격 파이프라인 e2e.
- GREEN: 감지기, 초안 생성, §10 거버넌스 연계.
- UX: 승격 승인 UI, 거부 시 재제안 차단.

### Phase P3+.G — UX & Prompt 통합 (6~10시간)

- 시스템 프롬프트 스냅샷 주입, Electron 4분면 뷰, Telegram digest, CLI subcommand.

## 19. 테스트 전략

### 19.1 단위 테스트

- 도메인 불변식: 금지 전이, 분면별 필수 필드.
- 우선순위 공식: 가중치 변경 시 단조성/경계.
- 규칙 엔진: 규칙별 allow/deny 테이블 기반.

### 19.2 스케줄러 시뮬레이션

- `FakeClock` + `InMemoryRepo` + `InMemorySlotGateway`.
- 시나리오 예:
  - S1: 3개 Active 상태에서 새 Waiting이 satisfied 됨 → 우선순위 높은 하나를 선택.
  - S2: change window 외에 deploy-tagged Entry → 다음 window까지 blocked.
  - S3: quiet hours 중 critical 이벤트 → 즉시 발송, 나머지는 digest.
  - S4: SLA 임박 Entry의 deadline_urgency 상승 → starvation 방지 가중치 확인.

### 19.3 동시성 테스트

- 스케줄러 tick과 도구 호출(`pause_task`, `resume_task`)이 동시에 발생할 때 레이스 조건.
- SQLite 트랜잭션 테스트: slot 취득은 원자적이어야 한다.
- Stress 테스트: 1000개 Entry + tick 100회.

### 19.4 WaitCondition 폴링

- `poll_interval_s` 준수(초과 호출 금지), `last_checked_at` 업데이트 원자성.
- Adapter 실패 시 지수 backoff.
- Deadline 만료 동작.

### 19.5 크래시 복구 테스트

- Active Entry를 가진 상태에서 프로세스 kill → 재부팅 → startup_recovery가 Waiting(awaiting_recovery)로 전이했는지 확인.
- 체크포인트 없는 Active Entry 탐지 시 경고.

### 19.6 Prompt 스냅샷 테스트

- snapshot 토큰 길이 상한 준수.
- delta 정확성: 직전 turn 대비 변경 Entry만 포함.

## 20. 의존성 및 통합 지점

| 연계 스펙 | 통합 내용 |
|-----------|-----------|
| §01 TaskContract | PortfolioEntry.task_contract_id, 계약 상태 변경 이벤트 구독 |
| §03 Verifier & Orchestrator | Monitoring 지표 계약, 이상 감지 |
| §04 MissionPack / Certification | Playbook 승격 시 MissionPack 생성, certification 경로 |
| §06 Decision OS | SLA·quiet·change window 정책의 출처, 정책 변경 시 스케줄러 재평가 |
| §10 Self-Improvement Governance | Playbook 승격 게이트 |
| §02 Semantic Memory | Prompt 주입용 포트폴리오 스냅샷 저장(옵션) |

외부 라이브러리:

- Pydantic v2(도메인).
- APScheduler 또는 자체 tick 스레드(기존 background_task_manager 활용 권장, 외부 의존 추가는 지양).
- SQLite(기존 스택 재사용).

## 21. 성공 기준 (Definition of Done)

- [ ] 모든 포트폴리오 전이가 `portfolio_transitions`에 기록됨 (감사 100%).
- [ ] SLA 준수율 측정 지표가 대시보드·CLI에 노출됨. 내부 테스트 환경에서 P0 SLA 준수율 >= 95%.
- [ ] 동시 활성 업무 3건을 안정 운영(1시간 스트레스 시나리오에서 규칙 위반 0).
- [ ] WaitCondition 4유형 모두 폴링·이벤트 기반 충족 확인 경로 동작.
- [ ] Quiet hours / change window 규칙이 시나리오 테스트에서 100% enforce.
- [ ] 크래시 복구 시 Active 누락 0건(startup_recovery가 모두 awaiting_recovery로 이전).
- [ ] Playbook Candidate 감지 정확도: 최근 30일 3회 반복 패턴에 대해 precision >= 0.8, recall >= 0.6(내부 라벨링 기준).
- [ ] LLM 프롬프트의 포트폴리오 스냅샷 토큰 <= 1500, delta 정확.
- [ ] Clean Architecture 체크: 도메인의 외부 import 0, application→runtime 직접 import 0.
- [ ] 단위 테스트 커버리지: domain >= 90%, application >= 85%, infrastructure >= 80%.

## 22. 리스크 및 롤백

| 리스크 | 확률 | 영향 | 완화책 | 롤백 |
|--------|------|------|--------|------|
| 동시 실행 경합 (slot 중복 취득) | 중 | 높음 | SQLite 트랜잭션 + 슬롯 테이블의 UNIQUE 제약, 재시도 백오프 | `max_active_slots=1`로 임시 강등 |
| 대기 상태 누락 (WaitCondition 충족했는데 재개 안 됨) | 중 | 중 | 평가 실패 시 경보, 체크 주기 하한, dead-letter 큐 | 해당 Entry 수동 `resume_task` |
| 우선순위 오판 (LLM이 잘못 재정렬) | 중 | 중 | `reorder_portfolio`는 제약 내에서만 반영, 사용자 가시성 | 재정렬 무시 토글 |
| Quiet hours 중 critical 오분류 | 낮 | 높음 | critical_bypass 목록 명시, 불확실 시 전송 우선 | critical_bypass 전체로 잠시 확대 |
| 감지기 오검출(Playbook 스팸) | 중 | 낮 | 유사도 임계 강화, 차단 해시, 사용자 피드백 루프 | 감지기 비활성 플래그 |
| 체크포인트 누락으로 재개 불가 | 낮 | 높음 | Active→Waiting 시 체크포인트 필수 enforce, 실패 시 전이 거부 | 마지막 run 로그 기반 수동 재시작 |
| 시간대/영업일 계산 오류 | 중 | 중 | 테스트용 FakeClock + 공휴일 캘린더 주입, 회귀 테스트 | 주말 SLA 적용을 자연일로 임시 전환 |
| 스케줄러 tick 과부하 | 낮 | 중 | tick 간격 조정, 배치 크기 상한, 관찰 메트릭 | tick 간격 상향 |

### 롤백 전략

- 마이그레이션 v12는 **add-only**. 컬럼/테이블 drop 대신 `enabled=0` 플래그와 schema feature flag로 off.
- 스케줄러 전체 비활성화 플래그(`portfolio.scheduler.enabled=false`) 제공. 비활성 시 기존 단일 세션 흐름으로 회귀.
- 도구 등록은 feature flag 기반. 롤백 시 tool registry에서 제외.

## 23. Open Questions

1. **영업일 캘린더의 출처**: 조직별 공휴일을 어디서 주입할 것인가? 정책 파일 vs Decision OS vs 외부 API. 1안은 `delivery_policy_store`의 `business_calendar` 필드로 시작.
2. **동시 실행 상한의 동적 조정**: 시스템 부하/모델 쿼터에 따라 max_active_slots를 자동 조정할지, 고정할지. 초기에는 고정 권장.
3. **Playbook Candidate 감지기의 위치**: 실시간 경량 감지 vs 일 1회 배치. 양쪽을 병행하되 임계값을 다르게 가져가는 안이 제시됨.
4. **LLM의 `reorder_portfolio` 권한 범위**: 규칙 위반이 아닌 범위에서 얼마나 적극적으로 허용할지. 초기에는 "연속 상위 2건 swap만" 같은 제한이 합리적.
5. **Monitoring 체크의 비용 모델**: standing order 실행 비용이 포트폴리오 비용에 어떻게 집계되어야 하는가(§04 cost envelope 연계).
6. **Waiting 업무의 우선순위 계산**: Waiting 상태에서도 priority_score를 매기는 것이 맞는지(필요), 아니면 Active 전이 직전에만 계산하는지(성능). 기본은 "on-demand + 이벤트 기반 캐싱".
7. **Electron 4분면 뷰의 드래그 의도 처리**: 사용자가 Entry를 Active→Waiting로 드래그하면 기본 WaitCondition 유형을 어떻게 기본값으로 제안할지.
8. **크래시 복구 시 auto-resume vs always-ask**: 정책 설정으로 제공하되 기본은 always-ask(보수적).
9. **테스트에서 FakeClock·FakeSlot·FakeAdapter의 공용 라이브러리화**: 다른 스펙(§01, §06)과 테스트 더블을 공유할지.
10. **Quiet hours의 사용자별 오버라이드**: 조직 정책 vs 개인 선호. 초기에는 조직 정책 우선, 개인은 approval 알림만 오버라이드 허용.

---

(끝)
