# 10. Self-Improvement 거버넌스 — 학습 결과의 책임 있는 승격

> 본 문서는 `Docs/ds-agent-enhancement-roadmap.md` §10 (Self-Improvement 거버넌스)의 상세 구현 스펙이다. DS Agent가 실행 trace로부터 자동 추출한 학습 산출물(패턴, 도메인 KB 항목, 커스텀 스킬)을 조직 표준으로 승격하기 전에 거쳐야 할 Learning Inbox, 리뷰 워크플로, 상태 머신, 재검증 스케줄, Deprecation 경로를 정의한다.

---

## 1. 배경 및 문제 정의

### 1.1 현재 상태

DS Agent의 `src/self_improve/` 모듈은 다음을 자동으로 수행한다.

- 실행 trace에서 자주 등장하는 액션 시퀀스/에러 패턴 추출 (`ExtractedPattern`).
- 사용자 피드백과 성공한 분석을 도메인 KB 항목으로 전환 (`DomainKBEntry`).
- 반복되는 분석 블록을 묶어 커스텀 스킬로 등록 (`CustomSkill`).

이 자동화는 개인 사용자에게는 강력한 학습 효과를 제공하지만, 기업 환경에 DS Agent를 배포할 경우 다음과 같은 위험을 내포한다.

1. **표준의 오염.** 한 사용자의 우연한 성공 패턴이 조직 전체 프롬프트에 반영되어 다른 프로젝트를 오도한다.
2. **데이터 누수.** 특정 프로젝트의 고유 지식(지표 정의, 도메인 용어)이 보편 KB로 승격되어 다른 프로젝트의 실행에 끼어든다.
3. **드리프트 은폐.** 자동 학습 결과가 소리 없이 축적되면, 어느 시점부터 에이전트 동작이 바뀐 이유를 추적하기 어렵다.
4. **기존 지식과의 충돌.** 새 학습 결과가 이미 검증된 항목과 모순되더라도 자동으로 덮어쓰여 품질이 저하된다.
5. **책임 소재 불분명.** "누가 이 지식을 승인했나?"라는 감사 질문에 답할 수 없다.

### 1.2 핵심 문제

> **자동 학습 결과가 곧바로 조직 표준이 되면 위험하다.**

자동 추출은 계속 자동이어야 한다. 그러나 **조직 표준으로의 승격은 반드시 사람 리뷰와 정책 게이트, 회귀 테스트를 통과해야 한다.** 본 스펙은 그 사이에 **Learning Lifecycle 상태 머신**을 삽입한다.

### 1.3 범위

- 자동 추출 로직 자체는 유지하되, 산출물의 기본 상태를 `proposed`로 변경.
- Learning Inbox, 리뷰 UI, 상태 전이 API 신설.
- 승격 시 §05 Evaluation Harness의 Gold Task Set 회귀 테스트를 게이트로 사용.
- 승격 후 재검증 스케줄, 성능 하락 자동 감지, Deprecation 경로 구축.
- §02 Semantic Memory, §04 MissionPack과의 통합 지점 정의.

### 1.4 범위 밖

- Self-Improvement 알고리즘 자체(패턴 추출 알고리즘 개선)는 본 스펙의 관심사가 아니다. 본 스펙은 "추출된 것을 어떻게 다룰 것인가"에 집중.
- 멀티 조직/테넌트 간 지식 공유 정책은 별도 스펙에서 다룬다.

---

## 2. 핵심 테제

1. **자동 추출은 유지한다.** LLM Orchestrator 원칙에 따라 패턴/KB/스킬 추출은 백그라운드에서 자동으로 이뤄진다.
2. **승격은 반드시 거버넌스 게이트를 통과한다.** proposed → promoted 사이에 최소 한 번의 사람 리뷰 혹은 정책 승인이 있어야 한다.
3. **승격 이후에도 감시한다.** promoted 아이템은 재검증 스케줄에 등록되어 성능 하락 시 자동 deprecated.
4. **롤백 가능성은 상시 유지.** 승격 이력과 비활성화 이력을 모두 기록하여 언제든 되돌릴 수 있다.
5. **충돌은 숨기지 않는다.** 기존 지식과의 모순은 감지하여 리뷰어에게 드러내고 동시 유효를 허용하지 않는다.
6. **Typed artifact 중심.** 모든 학습 산출물, 리뷰 이벤트, 승격 기록은 Pydantic 모델로 정의하여 감사 가능하게 한다.

---

## 3. Learning Lifecycle 상태 머신

### 3.1 상태 정의

```
                 ┌────────────────┐
                 │   proposed     │  (자동 추출 직후)
                 └───────┬────────┘
                         │ reviewer opens
                         ▼
                 ┌────────────────┐
                 │  under_review  │
                 └───────┬────────┘
          ┌──────────────┼──────────────┐
          │              │              │
   approve│       modify │         reject│
          ▼              ▼              ▼
   ┌──────────┐   ┌───────────┐   ┌───────────┐
   │ approved │   │ modified  │   │ rejected  │───► archived
   └────┬─────┘   └─────┬─────┘   └───────────┘
        │               │ re-review
        │               └────► under_review
        │
        │ eval gate pass
        ▼
   ┌──────────┐
   │ promoted │  (조직 표준 자산)
   └────┬─────┘
        │ schedule tick
        ▼
   ┌──────────┐   regression detected
   │monitored │────────────┐
   └────┬─────┘            │
        │ manual           │
        │ deprecate        ▼
        │            ┌───────────┐
        └───────────►│deprecated │───► archived (after grace)
                     └───────────┘
```

### 3.2 전이 조건 및 트리거

