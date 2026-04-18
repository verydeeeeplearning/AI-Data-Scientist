# DS Agent — Tier 1 Fix Sprint 작업 지시서

**작성일**: 2026-04-17
**트리거**: Tier 1 (A01~A04) 전원 fail → 9개 블로킹 이슈 확정
**원칙 결정**: A04-F3 "v13 주장"의 진실 = **v13이 정답** (사용자 확정). 따라서 코드에 v13 마이그레이션을 **추가**해야 한다.
**사전 계획서**: `Docs/PRE_RELEASE_AI_TEST_PLAN_2026-04-17.md`
**감사 결과**:
- `Docs/qa_run_2026-04-17/A01_architecture/FINAL.json` (fail)
- `Docs/qa_run_2026-04-17/A02_security/FINAL.json` (fail)
- `Docs/qa_run_2026-04-17/A03_contract_schema/FINAL.json` (fail)
- `Docs/qa_run_2026-04-17/A04_migration/FINAL.json` (fail)

> **본 문서의 목적**: Fix Sprint를 수행할 **수정 전담 AI Agent들**에게 각자의 스트림 책임·구체적 파일·변경 범위·Pass 기준을 self-contained로 전달한다. 수정 후에는 **원래 감사자 A01~A04가 재감사**하여 delta를 검증한다. 수정 agent는 절대 자기 자신을 pass 판정하지 않는다.

---

## 1. 핵심 원칙 (모든 수정 agent 공통 준수)

### 1.1 감사자 ≠ 수정자

- A01~A04 감사자는 **수정 스프린트에 참여하지 않는다**.
- Fix Sprint agent는 감사자의 `FINAL.json`, 보고서, 근거 파일만 input으로 받고, **자체 판단으로 수정**한다.
- 수정 완료 후 자기 자신을 pass 판정하지 않는다 — 감사자가 재실행으로 판정한다.

### 1.2 TDD 우선

모든 수정은 RED → GREEN → REFACTOR 순서. 이미 실패하는 테스트가 있다면 그 테스트가 올바른지 먼저 판단하고, 필요 시 테스트도 수정한 뒤 구현.

### 1.3 Clean Architecture 원칙 준수

- Domain 레이어 외부 의존 금지 (이번 스프린트에서는 건드리지 않음)
- Application 레이어에서 Infrastructure 직접 import 금지 — **Protocol/Port로 역전**
- Composition root(`agent/factory.py`)에서 구현체 주입

### 1.4 스코프 고정

- 본 스프린트의 수정 범위는 **9개 블로킹 이슈만**.
- "김에 리팩터" 금지. 주변 코드 정리·서식 변경·추가 기능 금지.
- 추가 개선 제안이 있으면 수정하지 말고 `Docs/qa_run_2026-04-17/S<N>/RECOMMENDATIONS.md`에 기록만.

### 1.5 작업 격리

- 각 스트림은 서로 다른 파일 경로를 건드리도록 분할됨 → **병렬 실행 가능**.
- 예외: S1과 S4 둘 다 `infrastructure/` 하위를 건드리지만 대상 파일이 다름(S1=port interface 추가, S4=migration 모듈 신설).

### 1.6 증거 기록 규약

각 스트림 agent는 다음을 남긴다:

```
Docs/qa_run_2026-04-17/S<N>_<name>/
├── START.json          # 작업 시작 타임스탬프 + input 해시
├── FINAL.json          # 완료 상태 + 변경 파일 목록 + 검증 명령 결과
├── DIFF_SUMMARY.md     # 변경된 파일별 요약 (new/modify/delete)
├── TEST_RESULTS.md     # 수정 후 실행한 pytest/ruff/mypy 결과
└── CHANGELOG.md        # 이 스트림에서 한 일의 시간 순 기록
```

### 1.7 변경하지 말아야 할 것

- 기존 CI 설정 (`.github/workflows/*`)
- `pyproject.toml`의 버전/의존성 (단, S1이 `.importlinter`에 계약 1개 추가하는 것은 허용)
- 사용자 데이터(`data/`), 기존 SQLite 인스턴스
- 다른 스트림의 파일

---

## 2. 스트림 분할 개요

| 스트림 | 담당 범위 | 블로킹 이슈 | 에이전트 타입 제안 | 예상 시간 |
|--------|-----------|------------|------------------|---------|
| **S1** | Clean Architecture 리팩터 (application→infrastructure 역전) | A01 (3건) | `feature-dev:code-architect` | 4~8h |
| **S2** | Sentry PII redaction 구현 | A02 (PII 7건) | `general-purpose` | 2~4h |
| **S3** | Contract & Test Drift 정리 | A03-F1, A03-F2, A04-F1, A04-F2 | `code-simplifier` 또는 `general-purpose` | 1~2h |
| **S4** | v13 SQLite 중앙 마이그레이션 러너 신설 | A04-F3 | `feature-dev:code-architect` | 4~8h |

