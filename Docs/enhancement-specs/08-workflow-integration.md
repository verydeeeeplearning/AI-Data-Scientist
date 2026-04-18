# 08. Workflow Integration — 조직 프로세스 연결

> Roadmap §8 Workflow Integration의 상세 구현 스펙.
> 관련 스펙: §01 TaskContract, §04 Policy Engine, §07 DeliveryPack, §09 Async Portfolio Manager.

---

## 1. 배경 및 문제 정의

### 1.1 "노트북에서 끝나지 않는다"

현재 DS Agent는 Postgres 연결(`tools/integration_tools.py`)과 파일 기반 산출물(HTML/CSV/notebook) 생성까지를 완결 지점으로 본다. 그러나 실제 기업 환경에서 데이터 사이언티스트의 업무는 다음과 같은 흐름을 따른다.

1. **요청 수집**: 도메인 stakeholder가 Slack DM, 이메일, 회의 중 구두 지시, Jira 티켓으로 분석을 요청한다.
2. **실행**: 노트북/스크립트/대시보드로 분석을 수행한다. ← 현재 에이전트가 커버하는 영역.
3. **공유**: 분석 결과를 Confluence/Notion 문서로 정리, 코드는 Git PR로 제출, 주요 그래프는 Slack 스레드에 포스팅.
4. **후속 액션**: 결론을 토대로 Jira 후속 태스크(실험 설계, 대시보드 갱신, 재가입 캠페인 등)를 발행하고 담당자 배정.
5. **리뷰/동기화**: 리뷰 미팅을 캘린더에 등록, 결과 요약 메일을 송부, BI 대시보드에 주석 추가.

이 중 3~5단계가 누락되면 DS의 결과물은 "노트북 내부의 죽은 코드"로 남고, 조직은 다시 사람의 수작업 전달에 의존한다. 자율 에이전트가 이 전 구간을 커버하지 못하면 "시니어 DS를 대체한다"는 명제가 성립하지 않는다.

### 1.2 현 상태의 한계

| 영역 | 현재 구현 | 공백 |
|------|-----------|------|
| 요청 수집 | CLI/Telegram/Electron 텍스트 프롬프트 | Slack 공식 워크스페이스 연동, 이메일 요청 파싱 부재 |
| 실행 추적 | run_id, session_id (JSON log) | 원 요청 → 실행 → 문서 → 후속 액션을 잇는 단일 추적 객체 부재 |
| 문서화 | DeliveryPack HTML/MD 로컬 저장 | Confluence/Notion 게시, Git PR 자동 생성 부재 |
| 후속 액션 | 결과 텍스트에 "TODO" 문자열로 기술 | 실제 티켓/캘린더 이벤트 발생 없음 |
| 감사 | dev/logs/run_*.log | 외부 시스템으로 나간 메시지/티켓의 idempotency 및 회수 전략 없음 |

### 1.3 이 스펙이 해결하는 것

- 모든 DS 업무를 **Work Object**라는 domain entity로 추적한다.
- Slack/Jira/Confluence/Notion/Git/Email/Calendar/BI 통합을 **Integration Hub** 아래 공통 포트 인터페이스로 흡수한다.
- LLM이 "어떤 채널로 어떤 형식으로 전달할지"를 판단하고, connector는 순수 실행기로만 동작한다(§8.2 핵심 테제).
- 외부로 나가는 write action에는 §04 Policy Engine의 승인 게이트가 걸린다.

---

## 2. 핵심 테제

1. **Work Object는 TaskContract의 실행 추적 뷰다.** TaskContract(§01)가 "계약"이라면 WorkObject는 계약 이행의 라이프사이클(Request → Execution → Documentation → Follow-up) 전체를 물리적으로 이어붙이는 객체다.
2. **LLM이 orchestrator, Connector는 executor다.** "Slack에 올릴지 메일로 보낼지", "Jira 티켓을 몇 개 끊을지"는 LLM이 DeliveryPack 리포트와 stakeholder 요구를 보고 판단한다. Connector는 `post_to_slack(channel, blocks)` 같은 저수준 실행만 제공한다.
3. **TDD와 Clean Architecture 준수.** 모든 connector는 `domain/interfaces`에 선언된 포트에 대한 infrastructure 구현이며, 테스트는 mock 서버/recording 기반으로 먼저 작성한다.
4. **Typed artifact WorkObject.** 모든 외부 참조는 `ExternalReference` value object로 표준화되어 Work Object 내부에 기록된다. 문자열 URL만 남기는 방식은 금지한다.
5. **모든 외부 write는 idempotent.** 동일 WorkObject에 대해 같은 action을 두 번 호출해도 중복 티켓/중복 메시지가 나지 않도록 idempotency key가 강제된다.
6. **Fail-closed.** 외부 시스템 장애 시 실행은 기록으로 남기되, 사용자 요약에는 "dispatch pending"을 명시하고 재시도 큐에 올린다.

---

## 3. Work Object 모델

### 3.1 개념 구조

Work Object는 4 섹션으로 구성된다.

```
WorkObject
├── request        # 누가, 어디서, 무엇을 요청했는가
├── execution      # TaskContract, runs, 현재 phase
├── documentation  # 생산된 산출물 (Confluence, Git PR, DeliveryPack)
└── follow_up      # 발생한 후속 액션 (Jira, Calendar, Slack DM)
```

### 3.2 Pydantic 스키마 (domain layer)