| 전이 | 트리거 | 정책 체크 | 자동/사람 |
|------|--------|-----------|-----------|
| (new) → proposed | self_improve가 추출 완료 | 중복/충돌 사전 검사 | 자동 |
| proposed → under_review | 리뷰어가 inbox에서 오픈 | 권한 확인 | 사람 |
| under_review → approved | 리뷰어가 승인 | 체크리스트 완료 여부 | 사람 |
| under_review → modified | 리뷰어가 내용 수정 | diff 기록 | 사람 |
| modified → under_review | 재검토 필요 | — | 자동 |
| under_review → rejected | 리뷰어가 기각 | 사유 필수 | 사람 |
| approved → promoted | Eval gate 자동 실행 후 통과 | 회귀 점수 임계 통과 | 자동 (사람이 승인한 경우) |
| approved → rejected | Eval gate 실패 | 실패 사유 기록 | 자동 |
| promoted → monitored | 정기 재검증 틱 도달 | — | 자동 |
| monitored → monitored | 재검증 통과 | — | 자동 |
| monitored → deprecated | 성능 임계 하락 또는 수동 | 사유 기록 | 자동 + 사람 |
| deprecated → archived | grace period 경과 | — | 자동 |
| rejected → archived | 즉시 | — | 자동 |

### 3.3 허용되지 않는 전이

- proposed → promoted 직행 금지 (리뷰 생략 불가).
- approved → promoted 직행 금지 (Eval gate 생략 불가).
- deprecated → promoted 직행 금지. 반드시 new proposed로 다시 제출.
- archived → 임의 상태 복귀 금지. 아카이브는 종결 상태.

### 3.4 병렬 상태

동일한 원천 패턴이 여러 번 추출될 수 있다. 이 경우 `LearningItem.signature`로 그룹화하고 가장 최신 것을 `current`로 마킹. 나머지는 `superseded` 플래그.

---

## 4. LearningItem 스키마

### 4.1 공통 베이스

```python
# src/domain/learning/entities.py
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime

LearningStatus = Literal[
    "proposed", "under_review", "approved", "modified",
    "rejected", "promoted", "monitored", "deprecated", "archived"
]

LearningType = Literal["pattern", "kb_entry", "custom_skill"]

class SourceInfo(BaseModel):
    run_ids: list[str]                 # 추출에 기여한 실행 ID들
    session_ids: list[str]
    project_id: Optional[str] = None
    extracted_at: datetime
    extractor_version: str             # 자동 추출기 버전

class Evidence(BaseModel):
    metric_name: str                   # e.g., "success_rate", "user_thumbs_up"
    metric_value: float
    sample_size: int
    confidence: float                  # 0~1
    raw_refs: list[str] = Field(default_factory=list)  # trace snippet ids

class ConflictRef(BaseModel):
    conflict_type: Literal["semantic_overlap", "explicit_contradiction", "duplicate"]
    conflicting_item_id: str
    similarity: float
    note: str

class LearningItem(BaseModel):
    item_id: str                       # UUID
    type: LearningType
    signature: str                     # dedup key (semantic hash)
    title: str
    summary: str
    status: LearningStatus = "proposed"
    version: int = 1
    source: SourceInfo
    evidence: list[Evidence]
    conflicts: list[ConflictRef] = Field(default_factory=list)
    current: bool = True
    superseded_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
```

### 4.2 하위 타입

```python
class ExtractedPattern(LearningItem):
    type: Literal["pattern"] = "pattern"
    pattern_body: str                  # natural language 설명
    action_sequence: list[str]         # normalized action ids
    applicable_when: str               # 적용 조건 텍스트

class DomainKBEntry(LearningItem):
    type: Literal["kb_entry"] = "kb_entry"
    kb_key: str                        # hierarchical key, e.g., "finance.metrics.ltv"
    kb_value: str
    tags: list[str]
    language: str = "ko"

class CustomSkill(LearningItem):
    type: Literal["custom_skill"] = "custom_skill"
    skill_name: str
    skill_description: str
    skill_body_path: str               # path to skill markdown / tool spec
    required_tools: list[str]
    io_schema: dict
```

### 4.3 리뷰/승격 아티팩트

```python
ReviewDecision = Literal["approve", "modify", "reject"]

class ReviewEvent(BaseModel):
    event_id: str
    item_id: str
    reviewer: str
    decision: ReviewDecision
    checklist: dict[str, bool]         # 체크리스트 항목별 결과
    comment: str
    diff: Optional[dict] = None        # modify인 경우 변경 내역
    created_at: datetime

class PromotionRecord(BaseModel):
    promotion_id: str
    item_id: str
    version: int
    promoted_by: str                   # user or "system"
    approved_review_id: str            # 승인된 ReviewEvent
    eval_report_id: str                # §05 Evaluation Harness 보고서
    eval_score: float
    baseline_score: float
    promotion_alias: Optional[str] = None  # e.g., "finance_kb_v3"
    rollback_ref: Optional[str] = None     # 이전 활성 버전의 promotion_id
    created_at: datetime

class DeprecationRecord(BaseModel):
    deprecation_id: str
    item_id: str
    reason_code: Literal[
        "regression", "manual", "conflict", "superseded", "policy"
    ]
    reason_text: str
    replacement_item_id: Optional[str] = None
    grace_period_days: int = 14
    effective_from: datetime
    archived_at: Optional[datetime] = None
    created_at: datetime

class ConflictAlert(BaseModel):
    alert_id: str
    item_id: str
    detected_at: datetime
    conflicts: list[ConflictRef]
    resolved: bool = False
    resolution_note: Optional[str] = None
```

### 4.4 불변 규칙

- `item_id`는 생성 후 변경 불가. 내용 수정은 `version` 증가로 표현.
- `source`는 생성 후 변경 불가. 재추출 시 새 `LearningItem`이 생성되고 signature로 연결.
- `promoted` 상태 진입은 반드시 `PromotionRecord`를 수반.
- `deprecated` 상태 진입은 반드시 `DeprecationRecord`를 수반.

---

## 5. Learning Inbox

### 5.1 역할

리뷰 대기 큐. proposed/under_review/modified 상태의 `LearningItem`을 리뷰어에게 제시한다.

### 5.2 쿼리 파라미터

| 파라미터 | 의미 | 예시 |
|----------|------|------|
| `status` | 상태 필터 | `proposed`, `under_review` |
| `type` | 학습 타입 | `pattern`, `kb_entry`, `custom_skill` |
| `project_id` | 추출 프로젝트 | `proj_retail_2026` |
| `since` | 추출 이후 | ISO timestamp |
| `priority` | 우선순위 | `high`, `normal`, `low` |
| `has_conflict` | 충돌 포함 여부 | `true` |
| `assignee` | 배정 리뷰어 | user id |

