# 01. Task Contract 엔진 구현 명세

**문서 버전**: 1.0
**작성일**: 2026-04-15
**상위 문서**: `Docs/ds-agent-enhancement-roadmap.md` §1
**대상 레이어**: domain / application / infrastructure / presentation 전반
**관련 스프린트 범위**: Medium (5 phases, 추정 12–15h)

## 구현 상태 (2026-04-16)

- 완료: Phase 1 Domain 엔티티/상태 기계, Phase 2 Use case/DTO/보조 Port,
  Phase 3 SQLite 저장소/migration v5, Phase 4 `@tool` 레이어 + Prompt 통합
- 완료: Phase 5 핵심 표면 통합
  - CLI: `ds-agent contract active|list|show|export`, interactive `/contract`
  - Telegram: `/contract`, `/contract agree`, `/contract abandon`
  - Electron: backend HTTP route + main IPC bridge + `MissionBriefPanel` / `ContractEditor` / `AssumptionDrawer`
- 검증: task-contract 대상 Python 테스트, 기존 CLI/Telegram/API 회귀 테스트, Electron `npm run typecheck` 통과
- 후속 polish: Electron 실시간 subscribe 스트림, Assumption verify 액션, Electron 컴포넌트/E2E 자동화는 별도 후속 작업으로 남김
- 참고: 이번 반영에는 `record_review_verdict`, `record_delivery_pack` 보조 tool도 포함됨

---

## 1. 배경 및 문제 정의

### 1.1 현재 에이전트의 한계

DS Agent는 LLM-orchestrator 단일 루프 아래 35+ @tool을 동원해 "분석을 끝까지 수행하는 실행 엔진"으로 작동한다. 1,382개 단위·스모크 테스트, 5-layer 메모리, Skill Hub, Self-Improve 파이프라인이 이미 구축돼 있으며, Electron·CLI·Telegram 3 tier 인터페이스가 동일한 코어를 공유한다. 그러나 기업 환경에 투입되는 순간 다음의 공백이 드러난다.

1. **모호한 요청의 번역 부재**: "이탈 분석해줘"를 받으면 즉시 `data_loader`를 호출하는 경향이 있다. 이는 PoC 단계에서는 속도로 작용하지만, 기업에서는 "무엇을 이탈이라 부를지", "어떤 데이터를 봐도 되는지", "의사결정 시점이 언제인지"가 합의되지 않은 채 실행되는 것을 의미한다.
2. **책임의 경계 미정의**: Agent가 무엇을 자동으로 하고, 무엇을 물어보고, 무엇을 escalate해야 하는지에 대한 명시적 계약이 없다. 정책 엔진(`policy_engine`)이 부분적으로 차단하지만 포괄적 "업무 계약"은 존재하지 않는다.
3. **산출물 기대 불일치**: 의뢰자는 exec 브리핑을 기대하고, peer DS는 노트북을 기대하고, PM은 Jira 티켓을 기대한다. 현재는 누가 receiver인지에 따라 포맷이 일관되지 않는다.
4. **감사 추적 공백**: 어떤 가정으로 어떤 데이터를 썼고, 어떤 의사결정자가 언제까지 결과를 써야 하는지가 세션 로그에 흩어져 있고 정형 artifact로 집계되지 않는다.

### 1.2 왜 "계약"인가

이 문서는 위의 공백을 "업무 계약(Task Contract)" 개념으로 메운다. 계약은 단지 체크리스트가 아니라, LLM이 스스로 업데이트하고 참조하며 의사결정의 근거로 삼는 **살아있는 typed artifact**이다. 계약은 의뢰자·리드·플랫폼팀 3 stakeholder의 기대를 동시에 가시화하여, 자율성 확대의 전제 조건인 "책임 구조"를 구축한다.

### 1.3 비목표 (Non-Goals)

- **워크플로 자동화 재도입 금지**: 계약은 상태 필드를 갖지만 이는 persistence를 위한 라벨이지, 하드코딩된 상태 기계의 전이 규칙이 아니다. 상태 전이의 판단은 LLM이 수행한다.
- **계약 강제 차단 로직 금지**: 계약을 위반하는 도구 호출을 정책 엔진이 차단할 수는 있으나, 계약 자체가 도구 실행을 막는 게이트 역할을 하지 않는다. LLM이 계약을 읽고 스스로 준수하는 구조다.
- **GUI 계약 작성 전용 마법사 금지**: MissionBriefPanel은 렌더링·편집 뷰이지, 단계별 입력 폼이 아니다. 초안은 항상 LLM이 생성한다.

---

## 2. 핵심 테제 (한 문장)

**TaskContract는 LLM이 스스로 생성·갱신·참조하는 typed artifact로서, 애매한 요청을 정확한 DS 문제로 번역하고 자율성의 경계와 책임 구조를 명시적으로 고정하는 단일 진실 공급원이다.**

---

## 3. Typed Artifact 체계

### 3.1 전체 구조

TaskContract는 1개의 루트 엔티티와 6개의 하위 artifact로 구성된다. 모든 artifact는 Pydantic v2 모델로 정의되며, 외부 I/O 의존성이 없는 순수 도메인 엔티티다. 루트는 하위 artifact를 id 참조(`goal_brief_id` 등)로 보관하고, 실제 직렬화는 SQLite 별도 테이블에 저장한다.

```
TaskContract (root)
 ├─ GoalBrief        (1:1, required, draft 시점에 생성)
 ├─ MetricSpec[]     (1:N, 데이터 탐색 후 누적)
 ├─ DatasetManifest  (1:1, 데이터 로딩 후 업데이트)
 ├─ AssumptionLog    (1:1 컨테이너, 내부에 entry 배열)
 ├─ ReviewVerdict[]  (1:N, 검증 단계별 1개)
 └─ DeliveryPack     (1:1, 분석 완료 후 생성)
```

### 3.2 TaskContract (루트)