```python
# domain/entities/work_object.py
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal

class RequestSource(str, Enum):
    SLACK = "slack"
    EMAIL = "email"
    JIRA = "jira"
    CLI = "cli"
    TELEGRAM = "telegram"
    ELECTRON = "electron"
    API = "api"

class WorkObjectPhase(str, Enum):
    INTAKE = "intake"
    EXECUTING = "executing"
    REVIEW = "review"
    DOCUMENTING = "documenting"
    FOLLOWUP = "followup"
    CLOSED = "closed"
    FAILED = "failed"

class ExternalReference(BaseModel):
    """어떤 외부 시스템의 어떤 리소스를 가리키는가."""
    system: Literal["slack", "jira", "confluence", "notion",
                    "github", "gitlab", "email", "calendar",
                    "looker", "tableau", "asana", "monday"]
    resource_type: str        # e.g. "issue", "page", "thread", "pr", "event"
    resource_id: str          # system-local id (Jira key, Slack ts, PR number)
    url: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    idempotency_key: str

class RequestSection(BaseModel):
    source: RequestSource
    requestor_id: str         # Slack user id, email address, etc.
    requestor_display: str    # "김상무"
    original_text: str        # 원문 (redaction 전)
    channel: str | None = None
    received_at: datetime
    external_ref: ExternalReference | None = None  # e.g. Slack thread

class ExecutionSection(BaseModel):
    task_contract_id: str
    run_ids: list[str] = Field(default_factory=list)
    current_phase: WorkObjectPhase = WorkObjectPhase.INTAKE
    started_at: datetime | None = None
    completed_at: datetime | None = None

class DocumentationSection(BaseModel):
    delivery_pack_id: str | None = None
    references: list[ExternalReference] = Field(default_factory=list)

class FollowUpAction(BaseModel):
    action_type: Literal["ticket", "calendar", "message", "dashboard_update"]
    description: str
    external_ref: ExternalReference
    policy_decision_id: str | None = None   # §04 승인 id

class FollowUpSection(BaseModel):
    actions: list[FollowUpAction] = Field(default_factory=list)

class WorkObject(BaseModel):
    work_object_id: str           # WO-YYYY-NNNN
    title: str
    request: RequestSection
    execution: ExecutionSection
    documentation: DocumentationSection = Field(
        default_factory=DocumentationSection
    )
    follow_up: FollowUpSection = Field(default_factory=FollowUpSection)
    created_at: datetime
    updated_at: datetime
    owner_agent: str              # "ds-agent-prod"
    tags: list[str] = Field(default_factory=list)
```

### 3.3 라이프사이클과 상태 전이

| From | To | 트리거 | 조건 |
|------|----|--------|------|
| intake | executing | TaskContract ratified | policy check pass |
| executing | review | first run 완료 | artifacts emitted |
| review | documenting | human approve or auto-approve rule | policy §04 |
| documenting | followup | doc connector success | at least 1 external_ref |
| followup | closed | 모든 follow-up action 종료 | no pending action |
| any | failed | connector 반복 실패 또는 policy reject | retry exhausted |

### 3.4 TaskContract와의 관계

- **1:1 기본 매핑.** 한 TaskContract는 한 WorkObject에 귀속된다.
- **다중 run 허용.** 같은 TaskContract의 재실행(run_002, run_003)은 WorkObject.execution.run_ids에 append된다.
- **TaskContract 변경 시.** 범위가 크게 달라지면 새 WorkObject를 분기(`parent_work_object_id` metadata)하는 것이 원칙이다. 이 분기는 LLM이 판단하되 policy_engine이 승인한다.

---

## 4. Integration Hub 아키텍처

### 4.1 포지셔닝

```
application use case (예: DispatchDeliveryPack)
        │
        ▼
 Port interface (domain/interfaces/connector.py)
        │
        ▼
 Integration Hub (infrastructure/external/integration_hub.py)
        │
        ├─ SlackConnector
        ├─ JiraConnector
        ├─ ConfluenceConnector
        ├─ GitConnector
        ├─ EmailConnector
        ├─ CalendarConnector
        └─ BIConnector
```

Hub는 연결 풀/인증/rate limit/재시도/이벤트 로깅 등 공통 관심사를 소화하고, 개별 connector는 시스템별 API 호출에 집중한다.

### 4.2 공통 포트 (Connector ABC)

```python
# domain/interfaces/connector.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from pydantic import BaseModel

TRequest = TypeVar("TRequest", bound=BaseModel)
TResponse = TypeVar("TResponse", bound=BaseModel)

class ConnectorResult(BaseModel):
    success: bool
    external_ref: "ExternalReference | None" = None
    error_code: str | None = None
    error_message: str | None = None
    retriable: bool = False

class Connector(ABC, Generic[TRequest, TResponse]):
    system_name: str

    @abstractmethod
    async def dispatch(
        self,
        request: TRequest,
        idempotency_key: str,
        dry_run: bool = False,
    ) -> ConnectorResult: ...

    @abstractmethod
    async def fetch(self, resource_id: str) -> TResponse | None: ...

    @abstractmethod
    def health_check(self) -> bool: ...
```

### 4.3 인증 및 자격증명

| 시스템 | 인증 방식 | 저장 위치 |
|--------|-----------|-----------|
| Slack | Bot Token + Signing Secret | `integration_credentials` 테이블 (암호화) |
| Jira | OAuth 2.0 (3LO) 또는 API token + email | 동일 |
| Confluence | OAuth 2.0 또는 API token | 동일 |
| Notion | OAuth 2.0 internal integration | 동일 |
| GitHub | GitHub App installation token | 동일 |
| GitLab | OAuth or PAT | 동일 |
| Email | SMTP (STARTTLS) + IMAP idle (수신) | 동일 |
| Calendar | Google OAuth, Microsoft Graph, CalDAV | 동일 |
| Looker/Tableau | API user + embed secret | 동일 |

- credential은 `cryptography.fernet` 로 대칭 암호화, key는 `DS_AGENT_INTEGRATION_KEY` 환경변수.
- 사용자 계정 기반(Impersonation) 이 아닌 **에이전트 서비스 계정** 이 원칙. 사용자 행위로 오인되지 않도록 메시지에 `via ds-agent` 서명을 삽입한다.

### 4.4 Rate Limit & Backoff

- 시스템별 token bucket (in-memory + SQLite 영속) 보유.
- 예: Slack Web API = 1 req/s (tier 2), Jira Cloud = 10 req/s per user.
- 429/503 수신 시 exponential backoff (`min(60s, 2^n)`), jitter 포함.

### 4.5 Idempotency Key

- 형식: `wo_{work_object_id}:{system}:{action}:{discriminator}`
  - 예: `wo_WO-2026-0042:jira:create_issue:growth-1234-seed`
- discriminator는 LLM이 "같은 의도의 action인지"를 판단할 수 있도록 요청 payload의 해시를 사용한다.
- Hub는 dispatch 직전 `integration_event_log`를 조회해 동일 key가 성공한 기록이 있으면 **기존 external_ref를 그대로 반환**(re-emit 금지).

### 4.6 재시도 & 실패 복구

| 실패 유형 | 처리 |
|-----------|------|
| 네트워크 타임아웃 | 3회 재시도, 모두 실패 시 DLQ(dead letter)로 이동 |
| 4xx 인증 | 즉시 실패, 자격증명 갱신 알림 |
| 4xx validation | 재시도 금지, LLM에게 payload 재생성 요청 |
| 5xx 서버 오류 | 지수 백오프 재시도 |
| 429 rate limit | `Retry-After` 준수 |
| idempotent duplicate | 기존 결과 리턴 |

DLQ는 `integration_event_log.status = "dlq"` 로 표식되며, CLI `ds-agent integration replay` 로 수동 재시도 가능.