### 5.3 우선순위 산정

자동 priority 계산 공식.

```
priority_score =
    0.4 * w_evidence(confidence, sample_size)
  + 0.3 * w_conflict(has_conflict ? 1 : 0)
  + 0.2 * w_scope(organization_wide ? 1 : 0.3)
  + 0.1 * w_staleness(days_since_extraction)
```

점수별 버킷: `>=0.7` high, `>=0.4` normal, 그 외 low.

### 5.4 리뷰 부담 분산 전략

- **Round-robin 배정.** 프로젝트 소유자 그룹 내 리뷰어에게 순환 배정.
- **Auto-batch.** 동일 signature로 그룹화되는 다중 아이템은 하나의 리뷰 티켓으로 묶어 제공.
- **SLA 알림.** high 버킷은 48시간, normal은 7일, low는 30일 내 리뷰되지 않으면 알림.
- **Escalation.** SLA 초과 시 상위 리뷰어로 에스컬레이션.
- **Reviewer Load Cap.** 1인 동시 오픈 티켓 상한(기본 10개)을 초과하면 신규 배정 중단.

### 5.5 Dedup 처리

- 동일 signature 아이템이 제안되면 기존 것에 evidence를 누적하고 새 아이템은 생성하지 않는다.
- 단, 기존이 `archived`/`rejected`인 경우 새로 생성하되 과거 이력을 참조 링크로 연결.

---

## 6. 리뷰 워크플로

### 6.1 리뷰어 역할

| 역할 | 권한 |
|------|------|
| `reviewer` | 리뷰 작성, approve/modify/reject |
| `senior_reviewer` | 충돌 해결 권한, escalation 처리 |
| `governance_admin` | 정책 수정, 강제 deprecate, 아카이브 삭제 |

역할은 §04 Authority Mode와 연동되며, 개인 사용자 모드에서는 `reviewer`와 `governance_admin`이 동일 인물일 수 있다.

### 6.2 체크리스트

리뷰어는 decision 전에 다음 항목을 반드시 평가한다.

```
[ ] 추출 프로젝트/세션은 신뢰할 만한가? (sample_size >= 3, 실패 세션 비율 확인)
[ ] 검증 지표는 이 지식의 유효성을 뒷받침하는가?
[ ] 기존 지식과 충돌하지 않는가? (ConflictAlert 확인)
[ ] 조직 전체에 일반화 가능한가, 특정 프로젝트에만 국한되는가?
[ ] 민감 정보/PII/비밀 값이 본문에 포함되어 있지 않은가?
[ ] 스킬의 경우: 도구 호출이 Authority Mode와 호환되는가?
[ ] KB 항목의 경우: 계산식/정의가 이미 등록된 metric catalog와 일치하는가?
```

체크리스트 결과는 `ReviewEvent.checklist`에 dict로 저장된다. 단, 모든 항목이 `true`일 필요는 없으며 `approve` 결정 시 필수 항목(민감 정보 없음, 충돌 검토 완료)만 강제한다.

### 6.3 Decision 기록

- `approve`: 체크리스트 만족 + 코멘트 권장. 자동으로 eval gate 단계로 진입.
- `modify`: 제목/본문/조건/적용 범위 수정 가능. diff가 `ReviewEvent.diff`에 기록. 상태는 `modified`로 전이 후 재검토 큐로.
- `reject`: 사유 필수. 상태는 `rejected`로 전이 후 일정 보관 기간 후 `archived`.

### 6.4 Second-Reviewer 규칙

다음 조건 중 하나에 해당하면 두 번째 리뷰어 승인을 요구.

- 타입이 `custom_skill`이고 `required_tools`에 destructive tool 포함.
- `ConflictAlert`가 해결되지 않은 상태.
- 범위가 organization-wide인 `DomainKBEntry`.
- priority가 `high`.

두 번째 리뷰는 독립적인 `ReviewEvent`로 기록되며 decision이 일치해야 다음 단계로 진행.

---

## 7. 승격(Promotion) 메커니즘

### 7.1 승격 파이프라인

```
approved 상태 진입
  ↓
PromotionPipeline.run(item)
  ├─ 1. Conflict re-check (최신 상태 기준)
  ├─ 2. Eval gate 실행 (§05)
  ├─ 3. 버전/alias 결정
  ├─ 4. 조직 자산 저장소 반영
  ├─ 5. PromotionRecord 기록
  └─ 6. 상태 → promoted, 기존 active 버전은 superseded
```

### 7.2 조직 자산 저장소

승격 대상별 반영 위치.

| 타입 | 저장소 |
|------|--------|
| ExtractedPattern | `domain_kb.json` 의 `patterns` 섹션 또는 semantic memory §02 |
| DomainKBEntry | `domain_kb.json` 의 해당 키 또는 metric catalog |
| CustomSkill | `skills/custom/<skill_name>/` 디렉터리 + skill registry |

모든 반영은 atomic write + 백업. 직전 활성 버전은 `rollback_ref`로 `PromotionRecord`에 연결.

### 7.3 버전과 alias

- `promotion_alias`는 조직에서 참조하는 논리 이름. 예: `finance_kb/ltv_definition`.
- 같은 alias에 새 아이템이 승격되면 기존 것은 자동으로 `superseded` 마킹되고 `deprecated`로 전이.
- 프롬프트와 스킬 로더는 alias를 기준으로 참조하여 롤백이 투명하게 이루어지도록 함.

### 7.4 롤백

- 롤백은 새로운 promotion이 아니라 `RollbackCommand`라는 별도 use case.
- 롤백 시 현재 활성 버전을 deprecate(reason=`manual`)하고 `rollback_ref`로 지정된 이전 버전을 `promoted`로 복원.
- 롤백 기록은 `PromotionRecord`에 `rollback=true` 플래그로 남긴다.

### 7.5 자동 승격 예외

§15의 매트릭스에 정의된 일부 low-risk 케이스(개인 모드, 비파괴, 소규모 KB)는 리뷰 없이 자동 승격이 가능하나, 이 경우에도 Eval gate는 반드시 통과해야 한다.