```python
# src/ds_agent/domain/entities/task_contract.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class TaskContractStatus(str, Enum):
    DRAFT = "draft"
    AGREED = "agreed"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    CLOSED = "closed"
    ABANDONED = "abandoned"


class DataSourceGrant(BaseModel):
    model_config = ConfigDict(frozen=True)
    warehouse: str = Field(..., description="snowflake, bigquery, local, ...")
    schema_name: str = Field(..., alias="schema")
    access_level: Literal["read_only", "read_write", "masked"] = "read_only"
    note: str | None = None


class Budget(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_compute_cost_usd: float | None = None
    max_llm_cost_usd: float | None = None
    max_wall_time_seconds: int | None = None


class DeliverableSpec(BaseModel):
    type: Literal["exec_brief", "ds_appendix", "action_proposals",
                  "dashboard", "notebook", "email", "slack_thread"]
    audience: Literal["executive", "ds_peer", "pm", "ops", "customer"]
    format: str  # pptx, ipynb, jira_tickets, html, md, ...
    count: int | None = None  # action_proposals 등 개수 제약
    constraints: dict[str, str] = Field(default_factory=dict)


class AutonomyBoundary(BaseModel):
    agent_will_do: list[str] = Field(default_factory=list)
    agent_will_ask: list[str] = Field(default_factory=list)
    agent_will_escalate: list[str] = Field(default_factory=list)


class DefinitionOfDone(BaseModel):
    criteria: list[str]
    rollback_rule: str | None = None


class TaskContract(BaseModel):
    """업무 위임 계약 루트 엔티티.

    LLM이 생성·갱신하는 단일 진실 공급원. 외부 패키지(SQLAlchemy,
    requests 등)에 의존해서는 안 된다. Pydantic v2만 허용.
    """
    task_id: str = Field(..., pattern=r"^TC-\d{4}-\d{3,}$")
    session_id: str
    type: str  # MissionPack 매핑 키 (e.g., churn_analysis)
    status: TaskContractStatus = TaskContractStatus.DRAFT

    # 업무 정의
    business_goal: str
    primary_kpi_id: str | None = None  # MetricSpec.metric_id 참조
    secondary_kpi_ids: list[str] = Field(default_factory=list)
    decision_owner: str | None = None
    decision_deadline: datetime | None = None

    # 자원 계약
    allowed_data_sources: list[DataSourceGrant] = Field(default_factory=list)
    forbidden_data_patterns: list[str] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)

    # 산출물
    required_deliverables: list[DeliverableSpec] = Field(default_factory=list)

    # 자율성
    autonomy: AutonomyBoundary = Field(default_factory=AutonomyBoundary)

    # DoD
    definition_of_done: DefinitionOfDone | None = None

    # 하위 artifact 참조
    goal_brief_id: str | None = None
    dataset_manifest_id: str | None = None
    assumption_log_id: str | None = None
    delivery_pack_id: str | None = None
    metric_spec_ids: list[str] = Field(default_factory=list)
    review_verdict_ids: list[str] = Field(default_factory=list)

    # 메타
    created_at: datetime
    updated_at: datetime
    created_by: str = "agent"  # agent | user
    version: int = 1  # 낙관적 락
```

### 3.3 GoalBrief

```python
# src/ds_agent/domain/entities/goal_brief.py
class GoalBrief(BaseModel):
    """비즈니스 목표를 DS 문제로 번역한 최초 브리프."""
    brief_id: str = Field(..., pattern=r"^GB-\d+$")
    task_id: str
    business_question: str       # 의뢰자가 실제로 쓴 문장 + 정제
    ds_problem_statement: str    # DS 용어로 재정의 (예: 이진분류 + 인과추정)
    hypothesis: str | None = None
    comparison_baseline: str     # 무엇과 비교할지 (전월, 동기, 전체 평균 ...)
    decision_to_make: str        # 결과로 어떤 액션을 결정하는가
    expected_effort: Literal["S", "M", "L", "XL"]
    created_at: datetime
    updated_at: datetime
```

### 3.4 MetricSpec

```python
# src/ds_agent/domain/entities/metric_spec.py
class MetricSpec(BaseModel):
    """특정 metric의 조직 내 정의. Enterprise Semantic Memory (§2)와 공유."""
    metric_id: str = Field(..., pattern=r"^MS-[a-z0-9_]+$")
    task_id: str
    name: str
    description: str
    formula: str                 # SQL 또는 pseudo-expression
    source_tables: list[str]
    grain: str                   # user-day, order, session 등
    unit: str                    # percent, count, seconds 등
    direction: Literal["higher_is_better", "lower_is_better", "target"]
    baseline_value: float | None = None
    target_value: float | None = None
    measurement_window: str | None = None  # 2026-Q2 등
    owner: str | None = None
    refresh_cadence: str | None = None      # daily, hourly 등
    confidence_grade: Literal["A", "B", "C"] = "B"
    is_primary_kpi: bool = False
    created_at: datetime
```

### 3.5 DatasetManifest

```python
# src/ds_agent/domain/entities/dataset_manifest.py
class DatasetEntry(BaseModel):
    dataset_ref: str             # schema.table 또는 파일 경로
    row_count: int | None = None
    schema_fingerprint: str | None = None
    freshness_seconds: int | None = None
    trust_grade: Literal["gold", "silver", "bronze", "unknown"] = "unknown"
    access_level: Literal["read_only", "read_write", "masked"] = "read_only"
    notes: str | None = None


class DatasetManifest(BaseModel):
    manifest_id: str = Field(..., pattern=r"^DM-\d+$")
    task_id: str
    entries: list[DatasetEntry] = Field(default_factory=list)
    total_rows: int | None = None
    generated_at: datetime
```

### 3.6 AssumptionLog

```python
# src/ds_agent/domain/entities/assumption_log.py
class AssumptionEntry(BaseModel):
    entry_id: str = Field(..., pattern=r"^AS-\d+$")
    statement: str               # 예: "이탈 = 30일 무활동"
    rationale: str               # 왜 이렇게 가정했는가
    risk_level: Literal["low", "medium", "high"]
    verified: bool = False
    verification_note: str | None = None
    asked_user: bool = False
    created_at: datetime


class AssumptionLog(BaseModel):
    log_id: str = Field(..., pattern=r"^AL-\d+$")
    task_id: str
    entries: list[AssumptionEntry] = Field(default_factory=list)
```

### 3.7 ReviewVerdict

```python
# src/ds_agent/domain/entities/review_verdict.py
class ReviewVerdict(BaseModel):
    verdict_id: str = Field(..., pattern=r"^RV-\d+$")
    task_id: str
    category: Literal["statistical", "data_quality", "policy", "narrative"]
    result: Literal["pass", "warn", "fail"]
    reviewer: str                # "agent" | "user:email" | "peer_llm"
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime
```

### 3.8 DeliveryPack