### 4.7 공통 Event Model

```python
class IntegrationEvent(BaseModel):
    event_id: str
    work_object_id: str
    system: str
    action: str
    request_payload_hash: str   # PII redaction 후
    idempotency_key: str
    status: Literal["pending", "success", "failed", "dlq", "duplicate"]
    external_ref: ExternalReference | None = None
    attempt: int
    latency_ms: int
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None = None
    policy_decision_id: str | None = None
```

---

## 5. Slack Connector (P0)

### 5.1 역할

- **요청 수집**: 슬래시 명령(`/ds-agent <prompt>`), 멘션(`@ds-agent`), 앱 홈의 "새 분석 요청" 모달.
- **결과 전달**: DeliveryPack 요약을 Block Kit으로 렌더링, 스레드 유지.
- **인터랙션**: "이 결과 승인", "후속 티켓 생성", "다시 실행" 버튼.
- **스레드 상태 유지**: 같은 Work Object의 후속 이벤트는 최초 스레드에 append.

### 5.2 이벤트 플로우

```
User → /ds-agent "churn 분석해줘"
          │
          ▼
  Slack → POST /slack/events → SlackEventController
          │
          ▼
  IntakeUseCase.from_slack(payload)
          │  → WorkObject(intake) 생성, TaskContractDraft 작성
          ▼
  Slack 스레드에 "TaskContract draft ready, approve?" Block 게시
```

결과 전달:

```
DispatchDeliveryPackUseCase → SlackConnector.dispatch(
    SlackMessageRequest(
        channel=work_object.request.channel,
        thread_ts=work_object.request.external_ref.resource_id,
        blocks=[...rendered from DeliveryPack summary...],
        attachments=[delivery_pack.html_url],
    )
)
```

### 5.3 필요한 OAuth Scope

| Scope | 이유 |
|-------|------|
| `app_mentions:read` | 멘션 기반 요청 수신 |
| `chat:write` | 결과 포스팅 |
| `chat:write.public` | 봇이 초대되지 않은 채널에도 포스팅(옵션) |
| `commands` | 슬래시 명령 |
| `files:write` | DeliveryPack HTML 업로드 |
| `channels:history`, `groups:history` | 스레드 상태 동기화 |
| `users:read`, `users:read.email` | requestor 매핑 |
| `im:write` | DM 전달 |

### 5.4 인라인 승인 UI

- Block Kit `actions` 블록에 `approve_delivery`, `request_changes`, `create_followups` 버튼.
- 클릭 시 Slack `block_actions` payload → `SlackActionController` → 해당 WorkObject의 policy decision 업데이트.
- 승인 결과는 동일 스레드에 replace (`chat.update`).

### 5.5 구현 타입

```python
# infrastructure/external/slack_connector.py
class SlackMessageRequest(BaseModel):
    channel: str
    thread_ts: str | None
    blocks: list[dict]
    text_fallback: str
    attachments_file_ids: list[str] = []

class SlackConnector(Connector[SlackMessageRequest, dict]):
    system_name = "slack"
    async def dispatch(...): ...
    async def upload_file(self, path: Path, title: str) -> str: ...
    async def update_message(self, channel: str, ts: str, blocks: list[dict]) -> None: ...
```

---

## 6. Jira Connector (P0)

### 6.1 역할

- 후속 액션 티켓 자동 생성.
- 원 요청 티켓 상태 동기화(진행중/완료).
- JQL 검색으로 기존 중복 티켓 탐지 후 link.

### 6.2 TaskContract → Jira Issue 매핑 규칙

| TaskContract 필드 | Jira 필드 | 변환 로직 |
|-------------------|-----------|-----------|
| `title` | `summary` | 최대 255자, 접두 `[DS]` |
| `business_goal` | `description` (상단) | Markdown → ADF 변환 |
| `recommendations[i]` | 별도 child issue | LLM이 issue split 여부 판단 |
| `assignee_hint` | `assignee` | email → accountId 조회 |
| `labels` | `labels` | `ds-agent`, `wo-{id}` 고정 추가 |
| `priority_hint` | `priority` | High/Med/Low ↔ Highest..Lowest |
| `due_date` | `duedate` | ISO 8601 |
| `epic_link` | `customfield_*` | 프로젝트별 custom field resolver |
| WorkObject id | `labels` + description footer | 역추적용 |

### 6.3 상태 동기화

- 에이전트가 만든 티켓 상태는 Jira webhook(`jira:issue_updated`)으로 수신 → WorkObject.follow_up.actions[*].external_ref.metadata.status 갱신.
- "Done" 전이 시 해당 follow-up action을 closed 처리.

### 6.4 중복 방지

- Dispatch 전 JQL 수행:
  `labels = "wo-{work_object_id}" AND summary ~ "{first 40 chars}"`
- 결과가 있으면 idempotency 매칭 여부 검사 후 기존 issue key 재사용.

### 6.5 구현 타입

```python
class JiraIssueRequest(BaseModel):
    project_key: str
    issue_type: str                     # "Task", "Story", ...
    summary: str
    description_adf: dict               # Atlassian Document Format
    assignee_account_id: str | None
    labels: list[str]
    priority: Literal["Highest","High","Medium","Low","Lowest"] | None
    due_date: date | None
    custom_fields: dict = {}
    parent_key: str | None = None       # subtask 연결
```

---

## 7. Confluence / Notion Connector (P1)

### 7.1 역할

- DeliveryPack을 페이지 형태로 자동 게시.
- 분기별/주차별 집계 페이지에 섹션 append.
- 라벨/태그 동기화.

### 7.2 페이지 구조 매핑

DeliveryPack 섹션 → Confluence heading 구조:

```
h1  Work Object Title (WO-2026-0042)
h2  Executive Summary       ← DeliveryPack.summary_ko
h2  Key Findings            ← DeliveryPack.findings
h2  Methodology             ← DeliveryPack.methodology
h2  Results                 ← DeliveryPack.results (Chart macro 삽입)
h2  Recommendations         ← DeliveryPack.recommendations
h2  Appendix: Runs & Code   ← Git PR 링크, notebook attachments
h2  Follow-up Actions       ← Jira issue macro
```

Notion의 경우 database schema를 이용: `Growth DS Reports` DB에 row 추가.

### 7.3 업데이트 전략

| 조건 | 전략 |
|------|------|
| 최초 게시 | 새 페이지 생성, 부모 = 프로젝트 스페이스 홈 |
| 같은 WorkObject 재실행 | 기존 페이지 edit, `history` 섹션에 version note 추가 |
| 주간 집계 페이지 | append-only, `<!-- WO-xxxx -->` 마커로 구간 식별 |
| 큰 구조 변경 | 사용자에게 diff preview → policy 승인 후 적용 |