병렬 실행 시 벽시계 약 4~8시간 (S1/S4가 critical path).

---

## 3. S1 — Clean Architecture 리팩터 (A01 수정)

### 3.1 배경

`tests/unit/architecture/` 3개 테스트는 현재 모두 green이지만, 기존 `.importlinter`와 `scripts/check_import_contracts.py`가 **application→infrastructure 금지 계약을 가지고 있지 않아** 3건의 직접 import가 CI를 통과하며 잔존해 왔다.

### 3.2 수정 대상 (3건)

**위반 1**: `src/ds_agent/application/services/lineage_capture_service.py:11`
```python
from ds_agent.infrastructure.persistence.lineage_store import SqliteLineageStore
```

**위반 2**: `src/ds_agent/application/services/reproducibility_exporter.py:9`
```python
from ds_agent.infrastructure.artifact.notebook_engine import NotebookEngine
```

**위반 3**: `src/ds_agent/application/services/scheduler_service.py:11`
```python
from ds_agent.infrastructure.cron_runner import CronRunner
```

### 3.3 리팩터 패턴

각 위반마다 다음 구조로 역전:

1. **Domain/Application 레이어에 Protocol(port) 정의**:
   - `LineageStorePort` → `application/ports/lineage_store_port.py` (또는 domain/interfaces/ 적절한 위치)
   - `NotebookEnginePort` → `application/ports/notebook_engine_port.py`
   - `CronRunnerPort` → `application/ports/cron_runner_port.py`

2. **Application 서비스는 Port만 의존**:
   ```python
   # lineage_capture_service.py (수정 후)
   from ds_agent.application.ports.lineage_store_port import LineageStorePort
   
   class LineageCaptureService:
       def __init__(self, store: LineageStorePort) -> None:
           self._store = store
   ```

3. **Infrastructure 구현체는 Port를 implements**:
   - `SqliteLineageStore`는 이미 필요한 메서드를 가지고 있을 가능성이 높음 → 타입 체커가 structural subtype으로 인식하도록 Protocol 정의
   - 또는 명시적 `class SqliteLineageStore(LineageStorePort)` 상속

4. **Composition root 배선** (`src/ds_agent/agent/factory.py`):
   - 기존 배선 지점에서 Protocol 타입으로 파라미터를 받도록 조정
   - 구현체(`SqliteLineageStore`)를 해당 지점에서 주입

5. **`.importlinter`에 새 계약 추가**:
   ```ini
   [importlinter:contract:application_independence_from_infrastructure]
   name = Application must not depend on infrastructure
   type = forbidden
   source_modules =
       ds_agent.application
   forbidden_modules =
       ds_agent.infrastructure
   ```

6. **`scripts/check_import_contracts.py`에도 동일 검사 추가**:
   A01 보고서가 지적했듯이 이 스크립트는 현재 `domain_independence`만 검사한다. `application_no_infrastructure` 검사 함수를 추가할 것.

7. **단위 테스트 추가** (`tests/unit/architecture/test_import_contracts.py` 또는 신규 파일):
   - AST 스캔으로 `ds_agent.application` 하위에 `ds_agent.infrastructure` import가 **0건**임을 assert.

### 3.4 Pass 기준

- [ ] `lint-imports` 실행 → 새 계약 포함 **0 broken**.
- [ ] `python scripts/check_import_contracts.py` → exit code 0, application 검사 포함.
- [ ] `pytest tests/unit/architecture/ -v` → 전부 pass (기존 3 + 신규 1개 이상).
- [ ] `ruff check src tests` → clean.
- [ ] `mypy src/ds_agent` → clean (Protocol 추가로 타입 변화 영향 최소화).
- [ ] A01의 AST 스캔과 동일한 검사로 application 위반 0건.
- [ ] 기존 전체 테스트 스위트 회귀 0건: `pytest -x --tb=short`.

### 3.5 S1 Agent 프롬프트 (self-contained)