---

## 8. 재검증 스케줄

### 8.1 기본 스케줄

- promoted 아이템은 `RevalidationSchedule`에 자동 등록.
- 기본 주기: 타입별로 다르게 설정.
  - `ExtractedPattern`: 30일
  - `DomainKBEntry`: 60일
  - `CustomSkill`: 14일

### 8.2 재검증 절차

```
Scheduler tick
  ↓
monitored 상태 전이
  ↓
§05 Evaluation Harness에서 관련 Gold Task 실행
  ↓
score 산출
  ↓
compare(score, baseline * threshold)
  ├─ pass → updated_at 갱신, monitored → promoted 재진입
  └─ fail → deprecate(reason="regression")
```

### 8.3 성능 하락 임계값

- 기본 임계: `score >= baseline * 0.9` (10% 이상 하락 시 regression).
- 타입별로 재정의 가능:
  - `CustomSkill`: 더 엄격하게 `0.95`.
  - `ExtractedPattern`: 느슨하게 `0.85`.
- 연속 2회 실패 시에만 deprecate 트리거 (단일 노이즈 방어).

### 8.4 Online Scoring

재검증 외에도 실제 운영 중 다음 신호가 누적되면 즉시 재검증 큐로 이동.

- skill 실행 에러율 > 20% (최근 20회).
- KB 항목이 프롬프트에 포함되었을 때 사용자 thumbs_down 비율 > 30%.
- 패턴 적용 후 goal 달성률 급락 (baseline 대비 25% 이하).

---

## 9. Deprecation 경로

### 9.1 Deprecation 사유 코드

| 코드 | 의미 |
|------|------|
| `regression` | 재검증 실패 |
| `manual` | 리뷰어/관리자의 수동 폐기 |
| `conflict` | 새로 승격된 아이템과 충돌 |
| `superseded` | 같은 alias에 새 버전이 승격 |
| `policy` | 조직 정책 변경 (예: 특정 도메인 금지) |

### 9.2 처리 모드

- **Immediate.** 즉시 프롬프트/스킬 레지스트리에서 제거. `regression`, `policy`는 기본 immediate.
- **Grace period.** 기본 14일간 경고 플래그와 함께 유지, 이후 archived. `manual`, `superseded`, `conflict`는 기본 grace.

### 9.3 대체 링크

`DeprecationRecord.replacement_item_id`를 통해 대체 아이템을 명시. 프롬프트 로더는 deprecated 아이템이 참조될 때 대체 아이템을 안내한다.

### 9.4 감사 기록

- 모든 deprecation은 로그와 SQLite에 영속화.
- dashboard에서 "최근 30일 deprecation 건수/사유 분포"를 확인할 수 있다.

---

## 10. Conflict Resolution

### 10.1 충돌 감지 신호

1. **Semantic overlap.** §02 Semantic Memory 임베딩 기반 코사인 유사도 >= 0.85.
2. **Explicit contradiction.** LLM 기반 판정기가 "모순" 라벨 부여.
3. **Duplicate.** signature 일치 혹은 제목+본문 해시 동일.

### 10.2 감지 시점

- 자동 추출 직후 (`proposed` 생성 시).
- 리뷰어가 `modify`한 후.
- 다른 아이템이 `promoted`로 승격된 직후 (기존 promoted 아이템 대상 재스캔).

### 10.3 리뷰어 개입 트리거

- semantic overlap 0.85~0.95: 경고만, 리뷰어 판단.
- semantic overlap >=0.95: second-reviewer 강제.
- explicit contradiction: 반드시 해결 후에만 `approved` 가능.
- duplicate: 자동 merge 제안 + 리뷰어 확정.

### 10.4 동시 유효 허용 여부

- 원칙적으로 **동시 유효 금지**. 같은 alias 혹은 의미상 동일한 KB는 동시에 promoted 상태일 수 없다.
- 예외: 스코프가 명시적으로 다른 경우 (프로젝트 A 한정 vs 조직 전체). 이 경우 `scope` 필드로 구분하여 둘 다 유효 가능.
- 동시 유효가 아닌 경우, 새 아이템 승격 시 기존은 자동 `superseded` 처리.

### 10.5 ConflictAlert 라이프사이클

```
detected → (reviewer acts) → resolved
                ↘ unresolved (SLA 초과 시 governance_admin 에스컬레이션)
```

---

## 11. Evaluation 연동 (§05)

### 11.1 Gate 위치

- **Pre-promotion gate.** `approved → promoted` 사이.
- **Scheduled revalidation.** promoted 이후 주기적.
- **Online canary.** 선택적으로 일부 trace에만 적용하여 실제 환경 비교.

### 11.2 Gold Task Set 매핑

- 각 `LearningItem`은 관련 Gold Task 묶음(`task_bundle_id`)을 가진다.
- `ExtractedPattern`은 action 유사도 기반으로 자동 매핑.
- `DomainKBEntry`는 태그/도메인 일치로 매핑.
- `CustomSkill`은 skill의 input/output schema에 부합하는 task로 매핑.

### 11.3 회귀 점수 임계

```
gate_pass = (new_score >= baseline_score * promotion_threshold)
  where promotion_threshold = {
    pattern: 1.00,
    kb_entry: 1.00,
    custom_skill: 1.02    # 스킬은 베이스라인 이상의 개선을 요구
  }
```

- `new_score`는 승격 후보 아이템을 포함한 프롬프트/스킬 구성으로 실행한 Gold Task 결과.
- `baseline_score`는 현재 활성 구성의 최근 값.

### 11.4 Online Scoring과 피드백 루프

- 운영 trace 중 aggregate success metric을 `LearningItem`별로 분해하여 집계.
- §03 Verifier의 Review Verdict도 입력으로 사용.
- 결과는 Eval Harness 리포트에 포함되어 다음 재검증의 baseline 업데이트에 쓰인다.

---

## 12. Clean Architecture 매핑