```python
# src/ds_agent/domain/entities/delivery_pack.py
class DeliveryItem(BaseModel):
    deliverable_type: str        # exec_brief, ds_appendix 등
    audience: str
    format: str
    artifact_path: str           # 파일 경로 또는 메시지 URI
    checksum: str | None = None
    delivered: bool = False
    delivery_channel: str | None = None  # telegram, slack, email, ...


class DeliveryPack(BaseModel):
    pack_id: str = Field(..., pattern=r"^DP-\d+$")
    task_id: str
    items: list[DeliveryItem] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    generated_at: datetime
```

### 3.9 상태 전이 규칙

LLM은 다음 전이만을 선택할 수 있도록 tool의 `update_task_contract` 입력이 `Literal`로 제약된다. 전이 적법성은 도메인 서비스에서 검증한다.

```
draft       → agreed | abandoned
agreed      → in_progress | abandoned
in_progress → review | in_progress   # 반복 허용
review      → in_progress | closed | abandoned
closed      → (terminal)
abandoned   → (terminal)
```

도메인 규칙:

- `draft → agreed`: `GoalBrief`가 존재하고 `required_deliverables`가 1개 이상이어야 한다.
- `in_progress → review`: 최소 1개의 `ReviewVerdict`가 존재해야 한다.
- `review → closed`: 모든 `ReviewVerdict.result`가 `fail`이 아니고 `DeliveryPack`이 존재하며 모든 `DeliveryItem.delivered == True`여야 한다.
- 모든 전이는 `updated_at` 갱신과 `version += 1`을 유발하며, `TaskContractStateTransition` 도메인 이벤트를 발행한다.

규칙 위반 시 도메인 서비스는 `TaskContractStateError`를 발생시키고, 호출한 use case는 이를 tool 응답의 `error` 필드로 변환한다.

---

## 4. Clean Architecture 매핑

### 4.1 레이어별 컴포넌트

| 레이어 | 컴포넌트 | 책임 |
|--------|---------|------|
| Domain (entities) | `TaskContract`, `GoalBrief`, `MetricSpec`, `DatasetManifest`, `AssumptionLog`, `AssumptionEntry`, `ReviewVerdict`, `DeliveryPack`, `DeliveryItem` | 불변 값 객체 + 엔티티. 외부 I/O 의존 금지 |
| Domain (services) | `TaskContractStateMachine` (순수 전이 검증), `TaskContractValidator` (DoD 체크) | 순수 함수 기반 비즈니스 규칙 |
| Domain (events) | `TaskContractCreated`, `TaskContractAgreed`, `TaskContractClosed`, `AssumptionAdded`, `ReviewVerdictRecorded` | 도메인 이벤트 |
| Domain (errors) | `TaskContractStateError`, `TaskContractNotFoundError`, `DoDUnmetError` | 도메인 고유 에러 |
| Domain (ports) | `TaskContractRepository`, `GoalBriefRepository`, `MetricSpecRepository`, `DatasetManifestRepository`, `AssumptionLogRepository`, `ReviewVerdictRepository`, `DeliveryPackRepository` | 저장소 추상화 |
| Application (use cases) | `CreateTaskContractUseCase`, `NegotiateTaskContractUseCase`, `AgreeTaskContractUseCase`, `UpdateTaskContractUseCase`, `AddAssumptionUseCase`, `RecordReviewVerdictUseCase`, `ClosetaskContractUseCase`, `ListTaskContractsUseCase`, `GetTaskContractUseCase` | 오케스트레이션. 도메인만 의존 |
| Application (DTOs) | `TaskContractDraftDTO`, `TaskContractUpdateDTO`, `AssumptionInputDTO`, `TaskContractViewDTO` | 경계 통과용 |
| Application (ports) | `IdGenerator`, `Clock`, `EventPublisher` | 보조 서비스 추상화 |
| Infrastructure (persistence) | `SqliteTaskContractRepository` 외 6개, `migration_v5.py` | Port 구현. SQLite 직접 쿼리 |
| Infrastructure (tools) | `tools/task_contract_tools.py` — @tool 6개 | Use case 호출 → LLM 친화 JSON 반환 |
| Infrastructure (prompt) | `agent/prompt_sections.py`의 `task_contract_section()` | 현재 contract 요약을 system prompt에 주입 |
| Presentation (CLI) | `presentation/cli/commands/contract.py` | `ds contract show/list/export` |
| Presentation (Electron) | `electron/src/renderer/components/mission/MissionBriefPanel.tsx`, `ContractEditor.tsx` | 렌더링·편집 UI |
| Presentation (Telegram) | `presentation/telegram/handlers/contract.py` | `/contract` 명령 |

### 4.2 Dependency Rule 준수 체크

- Domain → (no imports) ✓ Pydantic v2만 허용
- Application → Domain ✓
- Infrastructure → Application, Domain ✓
- Presentation → Application, Domain (Infrastructure는 composition root에서만) ✓
- Tools는 "interface adapter" 역할: LLM 호출을 Application use case 호출로 번역

### 4.3 Composition Root

`src/ds_agent/infrastructure/config/container.py`에서 DI 설정:

```python
def build_task_contract_container(sqlite_path: Path) -> TaskContractContainer:
    db = SqliteConnectionPool(sqlite_path)
    contract_repo = SqliteTaskContractRepository(db)
    goal_repo = SqliteGoalBriefRepository(db)
    # ... 나머지 5개 repo
    clock = SystemClock()
    id_gen = UlidBasedIdGenerator()
    publisher = InMemoryEventPublisher()
    return TaskContractContainer(
        create=CreateTaskContractUseCase(contract_repo, goal_repo, clock, id_gen, publisher),
        update=UpdateTaskContractUseCase(contract_repo, clock, publisher),
        # ...
    )
```

---

## 5. SQLite 스키마 (migration v5)

현재 마이그레이션은 v4. 본 변경은 v5로 번호를 올린다. 모든 JSON 필드는 `TEXT` 컬럼에 Pydantic `model_dump_json()` 결과를 저장한다.