### 7.4 태그/라벨 동기화

- Confluence labels: `ds-agent`, `wo-{id}`, TaskContract.tags
- Notion properties: Select 필드 `Status`, `Owner`, `Quarter`; Multi-select `Tags`.

### 7.5 구현 타입

```python
class ConfluencePageRequest(BaseModel):
    space_key: str
    title: str
    parent_page_id: str | None
    storage_format_body: str    # XHTML storage format
    labels: list[str]
    version_comment: str | None = None
    overwrite_page_id: str | None = None   # edit 모드
```

---

## 8. Git (GitHub/GitLab) Connector (P1)

### 8.1 역할

- 분석 노트북/스크립트/SQL을 PR로 제출.
- 리뷰어 자동 지정.
- CI 체크 대기 및 결과 수신.

### 8.2 브랜치 & PR 규칙

| 요소 | 규칙 |
|------|------|
| 브랜치명 | `ds-agent/wo-{id}-{slug}` (예: `ds-agent/wo-2026-0042-q2-churn`) |
| 커밋 메시지 | `feat(ds): {TaskContract.title}\n\nWO: {work_object_id}\nRun: {run_id}` |
| PR 제목 | `[DS][WO-{id}] {title}` |
| PR body | DeliveryPack summary + artifact links + "Generated by ds-agent" |
| Base branch | 기본 `main`, 프로젝트별 override |
| Draft | TaskContract가 review phase 미도달 시 draft |

### 8.3 리뷰어 지정

- TaskContract.reviewers + CODEOWNERS 교차.
- stakeholder(Slack requestor)가 GitHub 계정 매핑되면 자동 추가.
- LLM이 변경 범위를 보고 추가 reviewer 추천 가능(optional).

### 8.4 CI 통합

- GitHub Checks / GitLab Pipelines 상태를 폴링 또는 webhook으로 수신.
- 실패 시 WorkObject를 `review` phase에 유지하고 Slack 스레드에 에러 요약 전달.

### 8.5 구현 타입

```python
class GitPRRequest(BaseModel):
    repo: str                  # "org/repo"
    base_branch: str
    head_branch: str
    files: list["GitFileChange"]
    pr_title: str
    pr_body_markdown: str
    reviewers: list[str]
    labels: list[str]
    draft: bool = False

class GitFileChange(BaseModel):
    path: str
    content_base64: str
    mode: Literal["add", "update", "delete"]
```

---

## 9. Email / Calendar Connector (P2)

### 9.1 Email

- SMTP (Google Workspace / Microsoft 365 / 사내 Relay) 지원.
- 수신은 IMAP IDLE 또는 Gmail push notification.
- 템플릿: Jinja2 기반, 카테고리별(`delivery_summary`, `followup_request`, `daily_digest`).
- 첨부: DeliveryPack HTML + 주요 CSV.

### 9.2 Calendar

- Google Calendar API, Microsoft Graph, CalDAV.
- 이벤트 종류: `review_meeting`, `office_hours`, `deadline_reminder`.
- 타임존은 WorkObject.request.metadata.timezone → fallback = 조직 기본 TZ.
- 참석자 자동 매핑: Slack user → email lookup.

### 9.3 구현 타입

```python
class EmailRequest(BaseModel):
    to: list[str]
    cc: list[str] = []
    subject: str
    body_html: str
    body_text: str
    attachments: list["EmailAttachment"] = []
    reply_to: str | None = None

class CalendarEventRequest(BaseModel):
    calendar_id: str
    summary: str
    description: str
    start: datetime
    end: datetime
    timezone: str
    attendees_email: list[str]
    conference_tool: Literal["meet","zoom","teams"] | None = None
```

---

## 10. BI Connector (P2)

### 10.1 역할

- 대시보드 카드/룩에 주석(annotation) 추가.
- 지표 단위/정의 변경 반영.
- 리포팅 수치의 "why" 를 설명하는 note 삽입.

### 10.2 Looker

- Looker API 4.0.
- Looks / Dashboards에 markdown note element 삽입은 LookML 변경이 필요 → fallback: Slack/Confluence로 설명 리다이렉트.
- Schedule API로 리포트 snapshot 예약 전송.

### 10.3 Tableau

- REST API via `TableauServerClient`.
- Comment API로 뷰에 코멘트 추가.
- 데이터 원본 refresh 트리거.

### 10.4 API 한계와 Fallback

| 한계 | Fallback |
|------|----------|
| Looker는 in-dashboard text 직접 수정 불가 | Confluence에 해설 게시 + 링크 pin |
| Tableau comment는 permalink 없음 | dashboard url + comment text를 WorkObject documentation에 저장 |
| BI write scope 미보유 조직 | read-only로 지표만 fetch, 주석은 Slack으로 |

---

## 11. Asana / Monday Connector (P3)

### 11.1 위치

- 많은 조직이 Jira 외 별도 PM 툴을 사용 → follow-up action을 Asana/Monday에 생성.
- Jira Connector와 동일한 port 인터페이스를 가지므로 Hub 입장에서는 구분 없이 호출.

### 11.2 매핑

| 추상 개념 | Asana | Monday |
|-----------|-------|--------|
| 프로젝트 | project | board |
| 티켓 | task | item |
| 담당자 | assignee | person column |
| 상태 | section | status column |
| 우선순위 | custom field | status column (variant) |

### 11.3 기본 원칙

- P3이므로 **feature flag 뒤**에 기본 비활성.
- Jira Connector 테스트 매트릭스를 공유 (공통 port).

---

## 12. Clean Architecture 매핑