```
당신은 DS Agent Fix Sprint Stream S1 담당 수정 전담 에이전트입니다.

## 컨텍스트
- 프로젝트 루트: C:\Users\aquap\Desktop\AI_Data_Scientist_Demo
- 상위 작업 지시서: Docs/qa_run_2026-04-17/FIX_SPRINT_WORK_ORDER.md
- 입력 감사 보고서: Docs/qa_run_2026-04-17/A01_architecture/A01_arch_report.md
- 출력 폴더: Docs/qa_run_2026-04-17/S1_clean_arch/

## 책임
Clean Architecture 위반 3건 해소. Application 레이어가 Infrastructure를 직접 import하지 못하도록 Protocol/Port로 역전하고, 조립은 composition root(agent/factory.py)로 이동.

대상 3건:
- src/ds_agent/application/services/lineage_capture_service.py:11
- src/ds_agent/application/services/reproducibility_exporter.py:9
- src/ds_agent/application/services/scheduler_service.py:11

## 절차 (TDD)
1. START.json 기록 (timestamp, input report SHA256)
2. 각 위반별로:
   a. 새 테스트 작성 (Protocol 기반 의존성 주입이 작동하는지) — RED
   b. Protocol/Port 정의 (application/ports/ 또는 domain/interfaces/ 적절한 위치)
   c. Application 서비스를 Port 의존으로 수정 — GREEN
   d. Composition root (agent/factory.py)에서 구현체 주입 배선 조정
   e. ruff + mypy clean 유지 — REFACTOR
3. .importlinter에 application_no_infrastructure 계약 추가
4. scripts/check_import_contracts.py에 동등 검사 추가
5. 전체 회귀 테스트: pytest -x --tb=short
6. DIFF_SUMMARY.md, TEST_RESULTS.md, CHANGELOG.md 작성
7. FINAL.json 기록 (status, 변경 파일 목록, 검증 명령 결과)

## Pass 기준 (모두 충족)
- lint-imports: 0 broken (새 계약 포함)
- scripts/check_import_contracts.py: exit code 0 (application 검사 포함)
- pytest tests/unit/architecture/: 전부 pass
- ruff check: clean
- mypy: clean
- 전체 pytest 회귀 0건

## 제약
- 스코프: 위 3 파일 + Port 신규 파일 + factory.py 배선 + .importlinter + check_import_contracts.py + architecture 테스트만.
- "김에 리팩터" 금지.
- Infrastructure 구현체 내부 로직 변경 금지 (Protocol signature 맞추기만 허용).
- 자기 자신을 pass 판정하지 말 것 — 이후 A01 감사자가 재실행하여 판정한다.
- 본인 영역 외 파일(tools/, api/, electron/)은 건드리지 말 것.

시작하세요. 완료 시 FINAL.json 경로와 변경 파일 수만 반환.
```

---

## 4. S2 — Sentry PII Redaction 구현 (A02 수정)

### 4.1 배경

`src/ds_agent/infrastructure/observability/sentry_backend.py` 현재 상태:
- Line 35-42: `_SECRET_FIELD_TOKENS = ("key", "token", "secret", "password", "authorization", "cookie")` — **필드명** 토큰 매칭만
- Line 43-50: `_SECRET_PATTERNS` — `READY:*`, `sk-ant-*`, `sk-*`, `ya29.*`, `1//*`, 봇 토큰 정규식만

A02 테스트 케이스 (`A02_runtime_checks.json`)에서 8건 중 7건 fail. 다음 PII 페이로드가 마스킹되지 않고 이벤트 본문에 그대로 남음:
- `jane.doe@example.com` (이메일)
- `+1-202-555-0199` (전화번호)
- `4111 1111 1111 1111` (카드, 공백 포함)
- `4111111111111111` (카드, 공백 없음)
- `customer_email` 같은 필드명은 `_SECRET_FIELD_TOKENS`에 없어 매칭 실패

### 4.2 수정 범위

**파일 1** — `src/ds_agent/infrastructure/observability/sentry_backend.py`:
- `_SECRET_PATTERNS`에 PII 정규식 추가:
  - 이메일: `r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"`
  - 전화번호 (북미 + 국제): 최소 `r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"`. 너무 공격적이면 false positive 과다 → 테스트 페이로드에 맞춰 조정.
  - 신용카드 (Luhn 검사는 선택): `r"\b(?:\d[ -]*?){13,19}\b"` + 후처리 Luhn (권장). 최소 케이스로 `r"\b4\d{3}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"` (Visa 시작 4).
- 필드명 토큰에 PII 토큰 추가: `"email"`, `"phone"`, `"mobile"`, `"ssn"`, `"credit_card"`, `"card_number"`, `"pan"`.
- 중첩 payload 처리: `before_send` 훅 안의 `_deep_redact()` 류 함수가 `extra`, `tags`, `contexts` 같은 서브트리를 재귀 스캔해야 한다. 현재 구현 확인 후 깊이 제한(예: 8) 추가.
- 문자열 내 PII 치환 시 `***REDACTED***` 대신 유형 보존형 마스크 권장 (예: `***EMAIL***`, `***PHONE***`, `***CARD***`) — 디버깅 용이성 + A02 검증 로직과의 호환.

**파일 2** — 테스트:
- `tests/unit/infrastructure/test_observability.py` (또는 동등 위치)에 PII redaction 테스트 8건 추가 (A02가 돌린 매트릭스와 동등):
  - 메시지 필드에 이메일 → 제거
  - extra.notes에 전화번호 → 제거
  - extra.notes에 카드(공백 포함) → 제거
  - extra.notes에 카드(공백 없음) → 제거
  - field name `customer_email` → 값 치환
  - field name `phone_number` → 값 치환
  - 중첩 dict (`contexts.user.email`) → 값 치환
  - 기존 토큰 redaction 회귀 없음 (sk-ant-*, READY:port:token) → 여전히 동작