```sql
-- src/ds_agent/infrastructure/persistence/migrations/v5__task_contract.sql

CREATE TABLE IF NOT EXISTS task_contracts (
    task_id         TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    type            TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN
                        ('draft','agreed','in_progress','review','closed','abandoned')),
    business_goal   TEXT NOT NULL,
    primary_kpi_id  TEXT,
    decision_owner  TEXT,
    decision_deadline TEXT,
    budget_json     TEXT NOT NULL,              -- Budget pydantic dump
    autonomy_json   TEXT NOT NULL,              -- AutonomyBoundary
    allowed_sources_json TEXT NOT NULL,         -- list[DataSourceGrant]
    forbidden_patterns_json TEXT NOT NULL,
    required_deliverables_json TEXT NOT NULL,
    definition_of_done_json TEXT,
    goal_brief_id   TEXT,
    dataset_manifest_id TEXT,
    assumption_log_id   TEXT,
    delivery_pack_id    TEXT,
    metric_spec_ids_json TEXT NOT NULL DEFAULT '[]',
    review_verdict_ids_json TEXT NOT NULL DEFAULT '[]',
    secondary_kpi_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    created_by      TEXT NOT NULL DEFAULT 'agent',
    version         INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_task_contracts_session
    ON task_contracts(session_id);
CREATE INDEX IF NOT EXISTS idx_task_contracts_status
    ON task_contracts(status);

CREATE TABLE IF NOT EXISTS goal_briefs (
    brief_id        TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    payload_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_specs (
    metric_id       TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    is_primary_kpi  INTEGER NOT NULL DEFAULT 0,
    payload_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metric_specs_task ON metric_specs(task_id);

CREATE TABLE IF NOT EXISTS dataset_manifests (
    manifest_id     TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    payload_json    TEXT NOT NULL,
    generated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assumption_logs (
    log_id          TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    payload_json    TEXT NOT NULL  -- entries를 포함한 전체 AssumptionLog
);

CREATE TABLE IF NOT EXISTS review_verdicts (
    verdict_id      TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    category        TEXT NOT NULL,
    result          TEXT NOT NULL CHECK (result IN ('pass','warn','fail')),
    reviewer        TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_verdicts_task ON review_verdicts(task_id);

CREATE TABLE IF NOT EXISTS delivery_packs (
    pack_id         TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES task_contracts(task_id) ON DELETE CASCADE,
    payload_json    TEXT NOT NULL,
    generated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_contract_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_task ON task_contract_events(task_id);

-- migration 메타 업데이트
INSERT OR REPLACE INTO schema_migrations(version, applied_at)
VALUES (5, datetime('now'));
```

마이그레이션 실행은 기존 `MigrationRunner`를 재사용하며 v4 → v5 forward-only. 다운그레이드는 `v5__task_contract_rollback.sql`에 `DROP TABLE` 집합을 배치하되, 기본 CLI는 down을 노출하지 않는다 (운영자 전용).

---

## 6. LLM 도구 API

모든 도구는 `@tool` 데코레이터로 registry에 등록되며, 반환 JSON은 가급적 얕고 LLM이 재사용 가능한 형태(`task_id`, `status`, `next_suggested_action`)를 포함한다. 실패는 `{"ok": false, "error_code": "...", "message": "..."}` 구조로 통일.

### 6.1 `create_task_contract`

```python
@tool(
    name="create_task_contract",
    description="사용자 요청을 받아 TaskContract 초안(draft)을 생성한다. "
                "GoalBrief도 함께 생성되어야 하며, 이 도구는 반드시 분석 실행 "
                "이전에 호출되어야 한다.",
    category="mission",
)
def create_task_contract(
    session_id: str,
    contract_type: str,              # churn_analysis, ab_test, ...
    business_goal: str,
    goal_brief: dict,                # GoalBrief 필드 dict
    required_deliverables: list[dict],
    allowed_data_sources: list[dict] = None,
    forbidden_data_patterns: list[str] = None,
    budget: dict = None,
    autonomy: dict = None,
    decision_owner: str = None,
    decision_deadline: str = None,   # ISO8601
) -> dict:
    """Returns: {
        "ok": True,
        "task_id": "TC-2026-042",
        "status": "draft",
        "goal_brief_id": "GB-17",
        "next_suggested_action": "사용자에게 초안 확인 요청"
    }"""
```

### 6.2 `update_task_contract`

```python
@tool(name="update_task_contract",
      description="기존 TaskContract의 필드 또는 status를 갱신한다. "
                  "status 전이는 도메인 규칙이 검증한다.")
def update_task_contract(
    task_id: str,
    expected_version: int,            # 낙관적 락
    patch: dict,                      # 변경할 필드만
    transition_to: Literal["agreed","in_progress","review","closed","abandoned"] | None = None,
    reason: str | None = None,
) -> dict:
    """Returns: {
        "ok": True,
        "task_id": "TC-2026-042",
        "status": "agreed",
        "new_version": 2
    } | 실패 시 {"ok": False, "error_code": "VERSION_CONFLICT"|"INVALID_TRANSITION"|..., ...}"""
```

### 6.3 `get_task_contract`

```python
@tool(name="get_task_contract",
      description="단일 TaskContract를 하위 artifact 요약과 함께 조회한다.")
def get_task_contract(
    task_id: str,
    include: list[Literal["goal_brief","metric_specs","dataset_manifest",
                          "assumption_log","review_verdicts","delivery_pack"]] = None,
) -> dict:
    """Returns: TaskContractViewDTO.model_dump()"""
```

### 6.4 `add_assumption`

```python
@tool(name="add_assumption",
      description="LLM이 명시하지 않고 진행한 가정을 AssumptionLog에 기록한다. "
                  "risk_level이 high이면 사용자에게 확인을 권장한다.")
def add_assumption(
    task_id: str,
    statement: str,
    rationale: str,
    risk_level: Literal["low","medium","high"],
    asked_user: bool = False,
) -> dict:
    """Returns: {"ok": True, "entry_id": "AS-7",
                 "requires_user_confirmation": bool}"""
```

### 6.5 `list_my_contracts`

```python
@tool(name="list_my_contracts",
      description="현재 세션의 TaskContract 목록을 상태 필터와 함께 조회한다.")
def list_my_contracts(
    session_id: str,
    status_filter: list[TaskContractStatus] | None = None,
    limit: int = 20,
) -> dict:
    """Returns: {"ok": True, "contracts": [{"task_id","status","type",
                 "business_goal","updated_at"}...]}"""
```

### 6.6 `close_task_contract`

```python
@tool(name="close_task_contract",
      description="모든 DoD 기준이 충족되었을 때 TaskContract를 closed로 전환한다. "
                  "DeliveryPack이 없거나 ReviewVerdict가 실패이면 에러.")
def close_task_contract(
    task_id: str,
    expected_version: int,
    closing_note: str,
) -> dict:
    """Returns: {"ok": True, "task_id": "...", "status": "closed",
                 "dod_summary": [...]}"""
```

