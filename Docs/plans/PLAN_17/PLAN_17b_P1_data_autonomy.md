# Phase 1: Data Autonomy — 현업 위임 1순위 병목 해소

**Status**: Pending
**Started**: -
**Last Updated**: 2026-04-13
**Parent**: `PLAN_17_ROADMAP_MASTER.md`
**선행 조건**: Phase 0 완료 (Self-Debugging Loop 필수 — 커넥터 에러 자동 복구 필요)
**후행 Phase**: P3 (Enterprise Trust), P4 (Artifact), P5 (Operations)

---

## 1. Overview

### 왜 Data Autonomy가 최우선인가

실무에서 제일 큰 병목은 모델링이 아니라 **데이터 접근**이다. 현업 DS 업무의 60% 이상은 데이터를 찾고 연결하는 데서 시작한다. 현재 시스템은 "이미 파일이 워크스페이스에 있다"는 전제에서 시작하는데, 이는 현업 위임에서 가장 큰 Gap이다.

**현재 한계**:
- Sandbox가 `requests`, `socket`, `subprocess`를 차단 → 내부 warehouse/API 접근 불가
- 파일 기반 입력만 지원 (CSV, Excel, Parquet)
- SQL 쿼리 불가 → 현업에서 가장 빈번한 데이터 접근 경로 차단
- 대용량 데이터 처리 한계 (pandas 기반)

### 성공 기준

- [ ] Snowflake/BigQuery/Databricks/PostgreSQL 중 최소 2개 warehouse 연결 가능
- [ ] SQL 쿼리 실행 + 쿼리 비용 가드 동작
- [ ] 실행 경로 분리: Local Sandbox / Read-Only Warehouse / Policy-Approved Network
- [ ] 스키마 탐색으로 테이블·컬럼 의미 추론 가능
- [ ] 시간축 조인에서 미래 정보 유출 방지 (TemporalJoinGuardHook)
- [ ] 기존 테스트 전체 통과 + 신규 테스트 추가

---

## 2. Architecture Decisions (Clean Architecture)

### Layer Mapping

| Layer | Components | Responsibility |
|-------|-----------|---------------|
| **Domain** | `QuerySpec` (VO), `SchemaInfo` (Entity), `ConnectorConfig` (VO), `ExecutionPolicy` (VO) | 쿼리 명세, 스키마 구조, 커넥터 설정, 실행 정책 |
| **Application** | `QueryExecutionUseCase`, `SchemaInspectUseCase`, `QueryCostGuardHook`, `TemporalJoinGuardHook` | 쿼리 오케스트레이션, 스키마 탐색, 비용·누수 가드 |
| **Infrastructure** | `SnowflakeAdapter`, `BigQueryAdapter`, `PostgresAdapter`, `WarehouseRunnerSandbox`, `NetworkRunnerSandbox` | 실제 DB 연결, 쿼리 실행, 네트워크 격리 |
| **Presentation** | `sql_query` tool, `schema_inspect` tool, `data_catalog_search` tool | LLM에 노출되는 도구 인터페이스 |

### Key Decisions

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| Read-Only 강제 | 에이전트가 프로덕션 DB를 변경하면 안 됨 | 쓰기 필요 시 별도 승인 경로 필요 |
| 어댑터 패턴으로 커넥터 구현 | Warehouse 추가 시 코드 변경 최소화 | 추상화 비용, 각 DB의 특수 기능 활용 제한 |
| 쿼리 비용 가드를 Hook으로 | 모든 SQL 실행에 자동 적용, 우회 불가 | Hook 실행 오버헤드 |
| 실행 경로를 SandboxFactory로 분리 | 단일 책임, 보안 경계 명확 | Factory 복잡도 증가 |
| pushdown 최적화 스킬 | LLM이 효율적 SQL 생성하도록 유도 | 스킬 품질에 의존 |

---

## 3. 현재 코드 분석 — 확장 포인트

### 3.1 Sandbox 보안 (확장 필요)

**현재** (`tools/code_security.py:29-99`):
- `requests`, `httpx`, `urllib`, `socket` 모두 차단
- `subprocess`, `os.system` 차단