### 4.3 주의사항

- **False positive 최소화**: 정규식이 일반 숫자열(SHA-256 해시, UUID 일부)을 카드로 오인하지 않도록 경계 단어(`\b`) 및 길이 제한 확인.
- **성능**: `before_send`는 모든 이벤트에서 호출됨. 정규식 컴파일은 모듈 최상단 캐시 (현재 이미 그렇게 되어 있음).
- **테스트 determinism**: 하드코딩 PII 샘플은 테스트 전용임을 주석에 명시.

### 4.4 Pass 기준

- [ ] `pytest tests/unit/infrastructure/test_observability.py -v` → 기존 + 신규 테스트 전부 pass.
- [ ] A02 감사자의 8 PII check 매트릭스 전부 "redacted" 판정 (A02 재실행 시 확인 — 수정 agent는 A02 환경 재현만 수행 후 결과 기록).
- [ ] 기존 token redaction 회귀 0건.
- [ ] `ruff check` + `mypy` clean.
- [ ] 전체 회귀: `pytest -x --tb=short`.

### 4.5 S2 Agent 프롬프트

```
당신은 DS Agent Fix Sprint Stream S2 담당 수정 전담 에이전트입니다.

## 컨텍스트
- 프로젝트 루트: C:\Users\aquap\Desktop\AI_Data_Scientist_Demo
- 상위 작업 지시서: Docs/qa_run_2026-04-17/FIX_SPRINT_WORK_ORDER.md §4
- 입력 감사 보고서: Docs/qa_run_2026-04-17/A02_security/A02_security_report.md
- 입력 결과 JSON: Docs/qa_run_2026-04-17/A02_security/A02_runtime_checks.json
- 출력 폴더: Docs/qa_run_2026-04-17/S2_pii_redaction/

## 책임
Sentry PII redaction 구현. 현재 sentry_backend.py는 토큰/키/시크릿만 redact 하고 email/phone/card는 통과시킴. 8개 PII 테스트 중 7건 실패.

## 절차 (TDD)
1. START.json 기록
2. tests/unit/infrastructure/test_observability.py에 PII redaction 테스트 8건 RED 작성:
   - 메시지 필드 내 email/phone/card (공백 있는/없는)
   - extra.notes 내 동일 패턴
   - 필드명 `customer_email`, `phone_number` 값 치환
   - 중첩 dict (contexts.user.email) 값 치환
   - 기존 토큰 redaction (sk-ant, READY:port:token) 회귀 없음
3. src/ds_agent/infrastructure/observability/sentry_backend.py 수정:
   - _SECRET_PATTERNS에 email/phone/card 정규식 추가 (false positive 최소화)
   - _SECRET_FIELD_TOKENS에 email/phone/card/ssn/pan 토큰 추가
   - _deep_redact()가 중첩 dict 재귀 스캔하는지 확인, 안 되면 추가 (깊이 제한 8)
   - 치환 문자열 유형 구분 마스크 권장 (***EMAIL***, ***PHONE***, ***CARD***)
4. pytest 돌려 GREEN 확인
5. ruff + mypy clean 유지
6. 전체 회귀 테스트
7. FINAL.json 기록

## Pass 기준
- 신규 PII 테스트 8건 전부 pass
- 기존 token redaction 회귀 0건
- ruff, mypy clean
- 전체 pytest 회귀 0건

## 제약
- 수정 범위: sentry_backend.py + 관련 테스트 파일만.
- 다른 redaction 로직(로깅 포매터 등) 건드리지 말 것.
- Sentry SDK 버전 변경 금지.
- 자기 판정 금지. A02 감사자가 재감사한다.

시작하세요.
```

---

## 5. S3 — Contract & Test Drift 정리 (A03-F1, A03-F2, A04-F1, A04-F2 수정)

### 5.1 배경

4개 드리프트 이슈가 공통적으로 **"작은 타이핑/assertion 수정"** 수준이므로 단일 스트림에서 일괄 처리한다. 전부 Quick win.

### 5.2 수정 대상

#### 5.2.1 A03-F1: Bare `@tool` 데코레이터 사용 11건

**현상**: `tools/registry.py`의 `tool()` 데코레이터는 `name`, `description`을 keyword 필수 인자로 요구하는데, 다음 파일들에서 `@tool` (괄호 없이) 사용 → import 시 `TypeError`.

**위치**:
- `src/ds_agent/tools/learning_tools.py:42, 108, 169, 200, 225, 251` (6건)
- `src/ds_agent/tools/portfolio_tools.py:38, 69, 139, 196, 240` (5건)