### 6.7 보조 도구 (선택)

- `record_metric_spec`, `record_dataset_manifest`, `record_review_verdict`, `record_delivery_pack` — 각 하위 artifact의 upsert. 도메인 규칙상 TaskContract가 `draft` 이외 상태일 때만 허용.

### 6.8 도구 계층 정책

- 모든 도구는 `TaskContractContainer`를 composition root에서 주입받아 클로저로 캡처한다.
- 도구 반환의 `next_suggested_action`은 **권고 문자열**이지 LLM의 다음 수를 강제하지 않는다. No state machine 원칙 준수.
- 도구 실패 시 LLM이 복구할 수 있도록 `error_code`는 안정적인 enum 문자열이어야 한다.

---

## 7. Prompt 통합

### 7.1 주입 전략

`prompt_sections.py`에 `task_contract_section(session_id)` 함수를 추가하고, `prompt_builder.py`의 `build_system_prompt()` 내 기존 섹션(Skill Hub, Memory Digest 등) 다음 순서에 배치한다. 현재 세션에 활성 `in_progress` 또는 `agreed` contract가 있으면 요약을 주입하고, 없으면 "계약 미체결" 안내를 주입한다.

### 7.2 템플릿

```python
# src/ds_agent/agent/prompt_sections.py
TASK_CONTRACT_SECTION_TEMPLATE = """\
## Task Contract (현재 업무 계약)

{block}

[계약 준수 규칙]
- 이 계약의 `agent_will_escalate`에 해당하는 상황이 발생하면 반드시
  사용자에게 확인을 요청한 후에만 진행한다.
- `forbidden_data_patterns`에 해당하는 데이터는 읽지 않는다.
- `budget`을 초과할 위험이 있으면 즉시 escalate.
- 계약에 없는 deliverable을 자의로 추가하지 않는다.
- 가정이 필요하면 `add_assumption` 도구로 반드시 기록한다.
- 계약 상태 전이는 `update_task_contract(transition_to=...)`로만 수행한다.
"""

ACTIVE_CONTRACT_BLOCK_TEMPLATE = """\
- task_id: {task_id} (status={status}, version={version})
- goal: {business_goal}
- primary KPI: {primary_kpi_name} (baseline={baseline}, target={target})
- deliverables: {deliverables_summary}
- autonomy:
    will_do: {will_do}
    will_ask: {will_ask}
    will_escalate: {will_escalate}
- open assumptions (risk>=medium): {risky_assumptions}
- DoD: {dod_summary}
"""

NO_CONTRACT_BLOCK = """\
활성 TaskContract가 없다. 사용자 요청이 분석 실행을 요구한다면,
먼저 `create_task_contract`를 호출하여 업무 계약 초안을 생성하고
사용자 확인을 받은 뒤 실행하라. 단순 질의/탐색 요청은 예외.
"""
```

### 7.3 예시 출력

```
## Task Contract (현재 업무 계약)

- task_id: TC-2026-042 (status=in_progress, version=3)
- goal: Q2 이탈률 1pp 감소를 위한 핵심 이탈 드라이버 식별
- primary KPI: monthly_churn_rate (baseline=4.2%, target=3.2%)
- deliverables: exec_brief(pptx) | ds_appendix(ipynb) | action_proposals(jira x3)
- autonomy:
    will_do: 데이터 로딩, EDA, 모델 학습, 리포트 초안
    will_ask: 피처 정의 모호성, 비즈니스 컨텍스트
    will_escalate: 민감 데이터 접근, 배포, baseline 미개선
- open assumptions (risk>=medium):
    [AS-3] 이탈 = 30일 무활동 (medium, unverified)
- DoD: 이탈 드라이버 3개+, p<0.05, 액션 3건, 리뷰어 승인

[계약 준수 규칙]
...
```

### 7.4 토큰 예산

- 활성 contract 요약 블록은 하드 300 토큰 상한. 초과 시 `secondary_kpi`, 드문 `allowed_data_sources`는 "…외 N건"으로 축약.
- `assumption_log`는 `risk_level >= medium AND verified == false`만 노출.

---

## 8. UX 흐름

### 8.1 CLI

```
$ ds chat
user> 이번 분기 churn 분석해줘

[agent] 초안 계약을 생성했습니다: TC-2026-042
        business_goal: Q2 이탈률 1pp 감소 위한 이탈 드라이버 식별
        deliverables: exec_brief, ds_appendix, action_proposals x3
        확인하시겠습니까? (a=agree, e=edit, r=reject)

user> e allowed_data에 growth.marketing_campaign 추가

[agent] 계약 v2로 갱신했습니다. 다시 확인하시겠습니까?

user> a

[agent] 계약 agreed. 분석 시작합니다.
        ... (분석 로그) ...

$ ds contract show TC-2026-042
$ ds contract list --status in_progress
$ ds contract export TC-2026-042 --format json > contract.json
```

### 8.2 Electron

**MissionBriefPanel** (`electron/src/renderer/components/mission/MissionBriefPanel.tsx`):

- 좌측 사이드바에 현재 활성 contract 카드. `business_goal`, 상태 배지, KPI, deliverable 칩 목록.
- 상단 우측에 상태 전이 버튼 (Agree / Request Changes / Abandon).
- 하단에 "Open Assumptions" 배너. risk=high 항목은 빨간 테두리 (이모지 없이 border-color 사용).

**ContractEditor** (`ContractEditor.tsx`):

- 모달 다이얼로그로 열리며, JSON Schema 기반 폼 렌더러(`@rjsf/core` 대체 커스텀)로 Pydantic 스키마 반영.
- 편집 후 저장 시 `update_task_contract`를 호출하는 IPC 이벤트 발행. 서버 응답의 `new_version`을 panel에 반영.
- `forbidden_data_patterns` 등 배열 필드는 chip input. 자유 텍스트 + Enter로 추가.
- `autonomy.agent_will_escalate` 편집 시 경고 표시: "여기서 항목을 제거하면 자동 실행 범위가 넓어집니다".

**AssumptionDrawer**: MissionBriefPanel의 "N open assumptions" 링크 클릭 시 열리는 사이드 드로어. 각 entry에 "Verify" 버튼 → `update_task_contract` 또는 직접 `AssumptionEntry.verified = true` patch.

**IPC 계약**: 메인 프로세스는 `task_contract.get`, `task_contract.update`, `task_contract.subscribe` 세 IPC 채널을 노출. subscribe는 SSE-유사 이벤트 스트림으로 version change를 푸시하여 panel 자동 리프레시.