| 레이어 | 컴포넌트 | 책임 |
|--------|----------|------|
| Domain | `LearningItem`, `ExtractedPattern`, `DomainKBEntry`, `CustomSkill`, `ReviewEvent`, `PromotionRecord`, `DeprecationRecord`, `ConflictAlert`, `LearningLifecycle` | 상태 머신, 불변 규칙, 값 객체 |
| Application | `LearningInbox`, `ReviewLearningItemUseCase`, `PromoteLearningItemUseCase`, `DeprecateLearningItemUseCase`, `CheckRegressionUseCase`, `DetectConflictUseCase`, 포트(`LearningReviewStore`, `OrganizationAssetWriter`, `EvaluationGate`, `ConflictDetector`) | 유스케이스 오케스트레이션 |
| Infrastructure | `SqliteLearningReviewStore`, `FileOrganizationAssetWriter`, `GoldTaskEvaluationGate`, `EmbeddingConflictDetector`, self_improve auto-extractor adapter | 포트 구현, 외부 I/O |
| Presentation | `@tool list_learning_inbox`, `@tool review_learning_item`, Electron `LearningInbox.tsx`, CLI `learning` subcommands | 입력/출력 변환 |

의존성 규칙: Domain은 어느 것도 import하지 않는다. Application은 포트 인터페이스만 참조. Infrastructure는 포트를 구현. self_improve의 자동 추출기는 infrastructure에 머무르며, application의 `ReceiveLearningProposalUseCase`를 통해 proposed 아이템을 생성한다.

---

## 13. SQLite 스키마 (migration v13)

```sql
-- v13_self_improvement_governance.sql

CREATE TABLE IF NOT EXISTS learning_items (
  item_id TEXT PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('pattern', 'kb_entry', 'custom_skill')),
  signature TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL,
  status TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  payload_json TEXT NOT NULL,                -- 하위 타입 고유 필드 직렬화
  source_run_ids TEXT NOT NULL,              -- JSON array
  project_id TEXT,
  extracted_at TEXT NOT NULL,
  extractor_version TEXT NOT NULL,
  current INTEGER NOT NULL DEFAULT 1,
  superseded_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX idx_learning_items_status ON learning_items(status);
CREATE INDEX idx_learning_items_signature ON learning_items(signature);
CREATE INDEX idx_learning_items_project ON learning_items(project_id);

CREATE TABLE IF NOT EXISTS review_events (
  event_id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL REFERENCES learning_items(item_id),
  reviewer TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('approve','modify','reject')),
  checklist_json TEXT NOT NULL,
  comment TEXT,
  diff_json TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_review_events_item ON review_events(item_id);

CREATE TABLE IF NOT EXISTS promotion_records (
  promotion_id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL REFERENCES learning_items(item_id),
  version INTEGER NOT NULL,
  promoted_by TEXT NOT NULL,
  approved_review_id TEXT REFERENCES review_events(event_id),
  eval_report_id TEXT,
  eval_score REAL,
  baseline_score REAL,
  promotion_alias TEXT,
  rollback_ref TEXT,
  is_rollback INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_promotion_item ON promotion_records(item_id);
CREATE INDEX idx_promotion_alias ON promotion_records(promotion_alias);

CREATE TABLE IF NOT EXISTS deprecation_records (
  deprecation_id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL REFERENCES learning_items(item_id),
  reason_code TEXT NOT NULL,
  reason_text TEXT,
  replacement_item_id TEXT,
  grace_period_days INTEGER NOT NULL DEFAULT 14,
  effective_from TEXT NOT NULL,
  archived_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_deprecation_item ON deprecation_records(item_id);

CREATE TABLE IF NOT EXISTS conflict_alerts (
  alert_id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL REFERENCES learning_items(item_id),
  detected_at TEXT NOT NULL,
  conflicts_json TEXT NOT NULL,
  resolved INTEGER NOT NULL DEFAULT 0,
  resolution_note TEXT
);
CREATE INDEX idx_conflict_item ON conflict_alerts(item_id);

CREATE TABLE IF NOT EXISTS revalidation_schedule (
  item_id TEXT PRIMARY KEY REFERENCES learning_items(item_id),
  next_due_at TEXT NOT NULL,
  last_run_at TEXT,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  baseline_score REAL
);
CREATE INDEX idx_reval_due ON revalidation_schedule(next_due_at);
```

마이그레이션 스크립트는 `src/infrastructure/persistence/migrations/v13_self_improvement_governance.py`에 위치.

---

## 14. 주요 도구 / 유스케이스

### 14.1 @tool `list_learning_inbox`

```python
# src/infrastructure/tools/learning/list_learning_inbox.py

@tool("list_learning_inbox")
def list_learning_inbox(
    status: Optional[list[str]] = None,
    type: Optional[list[str]] = None,
    project_id: Optional[str] = None,
    since: Optional[str] = None,
    priority: Optional[str] = None,
    has_conflict: Optional[bool] = None,
    assignee: Optional[str] = None,
    limit: int = 50,
) -> list[LearningInboxItemDTO]:
    ...
```

반환 DTO는 `item_id`, 제목, 요약, priority, 상태, conflict 여부, 추출 프로젝트, 대기 일수 포함.

### 14.2 @tool `review_learning_item`

```python
@tool("review_learning_item")
def review_learning_item(
    item_id: str,
    decision: Literal["approve","modify","reject"],
    checklist: dict[str, bool],
    comment: str,
    modifications: Optional[dict] = None,
) -> ReviewEventDTO:
    ...
```

- `approve` 시 내부적으로 `PromoteLearningItemUseCase`를 큐에 등록.
- `modify` 시 `modifications` dict가 허용된 필드(title/summary/payload 일부)에 적용.
- 권한 확인은 Authority Mode와 연동.

### 14.3 `PromoteLearningItemUseCase`

내부 use case. 자동 실행되며 다음을 수행.

```
1. item 상태 approved 검증
2. ConflictDetector.rescan(item) 수행, 미해결 충돌 시 실패
3. EvaluationGate.run(item) 호출
4. threshold 미달 시 item 상태 rejected, reason 기록
5. 통과 시
   a. OrganizationAssetWriter.write(item)
   b. PromotionRecord 저장
   c. item 상태 promoted
   d. 기존 alias 보유 아이템 superseded/deprecated
   e. RevalidationSchedule에 등록
```