**필요 변경**: 전면 해제가 아닌 **실행 경로 분리**
- Local Sandbox: 기존 차단 유지
- Warehouse Runner: DB 커넥터 라이브러리만 허용 (`snowflake-connector-python`, `google-cloud-bigquery`, `psycopg2`)
- Network Runner: 정책 승인 후 `requests`, `httpx` 허용

### 3.2 Tool Registry (확장 포인트)

**현재** (`tools/registry.py`):
- 자기등록 데코레이터 패턴 → 새 tool 파일 추가만으로 등록
- `sql_query`, `schema_inspect`, `data_catalog_search` 파일 추가하면 자동 등록

### 3.3 PermissionHook (확장 필요)

**현재** (`builtin_hooks.py`):
- mode 기반 tool allowlist (READ_ONLY / WORKSPACE / FULL_ACCESS)
- SQL tool은 별도 permission 레벨 필요 (read-only SQL은 WORKSPACE에서 허용)

---

## 4. OpenClaw 참조 패턴

| OpenClaw 패턴 | DS Agent 적용 |
|--------------|--------------|
| Multi-Backend Sandbox (`SandboxBackendFactory`) | 실행 경로별 SandboxFactory 패턴 |
| Network Mode Validation (`validateNetworkMode()`) | Warehouse Runner의 네트워크 정책 |
| Tool Policy (`SandboxToolPolicy`) | SQL tool의 read-only 정책 |
| Per-agent Config (`resolveSandboxConfigForAgent()`) | 프로젝트별 커넥터 설정 |
| Remote FS Bridge (`remote-fs-bridge.ts`) | 쿼리 결과를 로컬 workspace로 안전하게 전달 |

---

## 5. Implementation Phases (TDD)

### Phase 1-1: Governed Data Connectors

**Goal**: Warehouse 연결 어댑터 + 커넥터 설정 시스템

#### RED: Write Failing Tests First

- [ ] **Test 1-1.1**: `ConnectorConfig` 검증 — 필수 필드 누락 시 에러
  - File: `tests/unit/domain/test_connector_config.py`
  - Scenario: host, database 없이 ConnectorConfig 생성 → ValidationError
  - Expected: Tests FAIL

- [ ] **Test 1-1.2**: `WarehouseAdapter` 인터페이스 — execute_query 반환 형식
  - File: `tests/unit/infrastructure/test_warehouse_adapter.py`
  - Scenario: MockAdapter.execute_query("SELECT 1") → DataFrame 반환
  - Expected: Tests FAIL

- [ ] **Test 1-1.3**: Read-Only 강제 — DDL/DML 쿼리 거부
  - File: `tests/unit/infrastructure/test_warehouse_adapter.py`
  - Scenario: "DROP TABLE users" → ReadOnlyViolationError
  - Expected: Tests FAIL

- [ ] **Test 1-1.4**: 타임아웃 — 장시간 쿼리 자동 종료
  - File: `tests/unit/infrastructure/test_warehouse_adapter.py`
  - Scenario: 30초 초과 쿼리 → TimeoutError
  - Expected: Tests FAIL

- [ ] **Test 1-1.5**: 결과 크기 제한 — 대량 결과 자동 샘플링
  - File: `tests/unit/infrastructure/test_warehouse_adapter.py`
  - Scenario: 100만 행 결과 → 상위 10,000행 + 경고
  - Expected: Tests FAIL

- [ ] **Test 1-1.6**: 커넥터 팩토리 — config에서 올바른 어댑터 선택
  - File: `tests/unit/infrastructure/test_connector_factory.py`
  - Scenario: type="snowflake" → SnowflakeAdapter 인스턴스
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 1-1.7**: Domain Value Objects
  - File: `src/ds_agent/domain/value_objects/connector.py`
  - `ConnectorConfig`: type (snowflake/bigquery/postgres/databricks), host, database, schema, credentials_ref, read_only (default=True), timeout_seconds (default=30), max_rows (default=10000)
  - `QuerySpec`: sql, parameters, timeout_override, cost_limit