**수정 방법**: 각 함수의 docstring 첫 줄을 description으로 끌어올려 `@tool(name=..., description=..., parameters=..., timeout=..., safety_level=...)`로 명시. 파라미터 스키마는 함수 시그니처에서 추론 가능하면 최소로 작성.

예시:
```python
# Before
@tool
def list_learning_inbox(status: str = "proposed", ...) -> str:
    """List learning items in the governance inbox with priority scores."""
    ...

# After
@tool(
    name="list_learning_inbox",
    description="List learning items in the governance inbox with priority scores.",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "default": "proposed"},
            "item_type": {"type": "string", "default": "all"},
            "limit": {"type": "integer", "default": 20},
        },
    },
    safety_level="safe",
)
def list_learning_inbox(status: str = "proposed", ...) -> str:
    ...
```

**계획서 부합성 재확인**: 계획서에서 `safety_level`은 `list_my_portfolio` (SAFE), `pause_task` / `resume_task` / `set_sla` / `request_monitoring` (CAUTION), learning 도구들은 대부분 SAFE + `rollback_promotion` CAUTION으로 명시됨. 각 도구마다 해당 safety_level 정확히 부여.

#### 5.2.2 A03-F2: WS E2E 모킹 드리프트

**현상**: `tests/e2e/test_ws_e2e.py:338, 378`의 monkeypatch가 `lambda session_id, callbacks, model=None: mock_agent` 형태. 실제 `AgentSessionRegistry._create_agent()` 시그니처는 `authority_mode` keyword를 필수로 받음.

**수정 방법**: 
```python
# Before
registry._create_agent = lambda session_id, callbacks, model=None: mock_agent

# After
def _fake_create_agent(session_id, callbacks, model=None, *, authority_mode=None, **kwargs):
    return mock_agent

registry._create_agent = _fake_create_agent
```
또는 `functools.partial`로 동등한 처리. `**kwargs`로 미래 추가 kwarg도 흡수.

#### 5.2.3 A04-F1: Work Object Store v11→v12 테스트 드리프트

**현상**: `tests/integration/infrastructure/test_sqlite_work_object_store.py::test_sqlite_work_object_store_round_trip_and_migration`가 `schema_migrations` max version `11`을 기대하나 실제로는 `12`.

**수정 방법**: assertion 값을 `12`로 업데이트. **단**, v12 마이그레이션이 실제로 무슨 변경을 포함하는지 코드(`src/ds_agent/infrastructure/persistence/work_object_store.py`의 `_MIGRATION_V11_1_VERSION_SQL`)에서 확인하고, 해당 스키마 변경에 대한 round-trip 검증도 함께 추가.

#### 5.2.4 A04-F2: Semantic Store v6→v7 테스트 드리프트

**현상**: `tests/integration/semantic/test_migration_v6.py`가 max version `6`을 기대하나 실제 `7`.

**수정 방법**: assertion 업데이트 + `_MIGRATION_V7_SQL` 변경 내용에 대한 검증 추가. 파일명을 `test_migration_v7.py`로 리네이밍할지는 현재 파일이 여러 이전 버전을 커버하는지 확인 후 결정.

### 5.3 Pass 기준

- [ ] `ds-agent` CLI import 가능 → `python -c "from ds_agent.tools import learning_tools, portfolio_tools"` 성공.
- [ ] Tool registry가 학습·포트폴리오 도구 11개 전부 등록 확인.
- [ ] `pytest tests/e2e/test_ws_e2e.py::TestChatE2E -v` → 2건 pass.
- [ ] `pytest tests/integration/infrastructure/test_sqlite_work_object_store.py -v` → pass.
- [ ] `pytest tests/integration/semantic/test_migration_v6.py -v` → pass.
- [ ] 전체 회귀 0건.

### 5.4 S3 Agent 프롬프트