### 8.3 Telegram

```
/contract                  → 활성 contract 1줄 요약 + 상세 링크 버튼
/contract show TC-...      → 요약 카드 메시지
/contract agree TC-...     → 상태 전이
/contract edit TC-... <json patch>   → patch 적용
```

agent 응답에 inline button `[Agree] [Edit in Web] [Reject]` 첨부. 누르면 webhook → `update_task_contract`.

---

## 9. 구현 Phases (TDD)

총 5개 phase. 각 phase는 RED → GREEN → REFACTOR 사이클을 엄수하며, Quality Gate 모두 통과해야 다음 phase로 진행한다.

### Phase 1: Domain 엔티티 및 상태 기계 (2–3h)

**RED (Failing tests)**
- `test/unit/domain/test_task_contract_entity.py`: Pydantic validation (잘못된 `task_id` 패턴, 빈 deliverables → 실패 예상)
- `test/unit/domain/test_task_contract_state_machine.py`: 적법/불법 전이 매트릭스, DoD 체크
- `test/unit/domain/test_assumption_log.py`: risk_level enum, verified flag 로직
- 모든 엔티티 파일에 대한 import-only smoke (yet not implemented → ImportError)

**GREEN**
- `domain/entities/*.py`에 7개 엔티티 최소 구현
- `domain/services/task_contract_state_machine.py` 전이 테이블
- `domain/errors/task_contract_errors.py`
- `domain/ports/task_contract_ports.py` (Protocol 기반)

**REFACTOR**
- Pydantic `ConfigDict(frozen=True)` 적용 가능한 값 객체 식별
- 중복되는 id pattern regex를 `_id_patterns.py`로 추출
- 도메인 이벤트 베이스 클래스 공용화

**Quality Gate**
- [ ] `pytest test/unit/domain -x` 전부 통과
- [ ] `mypy src/ds_agent/domain --strict` 에러 0
- [ ] `ruff check src/ds_agent/domain` 통과
- [ ] Dependency 검사: domain 내 파일에 외부 패키지 import 없는지 (Pydantic 외) AST 스캔 스크립트
- [ ] 상태 전이 테스트 커버리지 >= 95%

### Phase 2: Application Use Case + Port (2–3h)

**RED**
- `test/unit/application/test_create_task_contract_usecase.py`: in-memory fake repo 사용, GoalBrief 동시 생성 검증
- `test_update_task_contract_usecase.py`: version conflict 케이스, 잘못된 전이 케이스
- `test_add_assumption_usecase.py`: risk=high 시 `requires_user_confirmation=True`
- `test_close_task_contract_usecase.py`: DoD 미충족 시 `DoDUnmetError`

**GREEN**
- `application/usecases/task_contract/*.py` 9개 use case
- `application/dtos/task_contract_dtos.py`
- `application/ports/{clock,id_generator,event_publisher}.py`
- 각 use case는 repository를 Protocol로만 의존

**REFACTOR**
- 공통 검증 로직(`_ensure_contract_exists`, `_check_version`)을 `_base.py`로 추출
- DTO ↔ Entity 매퍼 분리

**Quality Gate**
- [ ] Application layer 커버리지 >= 85%
- [ ] `application/`에서 `infrastructure` import 0건 (grep 테스트)
- [ ] mypy, ruff 통과
- [ ] In-memory fake로만 모든 use case 테스트 가능 확인

### Phase 3: SQLite 저장소 + Migration v5 (2–3h)

**RED**
- `test/integration/infrastructure/test_sqlite_task_contract_repo.py`: tmp DB 상대로 CRUD round-trip
- `test_migration_v5.py`: v4 DB 위에 v5 적용 후 테이블 존재, 롤백 idempotency
- `test_optimistic_locking.py`: 동시 update 시 version 충돌

**GREEN**
- `infrastructure/persistence/migrations/v5__task_contract.sql` + 러너 등록
- `infrastructure/persistence/sqlite_task_contract_repository.py` 외 6개
- Pydantic `model_dump_json()` / `model_validate_json()` 왕복
- 트랜잭션 경계: TaskContract 상태 전이 + 관련 artifact upsert를 동일 트랜잭션에서

**REFACTOR**
- 공통 `_serialize/_deserialize` 헬퍼 추출
- `SqliteConnectionPool` 재사용

**Quality Gate**
- [ ] Integration test 커버리지 >= 80%
- [ ] Migration은 v4 DB에서 실행 성공, v5에서 실행 시 no-op
- [ ] 낙관적 락 동작 검증 (version mismatch → `VersionConflictError`)
- [ ] 외래키 cascade delete 검증

### Phase 4: @tool 레이어 + Prompt 섹션 (2–3h)

**RED**
- `test/unit/tools/test_task_contract_tools.py`: 6개 도구의 happy path + 주요 error path
- `test/unit/agent/test_task_contract_prompt_section.py`: 활성 contract가 있을 때/없을 때 블록 문자열 스냅샷
- `test_prompt_builder_integration.py`: `build_system_prompt()` 결과에 섹션 포함 순서 검증

**GREEN**
- `tools/task_contract_tools.py` — 6개 @tool
- 도구는 use case 실행 결과를 dict로 직렬화하는 얇은 어댑터
- `agent/prompt_sections.py`에 `task_contract_section()` 추가
- `agent/prompt_builder.py` 섹션 배치

**REFACTOR**
- 도구 응답 dict 빌더를 `_tool_response.py`로 일원화 (`ok/error_code/message` 규격)
- Prompt 템플릿 상수를 `_templates.py`로 분리

**Quality Gate**
- [ ] 도구 6개 모두 registry에 자동 등록 (smoke test)
- [ ] 프롬프트 토큰 증가량 < 400 tokens (tiktoken 측정)
- [ ] 도구 시그니처가 `typing.get_type_hints()`로 완전히 추론 가능
- [ ] Golden prompt snapshot 테스트 통과

### Phase 5: UI 통합 및 E2E (3–4h)

**RED**
- `test/e2e/test_contract_cli.py`: `ds contract list`, `show`, `export` 종단
- `electron/src/renderer/components/mission/__tests__/MissionBriefPanel.test.tsx` (React Testing Library): 상태 배지 렌더링, Agree 버튼 클릭 IPC 호출
- `test/integration/presentation/test_contract_ipc.py`: IPC 핸들러 round-trip
- `test/e2e/test_telegram_contract_handler.py`: `/contract agree` 명령 시 status 전이