- [ ] **Task 1-1.8**: Domain Interface
  - File: `src/ds_agent/domain/interfaces/warehouse.py`
  - `WarehouseAdapter` Protocol:
    - `execute_query(spec: QuerySpec) → pd.DataFrame`
    - `get_schemas() → List[SchemaInfo]`
    - `get_tables(schema: str) → List[TableInfo]`
    - `get_columns(schema: str, table: str) → List[ColumnInfo]`
    - `estimate_cost(spec: QuerySpec) → CostEstimate`
    - `validate_query(sql: str) → ValidationResult`

- [ ] **Task 1-1.9**: SQL 안전성 검증기
  - File: `src/ds_agent/infrastructure/sql_validator.py`
  - DDL 키워드 차단: CREATE, ALTER, DROP, TRUNCATE, RENAME
  - DML 키워드 차단: INSERT, UPDATE, DELETE, MERGE
  - DCL 키워드 차단: GRANT, REVOKE
  - 허용: SELECT, WITH (CTE), EXPLAIN
  - SQL 파싱: `sqlparse` 라이브러리 또는 regex 기반

- [ ] **Task 1-1.10**: Snowflake Adapter
  - File: `src/ds_agent/infrastructure/persistence/snowflake_adapter.py`
  - `snowflake-connector-python` 사용
  - Connection pooling, cursor 관리, 결과를 DataFrame 변환

- [ ] **Task 1-1.11**: BigQuery Adapter
  - File: `src/ds_agent/infrastructure/persistence/bigquery_adapter.py`
  - `google-cloud-bigquery` 사용
  - Dry-run으로 비용 추정, 결과를 DataFrame 변환

- [ ] **Task 1-1.12**: PostgreSQL Adapter
  - File: `src/ds_agent/infrastructure/persistence/postgres_adapter.py`
  - `psycopg2` 또는 `asyncpg` 사용
  - 트랜잭션 자동 ROLLBACK (read-only 보장)

- [ ] **Task 1-1.13**: Connector Factory
  - File: `src/ds_agent/infrastructure/persistence/connector_factory.py`
  - Config type → 올바른 Adapter 인스턴스 생성

#### REFACTOR

- [ ] Task 1-1.14: 어댑터 간 공통 로직 (타임아웃, 결과 제한) 추출

#### Quality Gate

- [ ] TDD compliance
- [ ] Build passes
- [ ] All tests pass
- [ ] Linting clean
- [ ] Read-Only 강제 검증 (DDL/DML 거부 테스트 통과)
- [ ] Credentials가 코드에 하드코딩되지 않음 (환경변수/secret ref)

---

### Phase 1-2: Native SQL Tool + Cost Guard

**Goal**: LLM이 SQL 쿼리를 설계·실행하고 비용을 제어하는 도구 체계

#### RED: Write Failing Tests First

- [ ] **Test 1-2.1**: `sql_query` tool — 정상 쿼리 실행 및 결과 반환
  - File: `tests/unit/tools/test_sql_tool.py`
  - Scenario: "SELECT count(*) FROM users" → {row_count: 1, columns: ["count"], data: [[12345]]}
  - Expected: Tests FAIL

- [ ] **Test 1-2.2**: `QueryCostGuardHook` — 비용 추정 후 임계치 초과 시 DENY
  - File: `tests/unit/application/test_query_cost_guard.py`
  - Scenario: 예상 비용 $50 > 임계치 $10 → DENY + 사유
  - Expected: Tests FAIL

- [ ] **Test 1-2.3**: `QueryCostGuardHook` — 임계치 이하 시 ALLOW
  - File: `tests/unit/application/test_query_cost_guard.py`
  - Scenario: 예상 비용 $2 < 임계치 $10 → ALLOW
  - Expected: Tests FAIL

- [ ] **Test 1-2.4**: SQL 결과 요약 — 대량 결과를 LLM 친화적으로 요약
  - File: `tests/unit/tools/test_sql_tool.py`
  - Scenario: 10000행 결과 → 상위 20행 + 통계 요약 (min, max, mean, nulls)
  - Expected: Tests FAIL