```
당신은 DS Agent Fix Sprint Stream S3 담당 수정 전담 에이전트입니다.

## 컨텍스트
- 프로젝트 루트: C:\Users\aquap\Desktop\AI_Data_Scientist_Demo
- 상위 작업 지시서: Docs/qa_run_2026-04-17/FIX_SPRINT_WORK_ORDER.md §5
- 입력 감사 보고서:
  - Docs/qa_run_2026-04-17/A03_contract_schema/A03_report.md
  - Docs/qa_run_2026-04-17/A04_migration/A04_report.md
- 출력 폴더: Docs/qa_run_2026-04-17/S3_drift_cleanup/

## 책임
4개 드리프트 이슈 일괄 정리:
- A03-F1: learning_tools.py (6건) + portfolio_tools.py (5건) bare @tool → 명명 인자화
- A03-F2: tests/e2e/test_ws_e2e.py:338, 378 monkeypatch에 authority_mode kwarg 수용
- A04-F1: test_sqlite_work_object_store.py의 expected schema version 11 → 12 + v12 변경 검증
- A04-F2: test_migration_v6.py의 expected schema version 6 → 7 + v7 변경 검증

## 절차
1. START.json 기록
2. 이슈 A03-F1:
   a. src/ds_agent/tools/registry.py의 tool() 시그니처 확인
   b. learning_tools.py, portfolio_tools.py의 11개 @tool 지점 각각 name/description/parameters/safety_level 명시화
   c. safety_level: list_my_portfolio, list_learning_inbox, get_learning_item = safe; pause_task, resume_task, set_sla, request_monitoring, rollback_promotion, review_learning_item = caution
   d. pytest tests/unit/infrastructure/test_*registry* 또는 import 테스트로 검증
3. 이슈 A03-F2:
   a. monkeypatch를 authority_mode kwarg 수용하도록 수정 (**kwargs 포함)
   b. pytest tests/e2e/test_ws_e2e.py::TestChatE2E 로 검증
4. 이슈 A04-F1, F2:
   a. 각 테스트의 expected version 숫자 업데이트
   b. 해당 버전 마이그레이션이 실제로 바꾼 스키마 요소(새 컬럼/인덱스)에 대한 positive assertion 추가
5. ruff + mypy + 전체 회귀
6. DIFF_SUMMARY, TEST_RESULTS, CHANGELOG 작성
7. FINAL.json 기록

## Pass 기준
- from ds_agent.tools import learning_tools, portfolio_tools 성공
- tool registry에 학습/포트폴리오 도구 11건 등록 확인
- 4개 대상 테스트 전부 pass
- 전체 pytest 회귀 0건

## 제약
- 스코프: 위 11 함수 + 3 테스트 파일 + monkeypatch 2지점만.
- tool() 데코레이터 시그니처 자체는 변경 금지.
- 마이그레이션 코드 자체 변경 금지 (테스트 assertion만 업데이트).
- v13 마이그레이션 추가 금지 (S4 담당 영역).
- 자기 판정 금지.

시작하세요.
```

---

## 6. S4 — v13 SQLite 중앙 마이그레이션 러너 신설 (A04-F3 수정)

### 6.1 배경

A04 보고서 §4.3:
- `src/ds_agent/infrastructure/migration/` 현재 파일: `config_migrations.py`, `__init__.py`만 존재.
- SQLite 스키마는 store별로 분산되어 있음: learning=1, task_contract=10, work_object=12, semantic=7.
- 계획서의 "v1~v13 마이그레이션" 주장은 **중앙 runner가 없어** 검증 불가.
- 사용자 결정: **v13이 정답** → 중앙 runner를 신설하고 v13까지의 마이그레이션을 확인 가능하게 만든다.

### 6.2 목표 설계

중앙 마이그레이션 레지스트리가 아래를 수행해야 한다:

1. **인벤토리**: 각 store(learning, task_contract, work_object, semantic)의 현재 스키마 버전을 조회.
2. **누락 감지**: 집계된 최대값이 13 미만이면 어느 store의 어떤 버전이 누락되었는지 보고.
3. **v13 신규 추가**: 최소 한 개 store에서 v13 마이그레이션을 실제로 정의 + 적용 가능하게 만들어 "observed_max_schema_version >= 13" 조건을 실코드로 만족시킨다.
4. **멱등성**: v13 적용 후 다시 run → 변경 0건.
5. **역방향 로드 호환**: v10에서 멈춘 DB 파일을 로드해 v13까지 이어서 적용 성공.

### 6.3 구현 접근

#### Step 1 — 중앙 마이그레이션 레지스트리 신설
새 파일: `src/ds_agent/infrastructure/migration/sqlite_migrations.py`

```python
"""Central SQLite migration inventory and runner.

Aggregates per-store migrations into a single plan up to v13.
Each registered store exposes (store_name, current_version_fn, apply_migrations_fn).
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable

@dataclass(frozen=True)
class StoreMigration:
    store_name: str
    target_version: int
    current_version: Callable[[...], int]
    apply: Callable[[...], None]

STORE_MIGRATIONS: list[StoreMigration] = [
    # register learning_store, task_contract_store, work_object_store, semantic_store
    # plus the new v13 migration owner
]

def migration_inventory() -> dict[str, int]:
    """Returns {store_name: current_version} for observability/tests."""
    ...

def run_all_migrations(connections) -> dict[str, int]:
    """Applies pending migrations across all stores. Idempotent."""
    ...
```

#### Step 2 — v13 마이그레이션 구현
v13이 어느 store에 붙을지 결정해야 한다. 실제 필요한 스키마 변경이 무엇인지는 코드와 미래 로드맵에 따라 판단:

**권장**: `work_object_store` 또는 `task_contract_store`에 v13을 도입.
- 예: `schema_migrations` 테이블에 `applied_at` 컬럼 추가 (운영 감사 관점)
- 또는 Portfolio 관련 인덱스 최적화
- **수정 agent는 기존 코드베이스를 읽고 가장 자연스러운 v13 스코프를 선택** → `RECOMMENDATIONS.md`에 결정 근거 기록.

#### Step 3 — 테스트 추가

새 파일: `tests/integration/infrastructure/test_central_migration_runner.py`

테스트 케이스:
1. 빈 SQLite 파일 → `run_all_migrations()` → 모든 store의 최대 버전 ≥ 해당 store의 target.
2. 집계 최대값 == 13.
3. 멱등성: 2회 호출 시 변경 0건.
4. 역방향 로드: store 중 하나를 v10 상태로 조립 → `run_all_migrations()` → v13.
5. 마이그레이션 인벤토리 출력이 각 store의 target과 일치.

#### Step 4 — 기존 store 통합
개별 store의 `_apply_migrations()` 함수를 중앙 러너에 registry 등록. 기존 호출 경로(예: factory 내부)는 중앙 러너를 호출하도록 교체하되, 기존 store-level 호출도 backward compatible하게 유지 (멱등이므로 안전).

### 6.4 Pass 기준

- [ ] `src/ds_agent/infrastructure/migration/sqlite_migrations.py` 존재, 중앙 인벤토리 + run_all 함수 제공.
- [ ] `migration_inventory()` 호출 → 적어도 하나의 store가 `target_version=13`이며, 집계 최대값 == 13.
- [ ] 신규 `test_central_migration_runner.py` 5 케이스 전부 pass.
- [ ] 기존 `test_sqlite_work_object_store.py`, `test_migration_v6.py` (S3에서 assertion 업데이트 후) 여전히 pass.
- [ ] `ruff`, `mypy` clean.
- [ ] 전체 회귀 0건.
- [ ] A04 감사자가 재실행했을 때 `plan_claim_v13_satisfied: true`, `central_sqlite_v13_runner_found: true`.

### 6.5 S4 Agent 프롬프트

```
당신은 DS Agent Fix Sprint Stream S4 담당 수정 전담 에이전트입니다.

## 컨텍스트
- 프로젝트 루트: C:\Users\aquap\Desktop\AI_Data_Scientist_Demo
- 상위 작업 지시서: Docs/qa_run_2026-04-17/FIX_SPRINT_WORK_ORDER.md §6
- 입력 감사 보고서:
  - Docs/qa_run_2026-04-17/A04_migration/A04_report.md
  - Docs/qa_run_2026-04-17/A04_migration/A04_sqlite_inventory.json
- 출력 폴더: Docs/qa_run_2026-04-17/S4_v13_migration/

## 책임
SQLite v13 중앙 마이그레이션 러너 신설.

현재: src/ds_agent/infrastructure/migration/에는 config_migrations만 있음. store별 분산 마이그레이션의 집계 최대 버전이 12. 사용자 결정: v13이 정답이므로 v13 마이그레이션을 코드에 추가하고 중앙 러너로 인벤토리/실행 가능하게 만들 것.

## 절차 (TDD)
1. START.json 기록
2. 기존 store 마이그레이션 구조 파악 (learning, task_contract, work_object, semantic 각각의 _apply_migrations 위치와 schema_migrations 테이블 관리 방식)
3. RED: tests/integration/infrastructure/test_central_migration_runner.py 작성
   - 빈 DB → run_all → 집계 최대 버전 == 13
   - 멱등성
   - 역방향 로드 (v10에서 이어 적용)
   - 인벤토리 출력 정확성
4. GREEN: src/ds_agent/infrastructure/migration/sqlite_migrations.py 신설
   - StoreMigration dataclass, STORE_MIGRATIONS 레지스트리
   - migration_inventory(), run_all_migrations() 구현
5. v13 마이그레이션을 work_object_store 또는 task_contract_store 중 더 자연스러운 쪽에 도입:
   - 구체적 스키마 변경 내용을 RECOMMENDATIONS.md에 근거와 함께 기록
   - 기존 store의 _apply_migrations에 v13 케이스 추가
6. 기존 호출 경로가 중앙 러너를 경유하도록 최소 수정 (backward-compatible)
7. ruff + mypy + 전체 회귀
8. FINAL.json 기록 (observed_max_schema_version == 13 달성 증거 포함)

## Pass 기준
- sqlite_migrations.py 신설, migration_inventory()/run_all_migrations() 동작
- 집계 최대 버전 == 13
- test_central_migration_runner.py 5 케이스 pass
- 기존 test 회귀 0건 (S3의 test drift 수정과 독립)
- ruff, mypy clean

## 제약
- 스코프: infrastructure/migration/ 신설 + 선택된 store 1개에 v13 블록 추가 + 중앙 러너 통합 + 신규 테스트만.
- 다른 store의 기존 스키마 변경 금지.
- Domain 레이어 수정 금지.
- v13 스코프 결정 근거를 RECOMMENDATIONS.md에 반드시 기록.
- 자기 판정 금지.

시작하세요.
```