```
src/
├── domain/
│   ├── entities/
│   │   ├── work_object.py           # WorkObject, sections
│   │   └── external_reference.py
│   ├── value_objects/
│   │   └── idempotency_key.py
│   ├── events/
│   │   ├── work_object_created.py
│   │   ├── external_dispatch_requested.py
│   │   └── external_dispatch_completed.py
│   ├── errors/
│   │   └── integration_errors.py    # ConnectorError, RateLimited, DuplicateDispatch
│   └── interfaces/
│       ├── connector.py             # Connector ABC
│       ├── work_object_repository.py
│       └── integration_event_repository.py
│
├── application/
│   ├── use_cases/
│   │   ├── create_work_object.py
│   │   ├── attach_external_reference.py
│   │   ├── dispatch_delivery_pack.py
│   │   ├── open_followup_tickets.py
│   │   └── close_work_object.py
│   ├── dtos/
│   │   └── dispatch_request_dto.py
│   ├── ports/
│   │   ├── policy_port.py           # §04
│   │   └── connector_registry_port.py
│   └── services/
│       └── dispatch_planner.py      # LLM이 어떤 connector 호출할지 결정
│
├── infrastructure/
│   ├── persistence/
│   │   ├── sqlite_work_object_repo.py
│   │   └── sqlite_integration_event_repo.py
│   └── external/
│       ├── integration_hub.py
│       ├── slack_connector.py
│       ├── jira_connector.py
│       ├── confluence_connector.py
│       ├── notion_connector.py
│       ├── git_connector.py
│       ├── email_connector.py
│       ├── calendar_connector.py
│       ├── looker_connector.py
│       ├── tableau_connector.py
│       ├── asana_connector.py
│       ├── monday_connector.py
│       └── credentials_store.py
│
└── tools/
    └── integration_tools.py         # @tool 함수 어댑터
```

- 의존성 방향: `tools → application → domain`, `infrastructure → application ports`, `domain`은 아무도 import하지 않음.
- LLM용 `@tool` 어댑터는 application use case를 감싸기만 한다(비즈니스 로직 금지).

---

## 13. SQLite 스키마 (migration v11)

```sql
-- migrations/v11_workflow_integration.sql

CREATE TABLE work_objects (
    work_object_id TEXT PRIMARY KEY,         -- WO-YYYY-NNNN
    title TEXT NOT NULL,
    task_contract_id TEXT NOT NULL,
    current_phase TEXT NOT NULL,
    request_json TEXT NOT NULL,              -- RequestSection JSON
    execution_json TEXT NOT NULL,
    documentation_json TEXT NOT NULL,
    follow_up_json TEXT NOT NULL,
    owner_agent TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    parent_work_object_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (task_contract_id) REFERENCES task_contracts(id),
    FOREIGN KEY (parent_work_object_id) REFERENCES work_objects(work_object_id)
);

CREATE INDEX idx_wo_phase ON work_objects(current_phase);
CREATE INDEX idx_wo_task_contract ON work_objects(task_contract_id);
CREATE INDEX idx_wo_updated ON work_objects(updated_at DESC);

CREATE TABLE integration_credentials (
    credential_id TEXT PRIMARY KEY,
    system TEXT NOT NULL,                    -- slack, jira, ...
    label TEXT NOT NULL,                     -- "growth-workspace"
    auth_type TEXT NOT NULL,                 -- oauth, api_token, basic
    encrypted_blob BLOB NOT NULL,            -- fernet-encrypted JSON
    scopes_json TEXT NOT NULL DEFAULT '[]',
    expires_at TEXT,
    rotated_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (system, label)
);

CREATE TABLE integration_event_log (
    event_id TEXT PRIMARY KEY,
    work_object_id TEXT NOT NULL,
    system TEXT NOT NULL,
    action TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_payload_hash TEXT NOT NULL,
    status TEXT NOT NULL,                    -- pending|success|failed|dlq|duplicate
    external_ref_json TEXT,
    attempt INTEGER NOT NULL DEFAULT 1,
    error_code TEXT,
    error_message TEXT,
    policy_decision_id TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    latency_ms INTEGER,
    FOREIGN KEY (work_object_id) REFERENCES work_objects(work_object_id)
);

CREATE UNIQUE INDEX idx_event_idempotency
  ON integration_event_log(idempotency_key)
  WHERE status IN ('success','duplicate');

CREATE INDEX idx_event_wo ON integration_event_log(work_object_id);
CREATE INDEX idx_event_dlq ON integration_event_log(status) WHERE status='dlq';

CREATE TABLE external_reference (
    reference_id TEXT PRIMARY KEY,
    work_object_id TEXT NOT NULL,
    system TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    url TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    idempotency_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (work_object_id) REFERENCES work_objects(work_object_id),
    UNIQUE (system, resource_type, resource_id)
);

CREATE INDEX idx_extref_wo ON external_reference(work_object_id);
```

Migration 적용:

```bash
python -m infra.migrate --to v11
```

---

## 14. 주요 도구 / 유스케이스

LLM이 사용하는 `@tool` 함수는 application use case의 thin adapter다.

### 14.1 `create_jira_ticket`

```python
@tool
def create_jira_ticket(
    work_object_id: str,
    summary: str,
    description_md: str,
    project_key: str,
    issue_type: str = "Task",
    assignee_email: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    due_date: str | None = None,
) -> dict:
    """
    후속 액션 Jira 티켓을 생성하거나, 동일 WorkObject+summary의 기존 티켓이
    있으면 그 참조를 반환합니다. Policy engine의 승인이 필요합니다.
    """
```

### 14.2 `post_to_slack`

```python
@tool
def post_to_slack(
    work_object_id: str,
    channel: str,
    summary_md: str,
    thread_ts: str | None = None,
    include_delivery_pack: bool = False,
    mention_requestor: bool = True,
) -> dict: ...
```

### 14.3 `publish_confluence_page`

```python
@tool
def publish_confluence_page(
    work_object_id: str,
    space_key: str,
    title: str,
    body_md: str,
    parent_page_id: str | None = None,
    labels: list[str] | None = None,
    edit_existing: bool = False,
) -> dict: ...
```

### 14.4 `open_git_pr`

```python
@tool
def open_git_pr(
    work_object_id: str,
    repo: str,
    base_branch: str,
    files: list[dict],        # [{path, content, mode}]
    title: str,
    body_md: str,
    reviewers: list[str] | None = None,
    draft: bool = False,
) -> dict: ...
```

### 14.5 `link_external_resource`

```python
@tool
def link_external_resource(
    work_object_id: str,
    system: str,
    resource_type: str,
    resource_id: str,
    url: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """
    이미 외부에 존재하는 리소스를 WorkObject에 연결 (e.g. 수동으로 만든 Jira 이슈).
    새 dispatch를 발생시키지 않습니다.
    """
```

### 14.6 WorkObject CRUD Use Cases

- `CreateWorkObjectUseCase(task_contract_id, request_section) -> WorkObject`
- `AttachExternalReferenceUseCase(work_object_id, reference)`
- `AdvancePhaseUseCase(work_object_id, to_phase)`
- `CloseWorkObjectUseCase(work_object_id, reason)`
- `ListWorkObjectsUseCase(filters)`
- `GetWorkObjectTimelineUseCase(work_object_id) -> list[IntegrationEvent]`

모든 use case는 `PolicyPort`를 생성자 주입 받아, 외부 write가 발생하는 경우 승인 여부를 먼저 확인한다.