### 14.4 `DeprecateLearningItemUseCase`

```python
def deprecate(
    item_id: str,
    reason_code: str,
    reason_text: str,
    replacement_item_id: Optional[str] = None,
    grace_period_days: int = 14,
    actor: str = "system",
) -> DeprecationRecord
```

권한: `manual`/`policy`는 `governance_admin`, 나머지는 system 자동.

### 14.5 `CheckRegressionUseCase`

스케줄러가 호출. monitored 상태로 전이, Eval gate 실행, 실패 시 deprecate.

### 14.6 추가 tool (보조)

- `@tool get_learning_item` — 상세 조회.
- `@tool list_promotions` — 최근 승격 이력.
- `@tool rollback_promotion` — 관리자 전용.
- `@tool list_deprecations` — deprecation 이력.
- `@tool resolve_conflict_alert` — 충돌 해결 기록.

---

## 15. 자동화 vs 사람 개입 매트릭스

§04 Authority Mode의 단계(advisor/assistant/collaborator/executor/autopilot/custodian)와 결합하여 정책을 결정한다.

| 시나리오 | Authority Mode | 리뷰 요구 | Eval gate | 비고 |
|----------|----------------|-----------|-----------|------|
| Personal mode + ExtractedPattern, scope=session | autopilot | 자동 승격 허용 | 필수 | 자동 승격 후 monitored 등록 |
| Personal mode + DomainKBEntry, scope=organization | executor 이상 | 사람 리뷰 필수 | 필수 | alias 충돌 방지 |
| Enterprise mode + ExtractedPattern | collaborator 이상 | 사람 리뷰 필수 | 필수 | second-reviewer 권장 |
| Enterprise mode + CustomSkill (non-destructive) | collaborator 이상 | 사람 리뷰 필수 | 필수 (threshold 1.02) | |
| Enterprise mode + CustomSkill (destructive tools) | executor 이상 | 사람 리뷰 2인 필수 | 필수 | second-reviewer 강제 |
| Any mode + ConflictAlert unresolved | — | 리뷰 필수, 해결 없이 승격 불가 | — | |
| Any mode + Deprecation(regression) | — | 자동 | — | 알림만 |
| Any mode + Deprecation(policy/manual) | custodian/admin | 사람 필수 | — | |
| Rollback | executor 이상 | 사람 필수 | — | 이전 버전 무결성 검증 |

자동 승격 허용 케이스라도 감사 기록(`PromotionRecord.promoted_by = "system"`)은 동일하게 남는다.

---

## 16. Prompt 통합

### 16.1 활성 지식 주입

- `PromptComposer`는 세션 시작 시 `promoted` 상태의 아이템을 alias 기준으로 로드.
- 스코프 필터: `organization` / `project:<id>` / `user:<id>`로 구분.
- 로딩 순서: 조직 → 프로젝트 → 사용자 (뒤쪽이 우선).

### 16.2 Deprecated 가드

- deprecated 아이템은 프롬프트에 주입되지 않는다.
- grace period 중 deprecated 아이템이 이미 로드된 세션에는 경고 메타데이터 삽입 ("이 지식은 곧 폐기됩니다. 대체: ...").
- skill 레지스트리는 deprecated 스킬 호출 시 `ToolDeprecatedError`를 반환하고, grace 중이면 경고 로그 후 실행.

### 16.3 Conflict 가드

- 같은 요청에 충돌하는 두 아이템이 동시에 로드 예정이면 PromptComposer가 중단하고 governance 채널로 알림. (10.4의 동시 유효 금지 규칙 반영)

### 16.4 감사 주입

- 프롬프트에는 사용된 아이템의 `item_id`와 `version`이 메타데이터로 포함되어, 실행 trace와 학습 아이템 사이의 추적성을 보장.

---

## 17. UX — Electron LearningInbox

### 17.1 화면 구성

- **왼쪽 패널.** 필터(상태, 타입, 프로젝트, priority, conflict), 배정된 티켓 목록.
- **중앙.** 선택된 아이템의 상세 (title, summary, evidence, source, conflicts).
- **오른쪽.** diff 뷰 (modify 모드 시), 체크리스트, decision 버튼.

### 17.2 Diff 뷰

- `DomainKBEntry` 수정 시 기존 값과의 textual diff.
- `ExtractedPattern`은 action sequence diff.
- `CustomSkill`은 skill body markdown diff + required tools 변경 하이라이트.

### 17.3 승인 UI

- 체크리스트 전체 true가 아닌 경우에도 approve 가능(필수 항목만 강제)하되 warning 배너 표시.
- second-reviewer가 필요한 경우 "1차 승인 완료. 2차 리뷰어 대기" 상태로 표시.

### 17.4 알림

- 신규 proposed 도착, SLA 임박, conflict 발생, regression 감지 시 토스트 + 배지.
- Electron tray 아이콘에 미처리 high priority 카운트.

### 17.5 승격 기록 타임라인

- 각 아이템에 대한 proposed → approved → promoted → monitored → deprecated 의 타임라인 시각화.
- 버전별 diff, PromotionRecord 링크, Eval report 링크 제공.

### 17.6 CLI 대응

- `ds learning list`, `ds learning show <id>`, `ds learning review <id> --approve`, `ds learning rollback <promotion_id>` 등.
- Telegram 인터페이스에서는 요약 카드와 approve/reject 버튼 제공.

---

## 18. 기존 self_improve 모듈 확장

### 18.1 변경 사항

1. 자동 추출기가 산출물을 직접 조직 자산(`domain_kb.json`, `skills/custom/`)에 반영하던 경로를 **완전히 차단**한다.
2. 대신 `SubmitLearningProposalPort`를 호출하여 `proposed` 상태의 `LearningItem`만 생성한다.
3. 기존 `self_improve/extractors/*` 파일의 반환 타입을 `LearningItem`으로 맞춘다.
4. 상태 필드가 없는 레거시 레코드는 마이그레이션 시 `proposed`로 주입 후 리뷰 큐에 일괄 적재.

### 18.2 신규 파일