**GREEN**
- `presentation/cli/commands/contract.py`
- `electron/src/renderer/components/mission/MissionBriefPanel.tsx`, `ContractEditor.tsx`, `AssumptionDrawer.tsx`
- `electron/src/main/ipc/task_contract.ts` 채널 + subscribe 이벤트 스트림
- `presentation/telegram/handlers/contract.py`

**REFACTOR**
- Panel의 fetch 로직을 `useTaskContract` hook으로 추출
- CLI·Telegram·IPC가 공유하는 표시 포매터를 `presentation/formatters/task_contract.py`로 통합

**Quality Gate**
- [ ] CLI / Electron / Telegram 3 tier 모두에서 Agree 전이 성공
- [ ] Electron E2E (Playwright) 시나리오 1건: 초안 생성 → 편집 → agree → closed
- [ ] 접근성: MissionBriefPanel 키보드 네비게이션 가능
- [ ] i18n: ko/en 모두 locale 키 등록
- [ ] 번들 크기 증가 < 80 KB gzipped

---

## 10. 테스트 전략

### 10.1 계층별 테스트 매트릭스

| 레이어 | 테스트 유형 | 커버리지 목표 | 도구 |
|--------|------------|--------------|------|
| Domain entities | 단위 (pure) | >= 95% | pytest, hypothesis |
| Domain services | 단위 (pure) | >= 95% | pytest |
| Application use cases | 단위 (fake repo) | >= 85% | pytest, unittest.mock |
| Infrastructure repos | 통합 (tmp SQLite) | >= 80% | pytest |
| Tools | 단위 + smoke | >= 80% | pytest |
| Prompt sections | 스냅샷 | 핵심 분기 | pytest + syrupy |
| CLI | E2E | 주요 명령 | pytest + click.testing |
| Electron UI | 컴포넌트 + E2E | 핵심 플로우 | Jest/RTL + Playwright |
| Telegram | 통합 | 주요 명령 | pytest + telegram mock |

### 10.2 대표 시나리오

**단위 — 상태 기계**
- `draft → review` (불법) → `InvalidTransitionError`
- `agreed → in_progress` (legal, GoalBrief 존재 + deliverable 1개+) → ok
- `review → closed` with fail verdict → `DoDUnmetError`

**단위 — Use case**
- `CreateTaskContractUseCase`: 유효 입력 → contract 생성 + `TaskContractCreated` 이벤트 발행
- `AddAssumptionUseCase`: risk=high → `requires_user_confirmation=True` 반환
- `UpdateTaskContractUseCase`: version mismatch → 실패 + 재조회 제안

**통합 — 저장소**
- Repo round-trip: TaskContract + 하위 6개 artifact 저장 → 전체 재로딩 → 동등성
- Cascade delete: task_contracts 삭제 시 goal_briefs, metric_specs 등도 삭제

**E2E — 위임 시나리오**
1. 사용자 "churn 분석해줘"
2. Agent → `create_task_contract` → MissionBriefPanel 렌더링
3. 사용자 필드 편집 → `update_task_contract` (version 2)
4. 사용자 Agree → `update_task_contract(transition_to=agreed)`
5. Agent 분석 수행, 중간에 `add_assumption` 2건
6. Agent → `record_review_verdict` x3
7. Agent → `record_delivery_pack`
8. Agent → `close_task_contract` → 성공
9. `ds contract show` 출력이 closed + dod_summary 포함

### 10.3 속성 기반 테스트 (hypothesis)

- 상태 전이 그래프에서 임의 경로 샘플링하여 불법 전이 모두 적절한 예외 발생
- 임의의 유효 TaskContract Pydantic 인스턴스 생성 → JSON 직렬화 → 역직렬화 동등성

### 10.4 성능 테스트

- `get_task_contract(include=all)` 응답 p95 < 50ms (1k contract 저장 상태)
- Prompt section 생성 p95 < 10ms

---

## 11. 의존성 및 통합 지점

### 11.1 기존 모듈과의 접점

| 기존 모듈 | 통합 방식 |
|-----------|----------|
| `agent/prompt_builder.py` | `build_system_prompt()` 내 섹션 체인에 `task_contract_section()` 추가. Skill Hub 이후, Memory Digest 이전 위치 |
| `agent/prompt_sections.py` | 신규 함수 추가. 기존 함수는 변경하지 않음 |
| `agent/session_registry.py` | 세션 시작 시 해당 `session_id`의 활성 contract id를 로드하여 컨텍스트에 cache |
| `tools/` registry | `task_contract_tools.py`를 `tools/__init__.py`의 registry 스캔 대상에 포함 |
| `infrastructure/persistence/migration_runner.py` | v5 스크립트를 migrations 목록에 등록. 적용 순서 보장 |
| `infrastructure/policy_engine.py` | (선택) `forbidden_data_patterns`을 정책 규칙으로 프록시하여 도구 호출 차단에 활용. 단, 계약 자체는 강제 게이트가 아님 |
| `application/usecases/memory/*` | MetricSpec을 Enterprise Semantic Memory (§2)와 공유하기 위한 포트 분리 지점 — 본 스펙에서는 별도 테이블 유지, §2에서 통합 |
| `presentation/electron/ipc/` | 신규 IPC 채널 3개 등록. 기존 세션 IPC와 충돌 없음 |
| `i18n/` ko.json, en.json | MissionBriefPanel, ContractEditor 문자열 키 추가 |

### 11.2 Cross-cutting 고려

- **Observability**: 모든 상태 전이 이벤트를 기존 `TelemetryEmitter`로 내보내어 감사 로그 연동 (§9 Observability 스펙과 일관).
- **Crash recovery**: 기존 `SessionCheckpointer`가 세션 종료 시 상태를 저장하는 것처럼, 진행 중인 draft contract도 checkpoint에 포함. 재시작 시 MissionBriefPanel 복구.
- **Concurrency**: 낙관적 락(version)을 기본으로, 동일 세션의 동시 업데이트는 어플리케이션 계층에서 `expected_version` 강제.

### 11.3 향후 스펙과의 연결

- **§2 Enterprise Semantic Memory**: MetricSpec이 조직 공유 metric catalog로 승격. 현재 스펙에서는 task-scoped MetricSpec만 저장하되, id 체계를 전역 호환으로 설계.
- **§3 Verifier Layer**: ReviewVerdict를 소비. 현재 스펙에서는 저장소만 제공, verifier는 §3에서 생산자 역할.
- **§4 Delivery Policy**: DeliveryPack 스키마가 §4 정책 엔진의 입력이 됨.
- **§5 Mission Pack Registry**: `TaskContract.type` 필드가 mission pack 키.