### 14.7 Integration Tools 확장 지점

기존 `tools/integration_tools.py` 의 Postgres 도구는 유지하되, 동일 모듈에 위 @tool들을 추가한다. 모두 `application/use_cases` 호출로만 구현되며, infra 직접 import 금지.

---

## 15. 정책 / 보안

### 15.1 Policy Engine 게이트 (§04 연동)

모든 외부 write action은 dispatch 전에 `PolicyPort.check(action_spec)`를 통과해야 한다.

| Action Class | 기본 Policy | Dual Approval |
|--------------|------------|---------------|
| Slack 내부 채널 post | auto-approve | No |
| Slack 외부/고객 채널 post | require human | Yes (DS + 매니저) |
| Jira ticket 생성 | auto-approve (ds-agent 라벨) | No |
| Jira 전사 프로젝트 생성 | require human | Yes |
| Confluence new page (팀 space) | auto-approve | No |
| Confluence edit (CEO 스페이스 등) | require human | Yes |
| Git PR (draft) | auto | No |
| Git PR (ready + merge 대상 main) | require human | Optional |
| Email 외부 발송 | require human | Yes |
| Calendar 외부인 초대 | require human | Yes |
| BI write | require human | Yes |

Policy decision id는 `integration_event_log.policy_decision_id`에 저장되어 감사 가능.

### 15.2 Redaction

- Connector dispatch 직전 payload는 `PIIRedactor` 를 통과.
- redact 대상: 이메일, 전화번호, 주민등록번호, 내부 secret 토큰, 개인 이름(옵션).
- redact 후의 **hash** 만 event log에 저장. 원문은 local encrypted store에만.

### 15.3 감사 로그

- 모든 outbound dispatch는 `integration_event_log` + `dev/logs/audit/integration-YYYYMMDD.log` (JSON line).
- Log fields: timestamp, actor=ds-agent-<version>, work_object_id, system, action, idempotency_key, policy_decision_id, status, latency_ms, user_identifier(initiator)
- 7년 보관 (조직 정책에 따라 조정), 로그 자체는 append-only FS (WORM) 마운트 권장.

### 15.4 잘못 보낸 메시지 회수

- Slack: `chat.delete` (15분 내) / message edit with retraction note.
- Jira: ticket transition to `Closed (Cancelled)` + comment "auto-retraction".
- Email: 외부 회수는 원리적으로 불가 → 후속 정정 메일 자동 발송 + 감사 로그에 incident 표식.
- 회수 액션 자체도 WorkObject에 기록.

---

## 16. Prompt 통합

### 16.1 시스템 프롬프트 주입

에이전트 초기화 시 사용 가능한 connector 목록을 system prompt에 주입한다:

```
## Available Integrations
You can dispatch actions through the following channels. Choose based on
stakeholder channel of origin, sensitivity, and action type.

- slack (available, scopes: chat.write, files.write, ...)
    preferred for: quick updates, requestor threads, approvals
- jira (available, project_keys: GROWTH, PLATFORM)
    preferred for: follow-up tasks, bugs, experiments
- confluence (available, spaces: DS, GROWTH)
    preferred for: long-form reports, weekly notes
- git:github (available, repos: org/ds-notebooks, org/growth-models)
    preferred for: reproducible code, peer review
- email (available, sender: ds-agent@company.com)
    preferred for: executive summaries, external stakeholders
- calendar (available, calendar_id: ds-team@company.com)
    preferred for: review meetings, office hours

## Decision Guidelines
- Always open a WorkObject before dispatching any external action.
- Prefer Slack threads for conversational follow-ups to keep context.
- Follow-up tickets go to Jira; PM-tool variants need explicit user opt-in.
- Documentation longer than 20 lines -> Confluence/Notion, not Slack.
- Code changes -> Git PR (draft first, ready only after policy approval).
```

### 16.2 Tool Selection Context

- `dispatch_planner` (application service) 는 WorkObject와 DeliveryPack을 받아 LLM에게 **일종의 "배송 계획 질의"** 를 수행.
- LLM의 출력은 structured: `DispatchPlan = list[DispatchStep]`. 각 step은 어떤 @tool을 어떤 인자로 호출할지 명시.
- 계획이 policy check를 통과하면 순차/병렬 실행.
- 실패한 step은 재계획 루프 (LLM에게 결과 피드백 후 다음 시도).

---

## 17. UX

### 17.1 Electron: WorkObjectPanel

- 왼쪽 트리: WorkObject 리스트 (phase 필터, 검색).
- 본문: 4 섹션 탭 (Request / Execution / Documentation / Follow-up).
- 타임라인 뷰: `integration_event_log` 기반 스트리밍 로그.
- 각 섹션 하단에 "Preview 채널별 메시지" 버튼 (Slack Block Kit 프리뷰, Confluence HTML 프리뷰).
- phase transition 버튼: advance/close/fail.

### 17.2 Electron: IntegrationSettings

- 좌측: 시스템 리스트. 각각 "Connected / Not connected / Expired" 뱃지.
- 우측: credential 입력 폼 (OAuth start 버튼 또는 토큰 입력).
- Health check 실행 버튼. 최근 10건 dispatch 결과 미니 테이블.
- Rotate/revoke 액션.

### 17.3 채널별 미리보기

- Slack: Block Kit Builder JSON을 시뮬레이션 뷰로 렌더.
- Confluence: storage format → HTML 프리뷰.
- Jira: issue creation form dry-run 결과.
- Git: diff 프리뷰 (monaco-diff 컴포넌트).
- Email: HTML + text fallback toggle.

### 17.4 CLI

- `ds-agent work list --phase=review`
- `ds-agent work show WO-2026-0042`
- `ds-agent work dispatch WO-2026-0042 --plan-only` (dry run)
- `ds-agent integration health`
- `ds-agent integration replay --event <event_id>`

---

## 18. 구현 Phases (TDD)

### Phase P2a — Work Object 도메인 + Slack & Jira 기초 (8–12h)

RED:
- `tests/unit/domain/test_work_object.py` — section 생성/검증/상태 전이.
- `tests/unit/domain/test_external_reference.py` — idempotency_key 유일성.
- `tests/integration/infrastructure/test_slack_connector.py` — httpretty/`respx` 기반 mock.
- `tests/integration/infrastructure/test_jira_connector.py` — 동일.

GREEN:
- `domain/entities/work_object.py`, `external_reference.py`
- `infrastructure/external/integration_hub.py` (공통 dispatch loop)
- `infrastructure/external/slack_connector.py`
- `infrastructure/external/jira_connector.py`
- Migration v11 적용.
- `tools/integration_tools.py` 에 `post_to_slack`, `create_jira_ticket`, `link_external_resource` 추가.