- [ ] **Test 1-2.5**: Integration — sql_query → QueryCostGuard → 실행
  - File: `tests/integration/test_sql_integration.py`

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 1-2.6**: `sql_query` Tool 구현
  - File: `src/ds_agent/tools/sql_tools.py`
  - Parameters: sql (required), connector_name (default: "default"), timeout (default: 30)
  - 결과 형식: {columns, data (상위 N행), row_count, summary_stats, cost_usd}
  - 대량 결과: DataFrame을 workspace에 parquet/csv로 저장 + 경로 반환

- [ ] **Task 1-2.7**: `QueryCostGuardHook` 구현
  - File: `src/ds_agent/agent/builtin_hooks.py`
  - Priority: 15
  - `pre_tool_use()`: sql_query tool 호출 시 → 비용 추정 → 임계치 비교
  - 임계치: config에서 설정 (default: $10/query, $100/session)
  - DENY 시: 사유 + 비용 절감 제안 (LIMIT, WHERE, 샘플링)

- [ ] **Task 1-2.8**: 결과 요약기
  - File: `src/ds_agent/tools/sql_result_summarizer.py`
  - 컬럼별 통계: type, nulls, unique, min, max, mean (numeric), top values (categorical)
  - LLM 토큰 절약: 전체 데이터 대신 요약 + 샘플 반환

#### Quality Gate

- [ ] 비용 가드 테스트 통과
- [ ] Read-only 검증 통과
- [ ] 결과 요약 품질 확인

---

### Phase 1-3: Execution Path Separation

**Goal**: Local Sandbox / Read-Only Warehouse Runner / Policy-Approved Network Runner 분리

#### RED: Write Failing Tests First

- [ ] **Test 1-3.1**: `ExecutionRouter` — tool 유형별 올바른 sandbox 선택
  - File: `tests/unit/application/test_execution_router.py`
  - Scenario: `execute_code` → LocalSandbox, `sql_query` → WarehouseRunner, `web_search` → NetworkRunner
  - Expected: Tests FAIL

- [ ] **Test 1-3.2**: WarehouseRunner — DB 라이브러리만 허용
  - File: `tests/unit/infrastructure/test_warehouse_runner.py`
  - Scenario: `import requests` in warehouse context → DENIED
  - Expected: Tests FAIL

- [ ] **Test 1-3.3**: NetworkRunner — 정책 승인 없이 실행 시 DENIED
  - File: `tests/unit/infrastructure/test_network_runner.py`
  - Scenario: 정책 미승인 상태에서 외부 API 호출 → DENIED
  - Expected: Tests FAIL

- [ ] **Test 1-3.4**: NetworkRunner — 정책 승인 후 실행 + 감사 로그
  - File: `tests/unit/infrastructure/test_network_runner.py`
  - Scenario: 정책 승인 + API 호출 → 성공 + audit_log 기록
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 1-3.5**: Domain Value Object
  - File: `src/ds_agent/domain/value_objects/execution_policy.py`
  - `ExecutionPolicy`: path (LOCAL/WAREHOUSE/NETWORK), allowed_modules, requires_approval, audit_required

- [ ] **Task 1-3.6**: `ExecutionRouter`
  - File: `src/ds_agent/application/services/execution_router.py`
  - Tool name → ExecutionPolicy 매핑
  - SandboxFactory에서 올바른 sandbox 인스턴스 반환

- [ ] **Task 1-3.7**: `WarehouseRunnerSandbox`
  - File: `src/ds_agent/tools/warehouse_sandbox.py`
  - 허용 모듈: `snowflake.connector`, `google.cloud.bigquery`, `psycopg2`, `pandas`, `numpy`
  - 차단: 기존 CodeSecurity 차단 목록 유지 (DB 라이브러리 예외)

- [ ] **Task 1-3.8**: `NetworkRunnerSandbox`
  - File: `src/ds_agent/tools/network_sandbox.py`
  - `requests`, `httpx` 허용 (정책 승인 후)
  - 모든 외부 호출 감사 로그 기록
  - 허용 도메인 whitelist 설정 가능