```
src/self_improve/
├── extractors/               # 기존 유지, 반환 타입만 변경
├── learning_inbox.py         # application 포트 호출 얇은 래퍼
├── proposal_submitter.py     # SubmitLearningProposalPort 어댑터
└── conflict_detector.py      # infrastructure 어댑터
```

### 18.3 호환성

- 기존 자동 추출 주기/스케줄러는 유지.
- 기존 `domain_kb.json`에 이미 존재하는 항목은 일괄 import되어 `promoted` 상태의 legacy PromotionRecord(promoted_by=`legacy_import`)로 생성. 이후 재검증 스케줄에 편입.

### 18.4 직접 적용 경로 차단 검증

- `ruff` custom rule 또는 import guard 테스트로 `self_improve`에서 `domain_kb.json` 파일을 직접 쓰는 코드를 금지.
- 레이어 테스트: infrastructure → application 포트를 통하지 않은 작성 호출을 탐지.

---

## 19. 구현 Phases (TDD)

우선순위는 로드맵의 P3. 전체 Phase는 3개로 구성.

### Phase 1: 기초 Inbox + proposed 상태

**목표.** 자동 추출 산출물이 조직 자산에 직접 반영되지 않고 Learning Inbox에 proposed로 들어가도록 전환.

- RED
  - `LearningItem` 도메인 모델 단위 테스트.
  - `SubmitLearningProposalUseCase` 포트 테스트.
  - self_improve 자동 추출기 integration 테스트: 추출 시 `domain_kb.json`이 변경되지 않고 `learning_items` 테이블에 proposed가 등록되는지.
  - `list_learning_inbox` tool 테스트.
- GREEN
  - migration v13 작성.
  - `SqliteLearningReviewStore` 구현.
  - `SubmitLearningProposalUseCase` + port 정의.
  - self_improve extractor 반환 타입 교체.
  - `list_learning_inbox` 및 `get_learning_item` tool.
  - legacy import 마이그레이션.
- REFACTOR
  - 직접 쓰기 경로 제거, import guard 테스트 추가.

### Phase 2: 승격 플로우 + Eval gate

**목표.** 리뷰어의 approve로 Eval gate를 거쳐 promoted 상태로 전이되는 파이프라인.

- RED
  - `ReviewLearningItemUseCase` 테스트 (approve/modify/reject 전이).
  - `PromoteLearningItemUseCase` 테스트 (gate pass/fail 분기).
  - `ConflictDetector` 테스트.
  - alias 충돌 시 기존 아이템 superseded 처리 테스트.
  - `review_learning_item` tool 테스트.
  - Electron LearningInbox 리뷰 UI e2e 테스트 (mocked backend).
- GREEN
  - `ReviewEvent`, `PromotionRecord`, `ConflictAlert` 영속화.
  - `EvaluationGate` 포트 및 `GoldTaskEvaluationGate` 구현 (§05 연동).
  - `OrganizationAssetWriter` 구현.
  - `review_learning_item`, `rollback_promotion`, `resolve_conflict_alert` tool.
  - Electron LearningInbox 컴포넌트.
- REFACTOR
  - 승격 파이프라인 단계 분리 재정비, observability 로그 추가.

### Phase 3: 재검증 + Deprecation

**목표.** promoted 아이템의 주기적 재검증과 regression 기반 자동 deprecation, grace period 처리.

- RED
  - `CheckRegressionUseCase` 테스트.
  - `DeprecateLearningItemUseCase` 테스트 (immediate/grace 분기).
  - `RevalidationScheduler` 주기 테스트.
  - Online signal 임계 초과 시 재검증 큐 진입 테스트.
  - 프롬프트 통합 테스트: deprecated 아이템이 프롬프트에 포함되지 않음.
- GREEN
  - `RevalidationScheduler` 구현 (APScheduler 또는 기존 스케줄러 확장).
  - `DeprecateLearningItemUseCase`, `DeprecationRecord` 저장.
  - PromptComposer에 deprecated 가드 삽입.
  - `list_deprecations` tool, Electron 알림 UI.
- REFACTOR
  - scheduler/eval 의존성 모듈화, 통합 시나리오 테스트.

---

## 20. 테스트 전략

### 20.1 상태 전이 테스트

- 각 허용 전이에 대해 happy path + 금지 전이에 대해 `IllegalStateTransition` 예외 검증.
- property-based 테스트로 임의 이벤트 시퀀스에서 상태 머신이 항상 유효 상태에 머무르는지 확인.

### 20.2 Conflict Detection 정확도 테스트

- 골든 데이터셋: (A, B, label) 트리플로 semantic_overlap 임계 검증.
- 반복 실험으로 false positive/negative 비율 측정. 목표: FP < 5%, FN < 10%.

### 20.3 승격 후 회귀 시나리오

- 승격된 아이템이 Gold Task에서 baseline 대비 성능 하락을 시뮬레이션 → 2회 연속 실패 시 deprecated 전이 검증.
- regression이 아닌 일시적 노이즈(1회 실패)에는 deprecate되지 않는지 검증.

### 20.4 Rollback 테스트

- promoted A → promoted B (A superseded) → rollback → A가 다시 promoted, B는 deprecated.
- 조직 자산 파일의 내용이 A 시점으로 복원되는지 검증.

### 20.5 보안/권한 테스트

- `reviewer`가 아닌 사용자가 `review_learning_item` 호출 시 거부.
- destructive tool 포함 스킬에 대해 second-reviewer 없이 승격 시도 시 거부.

### 20.6 통합 테스트

- self_improve 자동 추출 → proposed → 리뷰 승인 → Eval gate → promoted → 재검증 → deprecate 흐름 end-to-end.
- 전체 사이클 시간, 이벤트 카운트 메트릭 수집.

### 20.7 성능 테스트

- Inbox 10,000개 아이템 기준 필터/페이지네이션 응답 < 500ms.
- ConflictDetector 1회 호출 < 2s (embedding 재사용 시).

### 20.8 Coverage 목표

- Domain: 95% 이상.
- Application: 90% 이상.
- Infrastructure: 80% 이상.
- Presentation (UI): 주요 flow 위주 e2e.

---

## 21. 의존성 및 통합 지점