REFACTOR:
- Hub 내 재시도/idempotency 로직 strategy 패턴으로 분리.
- Connector 별 공통 rate limiter 추출.

Quality gate: §04 policy hook 연결, >=80% 커버리지.

### Phase P3a — Confluence/Notion + Git PR (10–14h)

RED:
- `tests/integration/infrastructure/test_confluence_connector.py`
- `tests/integration/infrastructure/test_notion_connector.py`
- `tests/integration/infrastructure/test_git_connector.py`
- DeliveryPack → Confluence storage format 변환 snapshot 테스트.

GREEN:
- Confluence/Notion/GitHub/GitLab connector 구현.
- `publish_confluence_page`, `open_git_pr` 도구.
- 브랜치/PR naming, CI 상태 폴링.

REFACTOR: 공통 문서 변환 파이프라인 (`MdToStorageFormat`, `MdToNotionBlocks`).

### Phase P3b — WorkObject Timeline UX (6–8h)

- Electron WorkObjectPanel, IntegrationSettings.
- CLI `ds-agent work/integration ...`.
- E2E 테스트: 한 WorkObject에 대해 Slack→Jira→Confluence→Git 전 과정 시나리오.

### Phase P3+ — Email/Calendar/BI (각 6–10h)

- Email/Calendar: template system, timezone resolver.
- Looker/Tableau: 권한별 fallback 전략 구현.
- Feature flag로 점진 롤아웃.

### Phase P4 — Asana/Monday + DLQ 운영 도구 (8h)

- Asana/Monday connector.
- DLQ CLI replay, webhook incident dashboard.

---

## 19. 테스트 전략

### 19.1 Mock 서버 / Recording

- `respx` (httpx) 또는 `pytest-httpserver`로 시스템별 응답을 고정.
- 실 운영 API에서 한번 캡처한 응답을 `tests/fixtures/integration/<system>/*.json` 으로 저장 (replay 테스트).
- Credential은 테스트용 더미, 실제 토큰은 `.env.test`에 두지 않음.

### 19.2 Dry-run 모드

- 모든 connector가 `dry_run=True` 플래그 지원.
- dry_run에서는 실제 API 호출 없이 생성될 payload + 예상 external_ref를 반환.
- CI 파이프라인은 dry_run으로 전 시스템 통합 플로우를 매 PR 검증.

### 19.3 Idempotency 검증

- Property-based test (Hypothesis):
  "같은 request payload + 같은 idempotency_key 로 N회 dispatch 시 external_ref는 항상 동일하고, 2번째 이후 status == duplicate."
- 동시성 테스트: `asyncio.gather` 로 동일 key 10회 → 단 1회만 실제 외부 호출.

### 19.4 Policy 통합 테스트

- require_human 정책이 걸린 action은 dispatch되지 않고 pending 상태 유지.
- 승인 이벤트 수신 후 자동 재개.

### 19.5 장애 시뮬레이션

- `toxiproxy` 또는 test-level sleep/fault injection.
- 429, 5xx, timeout 각 케이스에 대해 재시도/DLQ 경로 검증.

---

## 20. 의존성 및 통합 지점

| 대상 | 관계 |
|------|------|
| §01 TaskContract | WorkObject.execution.task_contract_id 로 1:1 이상 연결. TaskContract ratification 이벤트가 WorkObject INTAKE→EXECUTING 트리거. |
| §04 Policy Engine | 모든 외부 write 전 `PolicyPort.check` 호출. |
| §07 DeliveryPack | DispatchPlanner의 입력. DeliveryPack artifact url이 Slack/Confluence/Email 첨부로 전달. |
| §09 Async Portfolio Manager | WorkObject queue가 portfolio manager 의 관측 단위. |
| §10 Observability | integration_event_log → 운영 대시보드. |
| 기존 `tools/integration_tools.py` | Postgres 등 기존 데이터 도구 유지, 본 스펙은 "쓰기 방향 외부 시스템" 을 추가. |

---

## 21. 성공 기준 (DoD)

### 21.1 정량 지표

| 지표 | 목표 |
|------|------|
| Connector dispatch 성공률 (P0 systems) | >= 99.0% (재시도 포함) |
| Idempotency violation (중복 외부 리소스) | 0건 / 30일 |
| Policy-gated action의 무단 우회 | 0건 |
| 요청 → 첫 dispatch 까지 평균 시간 | <= 2분 (자동화 경로) |
| WorkObject 당 평균 follow-up action 수 | >= 1.2 (분석이 티켓/미팅으로 연결) |
| Dispatch plan accuracy (LLM이 선택한 채널이 사람 평가와 일치) | >= 90% |

### 21.2 정성 기준

- 임의의 DS 요청이 Slack에서 시작해 Slack 스레드의 "Closed" 배너로 끝나는 루프가 E2E로 동작한다.
- 운영자가 Electron WorkObjectPanel만으로 전 라이프사이클을 검수할 수 있다.
- Connector 추가가 기존 코드 수정 없이 새 파일 + registry 등록만으로 가능하다(OCP).

---

## 22. 리스크 및 롤백

| 리스크 | 확률 | 영향 | 완화 |
|--------|------|------|------|
| 외부 시스템 장애로 dispatch 실패 | High | Medium | DLQ + 재시도 + 사용자 요약에 pending 명시 |
| 잘못된 채널에 민감 메시지 전송 | Low | High | policy dual approval + redaction + 15분 내 chat.delete |
| OAuth 토큰 만료 | Medium | Medium | 만료 7일 전 알림, refresh flow 자동화 |
| idempotency key 충돌 | Low | High | WorkObject id + action + payload hash 조합, unique index |
| LLM이 과도한 티켓 생성 | Medium | Medium | action budget per WorkObject (default: Jira 5, Slack 10, Email 2) |
| 감사 로그 변조 시도 | Low | High | WORM 스토리지 + hash chain |
| Confluence edit 충돌 (동시 사람 편집) | Medium | Low | version 비교 후 conflict 시 새 페이지로 fork + 사람에 알림 |
| PII 유출 | Low | High | redactor gate + 서비스 계정 권한 최소화 |

### 롤백 전략

- **Phase P2a 실패**: migration v11 롤백 스크립트 (`v11_down.sql`), feature flag `workflow_integration.enabled=false`로 모든 connector 비활성. 기존 integration_tools 경로는 영향 없음.
- **특정 connector 오작동**: `IntegrationHub.disable(system)` 로 런타임 비활성. DispatchPlanner는 해당 system을 후보에서 제외.
- **잘못 전송된 대량 메시지**: `ds-agent integration retract --work-object <id>` — 지원되는 시스템에 대해 회수 액션 자동 수행, 불가한 경우 후속 정정 메시지 + incident 보고.