- [ ] **Task 1-3.9**: `SandboxFactory` 업데이트
  - File: `src/ds_agent/tools/sandbox.py`
  - `create_sandbox(policy: ExecutionPolicy) → ProcessSandbox` 팩토리 메서드

#### Quality Gate

- [ ] 실행 경로 격리 검증 (각 sandbox에서 금지 모듈 import 시 차단)
- [ ] 감사 로그 기록 확인
- [ ] 기존 ProcessSandbox 동작 변경 없음

---

### Phase 1-4: Schema/Lineage Inspector

**Goal**: 데이터 의미를 자율적으로 파악하는 스키마 탐색 도구

#### RED: Write Failing Tests First

- [ ] **Test 1-4.1**: `schema_inspect` — 테이블 목록 조회
  - File: `tests/unit/tools/test_schema_inspect.py`
  - Scenario: schema_inspect(action="list_tables", schema="analytics") → 테이블 리스트
  - Expected: Tests FAIL

- [ ] **Test 1-4.2**: `schema_inspect` — 컬럼 정보 조회
  - File: `tests/unit/tools/test_schema_inspect.py`
  - Scenario: schema_inspect(action="describe", table="users") → 컬럼명, 타입, nullable, 설명
  - Expected: Tests FAIL

- [ ] **Test 1-4.3**: 컬럼 의미 추론 — 이름 기반 자동 분류
  - File: `tests/unit/tools/test_schema_inspect.py`
  - Scenario: "created_at" → timestamp, "email" → PII, "user_id" → identifier
  - Expected: Tests FAIL

- [ ] **Test 1-4.4**: 샘플 데이터 조회 (안전한 LIMIT)
  - File: `tests/unit/tools/test_schema_inspect.py`
  - Scenario: schema_inspect(action="sample", table="orders", limit=5)
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 1-4.5**: `schema_inspect` Tool 구현
  - File: `src/ds_agent/tools/schema_tools.py`
  - Actions: list_schemas, list_tables, describe (columns), sample, relationships (FK)
  - 컬럼 의미 추론: naming convention 기반 규칙 (created_at → timestamp, _id → FK, email/phone → PII)

- [ ] **Task 1-4.6**: SchemaInfo Entity
  - File: `src/ds_agent/domain/entities/schema.py`
  - `SchemaInfo`: tables, relationships
  - `TableInfo`: name, schema, columns, row_count_estimate, description
  - `ColumnInfo`: name, type, nullable, description, inferred_meaning, is_pii

- [ ] **Task 1-4.7**: 스키마 캐싱
  - 스키마 정보를 memory에 저장 (변경 빈도 낮음)
  - TTL 기반 캐시 무효화 (default: 24시간)

#### Quality Gate

- [ ] 스키마 탐색 결과 정확성 확인
- [ ] PII 컬럼 자동 감지 동작 확인
- [ ] 캐시 동작 확인

---

### Phase 1-5: Temporal Join Guard

**Goal**: 시간축 조인에서 미래 정보 유출 방지

#### RED: Write Failing Tests First

- [ ] **Test 1-5.1**: 미래 정보 유출 패턴 감지
  - File: `tests/unit/application/test_temporal_join_guard.py`
  - Scenario: `LEFT JOIN events ON users.id = events.user_id` (시간 조건 없음) → WARNING
  - Expected: Tests FAIL

- [ ] **Test 1-5.2**: 올바른 시간축 조인 통과
  - File: `tests/unit/application/test_temporal_join_guard.py`
  - Scenario: `JOIN events ON ... AND events.created_at < users.label_date` → ALLOW
  - Expected: Tests FAIL

- [ ] **Test 1-5.3**: Python 코드에서 merge 패턴 감지
  - File: `tests/unit/application/test_temporal_join_guard.py`
  - Scenario: `pd.merge(df1, df2, on='user_id')` (temporal 컬럼 미사용) → WARNING
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 1-5.4**: `TemporalJoinGuardHook` 구현
  - File: `src/ds_agent/agent/ds_workflow_hooks.py`
  - Priority: 28 (BaselineGuard=25 이후, LeakageDetection=30 이전)
  - SQL 분석: JOIN 절에서 시간 조건 유무 확인
  - Python 분석: `merge()`, `join()` 호출에서 temporal 컬럼 사용 확인
  - WARNING 메시지: 구체적인 수정 제안 포함