| 의존성 | 내용 |
|--------|------|
| 기존 `src/self_improve` | 자동 추출 로직 유지, 산출물 라우팅만 변경 |
| §05 Evaluation Harness | Eval gate, Gold Task, 재검증 스케줄 |
| §02 Semantic Memory | Conflict detection의 semantic overlap 계산 |
| §04 MissionPack/Authority Mode | 자동화 매트릭스, 리뷰어 권한 판단 |
| §03 Verifier Layer | Online signal 입력원 |
| §01 TaskContract | LearningItem.source 추적과 taskcontract 연결 |
| PromptComposer | 활성/deprecated 지식 주입 가드 |
| SQLite 저장소 | migration v13, 기존 DB 파일에 추가 |
| Electron UI | 신규 LearningInbox 컴포넌트, 알림 센터 |
| Telegram/CLI | 요약 카드 및 승인 명령 |

외부 라이브러리: `apscheduler`(스케줄러), 기존 embedding 스택(semantic 유사도), 기존 migration runner.

---

## 22. 성공 기준 (DoD)

### 22.1 기능적 완성도

- [ ] self_improve 자동 추출이 조직 자산을 직접 갱신하지 않는다(테스트로 보장).
- [ ] proposed → under_review → approved/modified/rejected → promoted → monitored → deprecated 상태 머신이 모두 구현된다.
- [ ] Eval gate 미통과 시 promoted로 전이되지 않는다.
- [ ] deprecated 아이템은 프롬프트/스킬 로더에 노출되지 않는다.

### 22.2 정량 지표

| 지표 | 목표 |
|------|------|
| 리뷰 리드타임 (proposed → decision) | 중앙값 <= 3일 |
| 승격률 (approved 중 eval gate 통과 비율) | >= 75% |
| 자동 deprecation 정확도 (regression 감지) | precision >= 85%, recall >= 80% |
| Conflict detection FP | < 5% |
| Rollback 성공률 | 100% (조직 자산 무결성 유지) |
| Inbox 처리 SLA 준수율 | >= 95% |

### 22.3 감사 가능성

- 모든 상태 전이가 SQLite에 기록되고 재구성 가능.
- 승격된 아이템은 PromotionRecord → ReviewEvent → LearningItem → source runs 로 완전한 감사 체인을 형성.

### 22.4 운영 지표

- Learning Inbox 대시보드에서 backlog, priority 분포, SLA 위반 건수 실시간 확인 가능.

---

## 23. 리스크 및 롤백

| 리스크 | 확률 | 영향 | 대응 |
|--------|------|------|------|
| 리뷰 큐 적체 | 중 | 중 | 자동 우선순위, SLA 알림, auto-batch, reviewer load cap |
| 리뷰어 번아웃 | 중 | 중 | 배정 분산, low priority 자동 만료 옵션, 승인 매크로 |
| 승격된 아이템이 사후 품질 문제 유발 | 중 | 높 | 재검증, 롤백 경로 상시 유지, online signal 감시 |
| Eval gate 자체의 신뢰도 부족 | 중 | 높 | Gold Task 지속 업데이트, threshold 보정 주기 |
| Conflict 오탐으로 정상 승격 차단 | 중 | 중 | FP 임계 모니터링, 리뷰어 override 경로 |
| 레거시 import로 잘못된 항목이 promoted로 자리잡음 | 중 | 중 | 초기 재검증 주기 단축, spot-check 리뷰 배치 |
| Authority Mode 연동 오류로 권한 우회 | 낮 | 높 | 권한 테스트 자동화, 주기 audit |
| 자동 deprecation이 운영 중요 아이템을 제거 | 낮 | 높 | 연속 2회 실패 요구, grace 기본 14일, 알림 필수 |

### 23.1 롤백 전략

- **Phase별 롤백.** 각 Phase는 feature flag(`SELF_IMPROVE_GOVERNANCE_V1`)로 제어. 문제 발생 시 기존 자동 적용 경로로 임시 복귀 가능.
- **개별 아이템 롤백.** `rollback_promotion` tool로 alias 단위 복원.
- **일괄 롤백.** migration v13은 역방향 스크립트를 포함하여 테이블 유지 + 상태 필드 무시 모드 제공.
- **조직 자산 백업.** OrganizationAssetWriter는 매 승격 전 현재 자산 스냅샷을 저장하여 즉시 복원 가능.

---

## 24. Open Questions

1. **리뷰어 풀 정의.** 조직 규모에 따라 reviewer 역할을 어떻게 자동 배정할 것인가? 초기에는 설정 파일 기반으로 두고, 향후 OIDC 그룹과 매핑할지 결정 필요.
2. **동시 유효 예외의 경계.** 프로젝트 스코프와 조직 스코프가 의미상 동일한 KB에 대해 서로 다른 값을 가지는 경우 허용 조건을 어디까지 완화할 것인가.
3. **Eval gate의 비용.** 승격마다 Gold Task 전체 실행은 비용이 크다. incremental 평가(관련 subset만)로 단축하되 신뢰도 확보 방안.
4. **개인 모드와 기업 모드의 동일 DB 공유 여부.** 개인 사용자가 조직 가입 시 기존 promoted personal 아이템을 어떻게 이관/격리할 것인가.
5. **Deprecation 예외 처리.** policy 기반 즉시 폐기 시에도 최소 공지 기간을 강제해야 하는가.
6. **멀티 리뷰어 의견 충돌.** 1차 approve, 2차 reject인 경우의 자동 처리 규칙. 현재 초안은 "reject 우선"이나 검토 필요.
7. **LLM 기반 자동 리뷰 보조.** 초안 수준의 체크리스트 자동 채움을 도입할지, 도입한다면 bias 방지 방안.
8. **KB 스코프와 §02 Semantic Memory의 통합 깊이.** KB entry는 semantic memory와 사실상 동일 저장소로 합칠 수 있는가, 분리 유지할 것인가.
9. **Skill 실행 사이드이펙트의 재검증 비용.** destructive skill 재검증을 dry-run으로 강제하는 표준화 필요.
10. **메타 학습.** deprecation 사유 분포 자체를 입력으로 하여 추출기 하이퍼파라미터를 조정하는 피드백 루프의 도입 여부.

---