---

## 22.1 Implementation Status Update (2026-04-16)

- Landed in the current slice:
  - `WorkObject` / `ExternalReference` / `IntegrationEvent` domain models
  - SQLite-backed `v11` persistence for `work_objects`, `integration_event_log`, and `external_reference`
  - `CreateWorkObjectUseCase`, `AttachExternalReferenceUseCase`, `AdvancePhaseUseCase`, `CloseWorkObjectUseCase`, `ListWorkObjectsUseCase`, `GetWorkObjectTimelineUseCase`
  - `tools/integration_tools.py` additions for WorkObject CRUD/timeline plus tracked `post_to_slack` and `create_jira_ticket`
  - Basic `SlackConnector`, `JiraConnector`, idempotent `IntegrationHub`, and injected `PolicyPort.check(...)` gating before outbound Slack/Jira writes
  - Policy-blocked dispatch persistence as `integration_event_log.status = pending|failed` plus `pending_policy_actions` on the WorkObject aggregate
  - Dedicated Slack/Jira mock-server connector coverage for HTTP payload/auth roundtrip
  - Shared markdown conversion pipeline via `document_converters.py` (`markdown_to_confluence_storage`, `markdown_to_notion_blocks`)
  - Workflow-tracked `ConfluenceConnector`, `NotionConnector`, and `GitConnector` with dry-run support and mock-server coverage for GitHub and GitLab flows
  - `publish_confluence_page`, `publish_notion_page`, and `open_git_pr` tool paths that attach documentation references back onto the WorkObject timeline
  - `IntegrationHub` extension for Confluence/Notion/Git dispatch with the same idempotency and policy-gating surface used by Slack/Jira
  - Conservative autonomy classification and permission registration for the new documentation/pull-request write tools
- Verified:
  - `pytest tests/integration/infrastructure/test_confluence_connector.py tests/integration/infrastructure/test_notion_connector.py tests/integration/infrastructure/test_git_connector.py tests/integration/infrastructure/test_slack_connector.py tests/integration/infrastructure/test_jira_connector.py tests/integration/infrastructure/test_sqlite_work_object_store.py tests/unit/tools/test_integration_tools.py tests/integration/test_all_tools_registered.py tests/unit/runtime/test_action_classifier.py tests/unit/domain/test_work_object.py tests/unit/domain/test_external_reference.py` -> `79 passed`
  - `ruff check` on touched files -> clean
  - targeted `mypy` on the new Workflow Integration slice -> clean
  - `python -m compileall src/ds_agent/infrastructure/external src/ds_agent/tools/integration_tools.py src/ds_agent/runtime/action_classifier.py src/ds_agent/agent/permissions.py` -> clean
- P2a status:
  - P2a scope is now effectively complete.
- P3a status:
  - P3a foundation is now landed for Confluence/Notion/Git publishing flows.
- P3b status:
  - Richer request-source ingestion plus operator mutation surfaces are now landed for backend/CLI flows.
  - `POST /api/work-objects/intake`, `GET /api/work-objects/{work_object_id}/timeline`, `POST /api/work-objects/{work_object_id}/phase`, and `POST /api/work-objects/{work_object_id}/close` are in place for structured request intake and lifecycle control.
  - `ds-agent work intake|list|show|timeline|advance|close` now covers the same WorkObject lifecycle with request metadata parsing and external-reference bootstrap.
  - Presenter output now includes typed request-source/requestor context, metadata, and standalone timeline rendering for operator-facing surfaces.
- Verified:
  - `pytest tests/unit/infrastructure/test_work_object_api_routes.py tests/unit/infrastructure/test_work_cli.py tests/unit/presentation/test_work_object_presenters.py` -> `12 passed`
  - combined Workflow Integration regression -> `89 passed`
  - `ruff check` on touched files -> clean
  - targeted `mypy` on `work_objects.py`, `work_cli.py`, `work_object_presenters.py` -> clean
  - `python -m compileall src/ds_agent/api/routes/work_objects.py src/ds_agent/cli/work_cli.py src/ds_agent/presentation/work_object_presenters.py` -> clean
- Remaining work:
  - Electron-side mutation controls for WorkObject intake/phase/close
  - IntegrationSettings / integration health / replay surfaces
  - packaged WorkObject E2E coverage
  - later P3b/P3c connectors and operations (Email/Calendar/BI plus DLQ/replay operations)

## 23. Open Questions

1. **Multi-tenant credential 모델**: 조직 내 여러 Slack workspace / 여러 Jira instance를 동시에 쓰는 회사를 초기부터 지원할지, 단일 tenant로 시작할지.
2. **Slack/Email 요청 수신에서의 LLM 전체 노출**: inbound 요청 payload 전체를 LLM 컨텍스트에 투입할 때의 PII 처리 수준을 어디까지 강제할지 (§04와 정책 공유).
3. **Git Connector의 자동 merge 허용 범위**: draft → ready까지 허용하되, merge까지 자동화할지 여부. 조직별 CODEOWNERS 의존성.
4. **Confluence vs Notion 우선순위**: 두 문서 시스템을 동시에 운영하는 조직에서 "DeliveryPack의 canonical source"를 어디에 둘지.
5. **BI Connector의 write scope 정책**: 많은 조직이 BI에 write를 막아둠 → read + commentary fallback만 지원할지, 요청 시에만 write를 여는 dynamic policy로 갈지.
6. **WorkObject의 분기/병합**: 하나의 원 요청이 여러 WorkObject로 분화되거나, 여러 WorkObject가 하나의 리포트로 합쳐지는 경우의 모델링. parent/child만으로 충분한지, DAG가 필요한지.
7. **Async Portfolio Manager(§09)와의 스케줄링 결합**: WorkObject의 phase transition이 포트폴리오 우선순위에 반영되는 정확한 이벤트 흐름.
8. **외부 봇과의 구별**: Slack에서 다른 Bot(예: Jira Cloud for Slack)이 동일 스레드에 끼어들 때 WorkObject가 그 메시지를 어떻게 흡수/무시할지.
9. **i18n**: 사내 공용어가 한국어/영어 혼용일 때 외부 메시지 언어 정책 (template-locale per channel?).
10. **Cost observability**: Slack/Jira/Confluence API 자체 비용은 낮지만 첨부 스토리지/Email relay 비용이 누적될 때의 예산 게이트.

---

(끝)