- [ ] **Task 1-5.5**: 시간 컬럼 자동 감지
  - Naming convention: `*_at`, `*_date`, `*_time`, `timestamp`, `dt`
  - Type detection: datetime, date, timestamp 타입

#### Quality Gate

- [ ] 알려진 미래 정보 유출 패턴 전부 감지
- [ ] 정상 시간축 조인에 오탐 없음
- [ ] LeakageDetectionHook과 중복 없이 보완적 동작

---

## 6. 신규 Skill 정의

### `sql-planning` Skill

```markdown
# SQL Planning

분석 목적에 맞는 효율적인 SQL 쿼리를 설계하는 스킬.

## 쿼리 설계 원칙
1. **CTE 활용**: 복잡한 쿼리를 WITH 절로 분해하여 가독성 확보
2. **Pushdown 최적화**: WHERE/필터를 가능한 일찍 적용
3. **Projection 최적화**: 필요한 컬럼만 SELECT (SELECT * 지양)
4. **Window Function**: 순위, 이동 평균, LAG/LEAD 활용
5. **비용 인식**: EXPLAIN으로 실행 계획 확인, 불필요한 full scan 회피

## 시간축 조인 패턴
- Event-time join: 이벤트 발생 시점 기준 조인
- Processing-time join: 데이터 도착 시점 기준 조인
- 원칙: 항상 event-time 사용, processing-time은 데이터 파이프라인 디버깅에만

## Fan-out 방지
- 조인 전 key uniqueness 확인: SELECT key, COUNT(*) ... HAVING COUNT(*) > 1
- 조인 후 행 수 검증: 조인 전 행 수 ≈ 조인 후 행 수
```

### `schema-reasoning` Skill

```markdown
# Schema Reasoning

데이터 스키마를 탐색하고 의미를 추론하는 스킬.

## 컬럼 의미 추론 규칙
| 패턴 | 추론 | 예시 |
|------|------|------|
| *_id, *_key | Identifier/FK | user_id, order_key |
| *_at, *_date, *_time | Timestamp | created_at, order_date |
| *_count, *_cnt | Count metric | login_count |
| *_amount, *_price, *_cost | Monetary | total_amount |
| *_rate, *_ratio, *_pct | Ratio/Percentage | conversion_rate |
| *_flag, is_*, has_* | Boolean | is_active, has_email |
| email, phone, ssn, address | PII | — |

## Source of Truth 판별
- 이름에 "raw", "stg" → staging (중간 데이터)
- 이름에 "dim", "fact" → dimensional model (분석용)
- 이름에 "agg", "mart" → aggregated (보고용)
- 의심스러우면: 데이터 엔지니어에게 확인 요청
```

### `join-strategy` Skill

```markdown
# Join Strategy

안전하고 정확한 조인 전략을 설계하는 스킬.

## Fan-out 감지 체크리스트
1. 조인 키의 unique 비율 확인 (양쪽 테이블)
2. 예상 결과 행 수 추정 (N1 × N2 / unique_keys)
3. 조인 후 행 수 검증 (pre vs post)

## Granularity 매칭
- 양쪽 테이블의 분석 단위 일치 확인
  - user-level + transaction-level → 먼저 transaction을 user-level로 집계
  - daily + monthly → 먼저 granularity 통일

## Cardinality 검증
- 1:1 → 안전, 행 수 보존
- 1:N → 주의, N쪽 기준으로 행 수 증가
- M:N → 위험, fan-out 발생 → 반드시 사전 집계
```

---

## 7. Connector 설정 체계

### config.yaml 확장