---

## 7. 스트림 완료 후: 재감사 호출

### 7.1 재감사 트리거

4개 스트림의 `FINAL.json`이 모두 `status: "pass"`이고 기본 smoke(`pytest -x --tb=short`, `ruff check`, `mypy`)가 clean이면, 원래 감사자 A01~A04를 **동일한 프롬프트로 재실행**한다.

재실행 시 감사자에게 추가 컨텍스트로 전달:
- 이전 FINAL.json 경로
- Fix Sprint FINAL.json 경로들 (어떤 변경이 있었는지 참고)
- "이번 실행은 baseline 대비 delta 검증도 수행할 것"

### 7.2 재감사 추가 요구사항

재감사에서 각 A01~A04는 다음을 추가로 확인한다:

1. **이전 실패가 모두 해소됨** (원래 보고서의 Failures and Anomalies 항목 순회).
2. **새로운 실패 도입 없음** (회귀 체크 — 이전에 pass였던 것이 지금도 pass).
3. **수정 범위 외 영향 없음** (수정 agent가 스코프를 넘어 건드리지 않았는지 AST/파일 목록으로 확인).

재감사 결과가 모두 pass이면 **Tier 1 gate 통과** → Tier 2 진입.

### 7.3 재감사도 fail이면

해당 스트림의 FINAL.json + 재감사 FINAL.json을 묶어 **다음 Fix Sprint 라운드 (Round 2)** 지시서를 이 문서 업데이트 형태로 추가. 반복한다.

---

## 8. 오케스트레이션 명령 요약

오케스트레이터(사용자 또는 메인 Claude)가 실행할 명령 순서:

```
# Phase 1: Fix Sprint (병렬 4 스트림 스폰)
# Task 툴 4번 동시 호출 - 각 스트림별 §3.5, §4.5, §5.4, §6.5 프롬프트 사용
spawn S1 (feature-dev:code-architect)
spawn S2 (general-purpose)
spawn S3 (code-simplifier 또는 general-purpose)
spawn S4 (feature-dev:code-architect)

# Phase 2: 스트림 완료 확인
# 각 S<N>_*/FINAL.json을 읽어 status 확인

# Phase 3: 재감사 (병렬 4 에이전트 재실행)
# 계획서 §12의 A01~A04 프롬프트를 그대로 재사용 + "이전 baseline 대비 delta 검증" 추가
re-spawn A01
re-spawn A02
re-spawn A03
re-spawn A04

# Phase 4: Gate 판정
# 4개 재감사 FINAL.json 모두 pass → Tier 2 진입
# 하나라도 fail → 이 문서에 Round 2 섹션 추가 후 반복
```

---

## 9. 실패 대비 (Contingency)

| 상황 | 대응 |
|------|------|
| S1의 Port 리팩터가 다른 모듈에 광범위 영향 | 스코프 축소: 3건 중 가장 깨끗한 것부터, 나머지는 Round 2로 이월 |
| S2 PII regex가 false positive 과다 발생 | 테스트 세트의 정상 payload (UUID, SHA, 긴 숫자열)도 redact 안 됨을 negative test로 추가 후 regex 정교화 |
| S3 safety_level 결정이 도구별로 불분명 | 계획서 §5.7 + `Docs/enhancement-specs/09-async-portfolio.md`, `10-self-improvement-governance.md` 참조. 판단 어려우면 기본 `safe`로 두고 `RECOMMENDATIONS.md`에 기록 |
| S4의 v13 스코프가 합당한 스키마 변경 없이 인위적으로 보임 | 기존 store 중 향후 기능 확장(P2-15 팀/엔터프라이즈, BI 커넥터)과 연결되는 지점을 선택. 그래도 불분명하면 `applied_at TIMESTAMP` 감사 컬럼 추가가 가장 방어 가능한 변경 |
| 재감사에서 새 회귀 발견 | 해당 회귀의 원인 스트림을 역추적, 스트림 agent에게 핀포인트 수정 요청 (별도 Round 2 스트림으로 분리) |

---

## 10. 변경 추적

| 날짜 | 변경 | 작성자 |
|------|------|--------|
| 2026-04-17 | 최초 작성 — 4 스트림 Fix Sprint 작업 지시서 확정 | Main orchestrator |

---

*본 문서는 Tier 1 재감사가 전원 pass를 받을 때까지 active하며, 재감사 실패 시 Round N 섹션이 append 된다. Tier 2로 진입한 시점에 archive 된다.*