---

## 12. 성공 기준 (DoD)

### 12.1 기능 완결성

- [ ] 6개 @tool 도구가 registry에 등록되고 LLM 시스템 프롬프트의 tool spec에 노출된다.
- [ ] CLI/Electron/Telegram 3 tier에서 Agree/Edit/Close 전이가 동작한다.
- [ ] 모든 상태 전이가 version 충돌을 올바르게 감지한다.
- [ ] Prompt에 활성 contract 블록이 삽입되고 토큰 예산 400 이내를 유지한다.

### 12.2 품질 지표

- [ ] Domain + Application 테스트 커버리지 평균 >= 85%
- [ ] Integration 커버리지 >= 80%
- [ ] E2E 시나리오 위임 1건 + 거부 1건 + 롤백 1건 통과
- [ ] mypy --strict 에러 0 (본 스펙이 추가한 모듈 대상)
- [ ] ruff check 경고 0

### 12.3 운영 지표

- [ ] `get_task_contract(include=all)` p95 < 50ms @ 1k contracts
- [ ] 새 DB에서 v4 → v5 마이그레이션 < 2s
- [ ] Electron bundle 증가 < 80 KB gzipped

### 12.4 사용자 지표 (초기 dogfooding)

- [ ] 내부 파일럿 5 세션에서 평균 contract draft 생성 시간 < 30s (LLM 호출 포함)
- [ ] 의뢰자가 "agree" 전에 평균 수정 횟수 1회 이내 — 그 이상이면 GoalBrief 품질 개선 필요

---

## 13. 리스크 및 롤백

### 13.1 리스크 매트릭스

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|----------|
| LLM이 도구를 호출하지 않고 분석을 시작 | High | High | 시스템 프롬프트에 "분석 실행 전 `create_task_contract` 필수" 규칙 주입. 파일럿에서 도구 호출율 계측 |
| contract 편집 폼의 JSON 스키마 불일치로 UI crash | Med | Med | 서버/클라이언트 모두 Pydantic 스키마를 단일 소스로 export (JSON Schema 생성) |
| v5 마이그레이션 실패 | Low | High | forward-only + pre-migration backup. `--dry-run` 플래그로 SQL 검증 후 적용 |
| 낙관적 락 충돌로 UX 저하 | Med | Low | UI에서 충돌 시 자동 재조회 후 merge diff 제시 |
| Prompt 토큰 예산 초과로 context truncation | Low | Med | 블록 렌더러에 하드 상한 + 압축 우선순위 |
| LLM이 `will_escalate` 규칙을 무시 | Med | High | policy_engine이 forbidden_data_patterns을 차단하는 하드 게이트로 보완. assumption log 필수화 |
| contract 개수 폭증으로 SQLite 성능 저하 | Low | Low | `idx_task_contracts_session/status` 인덱스 + archive 정책 (§9 연계) |

### 13.2 Phase별 롤백 전략

| Phase | 실패 시 롤백 |
|-------|------------|
| 1 | 도메인 파일 삭제, 기존 코드 영향 없음 |
| 2 | Application 파일 삭제. Phase 1은 독립 사용 가능 |
| 3 | `migration_v5` 스크립트 비활성화 + 새 테이블 DROP. 기존 v4 시스템 무영향 |
| 4 | 도구 registry 등록 해제, prompt section 제거 플래그(`TASK_CONTRACT_PROMPT_ENABLED=False`) |
| 5 | Electron panel을 feature flag로 비활성, CLI/Telegram 명령 숨김 |

### 13.3 Feature Flag

`config/feature_flags.yaml`에 다음을 추가:

```yaml
task_contract:
  enabled: true
  prompt_injection: true
  electron_panel: true
  enforce_creation_before_analysis: false   # 점진 도입용. 파일럿 후 true 전환
```

---

## 14. Open Questions

1. **초기 draft 강제 여부**: 현재는 "분석 실행 전 계약 필수"를 프롬프트 규칙으로만 유도한다. `enforce_creation_before_analysis=true`로 정책 엔진에 하드 차단을 두면 No-State-Machine 원칙과 충돌 가능성이 있다. 어느 쪽을 기본값으로 할지 파일럿 데이터 확보 후 결정.
2. **MetricSpec의 전역화 시점**: 본 스펙은 task-scoped 저장으로 시작한다. §2 Enterprise Semantic Memory 착수 시 task-scoped MetricSpec을 전역 Metric Registry로 승격하는 마이그레이션 경로를 어느 스프린트에 배치할지 미정.
3. **contract diff 표현**: version 증가 시 이전 버전과의 diff를 보관할지, 아니면 이벤트 로그만으로 재구성할지. 초기는 이벤트 로그 + DB version 필드로 충분하다고 판단하지만, UI에서 "이 Agree 이후 바뀐 것"을 보여줄 때 성능 요구가 생기면 snapshot 저장을 고려.
4. **의뢰자 외 stakeholder의 서명**: 현재 `decision_owner`는 문자열 필드. 리드/플랫폼팀의 서명/리뷰 기록을 별도 `ContractSignature` artifact로 분리할지 여부 — §3 Verifier Layer와 연동 결정 필요.
5. **Telegram에서 JSON patch 편집 UX**: 모바일에서 JSON을 직접 편집하는 것은 비현실적. Web link → Electron deep link로 유도하는 방식이 현실적이나, Telegram 단독 사용자에게는 UX 저하. 경량 폼 메시지(Reply Keyboard with field-by-field)가 대안이나 구현 비용이 큼. v1에서는 link 우선, v2에서 경량 폼 검토.
6. **비용 측정 기준**: `budget.max_compute_cost_usd`를 측정하려면 infra에 cost meter가 필요. 본 스펙은 필드만 정의, 실측 연동은 §7 Cost Observability 스펙에 위임.
7. **계약 간 의존성**: 한 세션에서 여러 contract를 병행 실행하거나 parent-child로 쪼개는 경우(`parent_task_id`). v1에서는 단일 contract 전제. 필요 시 v2에서 필드 추가.

---

**다음 스펙**: `02-enterprise-semantic-memory.md` (MetricSpec 전역화, 조직 metric catalog, 신뢰도 등급 체계)