```yaml
connectors:
  default:
    type: snowflake
    account: ${SNOWFLAKE_ACCOUNT}
    database: analytics
    schema: public
    warehouse: compute_wh
    role: reader_role
    credentials:
      method: env  # env / secret_manager / oauth
      user_var: SNOWFLAKE_USER
      password_var: SNOWFLAKE_PASSWORD
    policies:
      read_only: true
      max_query_cost_usd: 10.0
      max_rows: 50000
      timeout_seconds: 60
      allowed_schemas:
        - analytics.*
        - staging.public
      blocked_tables:
        - analytics.pii_users
        - analytics.raw_events  # too large

  bigquery_prod:
    type: bigquery
    project: my-project
    dataset: analytics
    credentials:
      method: service_account
      key_file_var: GOOGLE_APPLICATION_CREDENTIALS
    policies:
      read_only: true
      max_query_cost_usd: 5.0
      max_rows: 100000

  local_postgres:
    type: postgres
    host: localhost
    port: 5432
    database: analytics
    credentials:
      method: env
      user_var: PG_USER
      password_var: PG_PASSWORD
    policies:
      read_only: true
      timeout_seconds: 30
```

### Credential 보안

| 방법 | 설명 | 사용 시기 |
|------|------|----------|
| `env` | 환경 변수 참조 | 로컬 개발, CI/CD |
| `secret_manager` | AWS/GCP/Azure Secret Manager | 프로덕션 |
| `oauth` | OAuth 2.0 플로우 | 사용자 인증 필요 시 |

**원칙**: credential은 절대 config 파일에 직접 저장하지 않음. `*_var` suffix로 환경변수명만 참조.

---

## 8. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Warehouse 연결 credential 유출 | 낮음 | 매우높음 | 환경변수만 참조, 감사 로그, 코드에 절대 하드코딩 안 함 |
| 비용 폭주 (비싼 쿼리) | 중 | 높음 | QueryCostGuardHook, 쿼리당/세션당 비용 한도 |
| Read-Only 우회 | 낮음 | 매우높음 | SQL 파싱 + DB 레벨 read-only role 이중 보호 |
| 대량 데이터 OOM | 중 | 중간 | max_rows 제한, 결과를 파일로 저장, 샘플링 전략 |
| 시간축 조인 오탐 | 중 | 낮음 | 경고만 (DENY 아님), 사용자가 무시 가능 |
| 커넥터 라이브러리 호환성 | 높음 | 중간 | optional dependency, 없으면 graceful degradation |

---

## 9. Dependencies

### Required Before Starting
- [ ] Phase 0 완료 (Self-Debugging Loop — 커넥터 에러 자동 복구)
- [ ] Phase 0 Memory — 스키마 캐싱에 사용

### External Dependencies (optional extras)

```toml
[project.optional-dependencies]
warehouse = [
    "snowflake-connector-python>=3.0.0",
    "google-cloud-bigquery>=3.0.0",
    "psycopg2-binary>=2.9.0",
    "sqlparse>=0.5.0",
]
```

---

## 10. Rollback Strategy

### Phase 1-1 (Connectors) 실패 시
- connector 설정을 config에서 제거하면 기존 file-only 모드 유지
- 어댑터 모듈은 optional import로 없어도 에러 안 남

### Phase 1-2 (SQL Tool) 실패 시
- `sql_query` tool을 registry에서 제거 (import 라인 제거)
- QueryCostGuardHook factory에서 등록 해제

### Phase 1-3 (Execution Path) 실패 시
- SandboxFactory를 기존 단일 ProcessSandbox로 롤백
- ExecutionRouter 제거, 기존 직접 sandbox 호출로 복원

### Phase 1-4 (Schema Inspector) 실패 시
- `schema_inspect` tool 제거 (독립 모듈)

### Phase 1-5 (Temporal Join Guard) 실패 시
- Hook 등록 해제 (한 줄 삭제)

---

## 11. Progress Tracking

- Phase 1-1 (Connectors): 0%
- Phase 1-2 (SQL Tool + Cost Guard): 0%
- Phase 1-3 (Execution Path Separation): 0%
- Phase 1-4 (Schema Inspector): 0%
- Phase 1-5 (Temporal Join Guard): 0%
- **Overall Phase 1**: 0%

---

## Notes & Learnings

- [구현 중 발견 사항 기록]
