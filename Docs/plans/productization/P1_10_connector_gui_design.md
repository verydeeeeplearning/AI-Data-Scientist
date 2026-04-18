# P1-10 Connector GUI Design

Implementation note: Phase 1 scope is now implemented on the shared `connector.*` RPC surface for Postgres, BigQuery, and Snowflake.

**상태**: Complete for Postgres GA · BigQuery/Snowflake UI polish는 post-beta
**범위**: P1-10 Phase 3
**의존성**: P0-02 (secure credential storage), existing warehouse adapters
**최근 갱신**: 2026-04-15

## 2026-04-15 범위 조정

**베타 출시 범위**:
- `connector.*` RPC surface (list/test/save/delete) — Postgres/BigQuery/Snowflake 공통
- `ConnectorWizard.tsx` 의 3 가지 type 탭 — 필드 입력, validation, test → save 게이팅 동작
- Postgres: 실계정으로 list/test/save/delete 전 플로우 GA
- BigQuery/Snowflake: UI 동작 + backend adapter 모두 존재. 다만 실 운영 회귀 검증은
  각각 GCP service-account / Snowflake trial 계정 확보 시점에 수행

**post-beta** (실제 고객 워크로드 확보 시점에 재평가):
- BigQuery/Snowflake 의 auth-mode 별 edge case 검증 (ADC, keyfile rotation 등)
- connector-specific 오류 메시지/복구 제안 강화
- 대용량 결과셋 스트리밍 / 페이지네이션 UX

---

## 1. 배경

현재 코드베이스에는 connector 도메인 모델과 warehouse adapter가 이미 존재한다.

- 도메인: `src/ds_agent/domain/value_objects/connector.py`
- 설정 모델: `src/ds_agent/config/schema.py`
- adapter: `postgres_adapter.py`, `bigquery_adapter.py`, `snowflake_adapter.py`

하지만 일반 사용자용 GUI와 연결 테스트 API는 없고, 현재 설정 모델은 BigQuery/Snowflake처럼
필드 구성이 크게 다른 connector를 자연스럽게 담기 어렵다.

핵심 문제는 두 가지다.

1. connector마다 필요한 필드가 달라서 rigid schema만으로는 확장이 어렵다.
2. password / service account JSON / private key 같은 자격증명은 config YAML에 남으면 안 된다.

---

## 2. 결정 요약

이번 설계의 핵심 결정은 다음과 같다.

1. connector 설정은 `고정 코어 필드 + type별 options` 구조로 간다.
2. raw secret은 persisted config에 저장하지 않는다. `SecretStoragePort`에 저장하고 config에는 `credential_ref`만 남긴다.
3. Electron surface는 별도 HTTP보다 WebSocket RPC(`connector.*`)를 기본 제어면으로 사용한다.
4. 연결 테스트는 반드시 read-only probe만 수행한다. 사용자 입력 SQL은 받지 않는다.
5. 1차 제품화는 `Postgres 우선`, 이후 BigQuery, Snowflake를 확장한다.

---

## 3. 설계 목표

- connector 타입이 달라도 동일한 저장/테스트/UI 흐름을 유지한다.
- connector metadata와 secret을 분리한다.
- read-only 원칙을 코드와 API 계약으로 강제한다.
- Electron, CLI, headless 경로가 같은 backend 모델을 재사용할 수 있어야 한다.
- 이후 connector 타입이 늘어나도 config schema churn을 최소화한다.

## 4. 비목표

- 이번 단계에서 full SQL workbench를 만들지 않는다.
- 이번 단계에서 arbitrary marketplace-style third-party connector loading까지 열지 않는다.
- 이번 단계에서 cloud storage connector(GDrive/S3/OneDrive)는 다루지 않는다.
- 이번 단계에서 query preview/cost estimation의 모든 connector별 차이를 해결하지 않는다.

---

## 5. 왜 `고정 코어 + options` 인가

### 대안 A: 타입별 Pydantic 모델을 계속 추가

장점:

- 타입 안정성이 높다.
- 폼 검증을 정적으로 표현하기 쉽다.

단점:

- connector 타입이 늘 때마다 root config schema가 커진다.
- BigQuery/Snowflake/Postgres 간 필드 차이가 커서 모델 churn이 크다.
- renderer form, migration, serialization이 모두 타입별로 분기된다.

### 대안 B: 완전 자유 JSON

장점:

- 확장성은 가장 좋다.

단점:

- 검증이 약해진다.
- secret과 non-secret 경계가 흐려진다.
- 운영자가 어떤 필드가 안전하게 persisted 되는지 알기 어렵다.

### 선택: 고정 코어 + options

이 구조가 가장 현실적이다.

- 공통 운영 정책은 고정 필드로 관리한다.
- connector별 차이는 `options`에 넣는다.
- 검증은 `connector.test/save` 서비스에서 타입별 규칙으로 보강한다.
- secret은 항상 별도 저장소로 분리한다.

---

## 6. 제안 데이터 모델

### 6.1 Domain Model

현재 `ConnectorConfig`는 `host/database/schema` 중심인데, 이를 아래 구조로 정리한다.

```python
from dataclasses import dataclass, field
from enum import StrEnum

ConnectorOptionScalar = str | int | float | bool | None


class ConnectorType(StrEnum):
    POSTGRES = "postgres"
    BIGQUERY = "bigquery"
    SNOWFLAKE = "snowflake"


class CredentialMethod(StrEnum):
    ENV = "env"
    SECRET_MANAGER = "secret_manager"
    OAUTH = "oauth"


@dataclass(frozen=True, slots=True)
class ConnectorConfig:
    name: str
    type: ConnectorType
    label: str = ""
    options: dict[str, ConnectorOptionScalar] = field(default_factory=dict)
    credential_method: CredentialMethod = CredentialMethod.SECRET_MANAGER
    credential_ref: str = ""
    read_only: bool = True
    timeout_seconds: int = 30
    max_rows: int = 10_000
```

### 6.2 Persisted Config Shape

`DSAgentConfig.connectors`는 아래 shape를 저장한다.

```yaml
connectors:
  analytics_prod:
    type: postgres
    label: "Analytics Postgres"
    credential_method: secret_manager
    credential_ref: "connector/analytics_prod/credentials"
    read_only: true
    timeout_seconds: 30
    max_rows: 10000
    options:
      host: "db.example.com"
      port: 5432
      database: "analytics"
      schema: "public"
      username: "readonly_user"
      ssl: true
```

중요한 원칙:

- `options`에는 secret이 아닌 필드만 저장한다.
- `credential_ref`는 secure storage key만 가리킨다.
- password, service account JSON, DSN, private key는 YAML에 저장하지 않는다.

### 6.3 Type별 Options 규칙

#### Postgres

`options`:

- `host: str`
- `port: int`
- `database: str`
- `schema: str`
- `username: str`
- `ssl: bool`

secret payload:

```json
{
  "kind": "password",
  "password": "..."
}
```

비고:

- `username`은 secret이 아니므로 persisted 가능
- 필요시 추후 `dsn` 방식 지원 가능

#### BigQuery

`options`:

- `project_id: str`
- `dataset: str | null`
- `location: str | null`
- `billing_project: str | null`

secret payload 예시:

```json
{
  "kind": "service_account_json",
  "json": "{...}"
}
```

또는 향후 OAuth:

```json
{
  "kind": "oauth_ref",
  "ref": "google:default"
}
```

#### Snowflake

`options`:

- `account: str`
- `warehouse: str`
- `database: str`
- `schema: str`
- `username: str`
- `role: str | null`

secret payload:

```json
{
  "kind": "password",
  "password": "..."
}
```

향후 private key auth는 별도 `kind`로 확장한다.

---

## 7. Secret 저장 원칙

### 7.1 저장 원칙

- raw secret은 renderer localStorage에 저장하지 않는다.
- raw secret은 `config.yaml`에 저장하지 않는다.
- secret persistence는 `SecretStoragePort`를 사용한다.
- config에는 `credential_ref`만 남긴다.

### 7.2 권장 구현

`src/ds_agent/infrastructure/secrets/connector_secret_manager.py`를 추가한다.

역할:

- connector secret CRUD
- namespacing (`connector/<name>/credentials`)
- masking / existence check
- JSON payload encode/decode

권장 인터페이스:

```python
class ConnectorSecretManager:
    def store(self, connector_name: str, payload: dict[str, object]) -> str: ...
    def load(self, credential_ref: str) -> dict[str, object] | None: ...
    def delete(self, credential_ref: str) -> None: ...
    def has_secret(self, credential_ref: str) -> bool: ...
```

### 7.3 Desktop 경로에 대한 현실적 판단

Electron desktop의 최종 이상형은 main-process-owned vault지만, connector는 structured JSON secret이 필요하고
backend adapter가 직접 이를 사용해야 한다.

따라서 1차 구현은 backend `SecretStoragePort`를 canonical store로 사용한다.

이 결정의 이유:

- backend adapter가 이미 Python 기반이다.
- connection test를 backend에서 바로 수행해야 한다.
- desktop-only vault와 backend adapter를 억지로 분리하면 1차 구현 복잡도가 과도하게 올라간다.

즉, Phase 1 connector secret은 backend secure storage 기준으로 통일하고, Electron vault 완전 통합은 후속 하드닝으로 둔다.

---

## 8. API 설계

### 8.1 원칙

Electron 설정 화면은 이미 WebSocket RPC를 사용 중이므로 connector도 같은 surface를 사용한다.

P1-10 문서에 적힌 `POST /api/connectors/test`는 선택지가 될 수 있지만, desktop surface 기준으로는
`connector.*` RPC가 더 자연스럽다.

권장 기본 API:

- `connector.list`
- `connector.test`
- `connector.save`
- `connector.delete`

HTTP wrapper는 나중에 external admin surface가 필요할 때 추가한다.

### 8.2 `connector.test`

요청:

```json
{
  "name": "analytics_prod",
  "type": "postgres",
  "label": "Analytics Postgres",
  "options": {
    "host": "db.example.com",
    "port": 5432,
    "database": "analytics",
    "schema": "public",
    "username": "readonly_user",
    "ssl": true
  },
  "credentialMethod": "secret_manager",
  "credentialPayload": {
    "kind": "password",
    "password": "..."
  },
  "readOnly": true,
  "timeoutSeconds": 30,
  "maxRows": 10000
}
```

응답:

```json
{
  "ok": true,
  "latencyMs": 218,
  "probe": {
    "kind": "select_1",
    "message": "Read-only probe succeeded."
  },
  "details": {
    "server": "postgres",
    "database": "analytics",
    "schema": "public"
  },
  "warnings": []
}
```

실패 응답:

```json
{
  "ok": false,
  "errorCode": "AUTH_FAILED",
  "message": "Authentication failed for the supplied credentials."
}
```

제약:

- 사용자 SQL 입력은 받지 않는다.
- test request의 `credentialPayload`는 메모리에서만 사용하고 persisted 하지 않는다.
- secret payload는 로그에 남기지 않는다.

### 8.3 `connector.save`

요청:

```json
{
  "name": "analytics_prod",
  "type": "postgres",
  "label": "Analytics Postgres",
  "options": {
    "host": "db.example.com",
    "port": 5432,
    "database": "analytics",
    "schema": "public",
    "username": "readonly_user",
    "ssl": true
  },
  "credentialMethod": "secret_manager",
  "credentialPayload": {
    "kind": "password",
    "password": "..."
  },
  "readOnly": true,
  "timeoutSeconds": 30,
  "maxRows": 10000
}
```

동작:

1. payload validation
2. secret 저장
3. `credential_ref` 생성
4. config connectors upsert
5. adapter registry refresh

응답:

```json
{
  "connector": {
    "name": "analytics_prod",
    "type": "postgres",
    "label": "Analytics Postgres",
    "credentialMethod": "secret_manager",
    "credentialRef": "connector/analytics_prod/credentials",
    "hasCredential": true,
    "readOnly": true,
    "timeoutSeconds": 30,
    "maxRows": 10000,
    "options": {
      "host": "db.example.com",
      "port": 5432,
      "database": "analytics",
      "schema": "public",
      "username": "readonly_user",
      "ssl": true
    }
  }
}
```

### 8.4 `connector.list`

응답은 secret 제외 metadata만 반환한다.

### 8.5 `connector.delete`

동작:

1. config에서 connector 제거
2. secret storage에서 `credential_ref` 삭제
3. adapter registry refresh

---

## 9. Read-Only Probe 규칙

모든 connector test는 read-only probe만 허용한다.

| Connector | Probe | 목적 |
|---|---|---|
| Postgres | `SELECT 1` | 연결/인증 확인 |
| BigQuery | `SELECT 1` 또는 dataset metadata 조회 | client 권한/프로젝트 확인 |
| Snowflake | `SELECT 1` | 연결/인증 확인 |

추가 보장:

- connector 저장 시 `read_only=True`가 기본값이며 UI에서 꺼둘 수 없게 시작한다.
- 실제 query 도구는 기존 `validate_sql_safety()`와 query guard hook을 계속 사용한다.

---

## 10. UI 설계

### 10.1 위치

`electron/src/renderer/components/settings/ConnectorWizard.tsx`

`SettingsPanel`의 새 섹션에서 진입한다.

### 10.2 사용자 흐름

1. `Add Connector`
2. connector type 선택
3. connector form 입력
4. `Test Connection`
5. 성공 시 `Save Connector`
6. 저장 후 connector list에 반영

### 10.3 화면 상태

#### Connector List

- connector label
- type badge
- read-only badge
- credential configured 여부
- 마지막 test 결과
- edit / delete 액션

#### Wizard Form

- 공통 필드: name, label, read_only, timeout, max_rows
- type-specific form: options
- secret 입력란: password / service account JSON / etc

#### Test Result Panel

- success/failure
- latency
- resolved target info
- warnings

### 10.4 조직 정책 연동

`connectorCreationAllowed`가 false면:

- `Add Connector` 비활성화
- `connector.save/delete` RPC는 서버에서도 거부

---

## 11. 단계별 구현 권장안

### Phase 1: 모델 정리

- `ConnectorConfig` / `WarehouseConnectorSettings`를 `options` 구조로 개편
- config migration 추가

### Phase 2: Secret Manager + RPC

- `ConnectorSecretManager`
- `connector.list/test/save/delete`
- adapter registry refresh path

### Phase 3: Postgres GUI

- Postgres connector form
- read-only test
- save/delete/list

### Phase 4: BigQuery / Snowflake

- BigQuery service account / OAuth flow
- Snowflake password flow

이 순서가 가장 안전하다. Postgres는 기존 adapter와 config semantics가 가장 가깝고, UI/secret flow 검증에 적합하다.

---

## 12. Migration

config schema version을 한 단계 올리고, 기존 connector 설정이 있다면 아래 규칙으로 변환한다.

기존:

```yaml
connectors:
  default:
    type: postgres
    host: localhost
    database: analytics
    schema: public
    credential_method: env
    credential_ref: PG_DSN
```

변환 후:

```yaml
connectors:
  default:
    type: postgres
    label: "default"
    credential_method: env
    credential_ref: PG_DSN
    read_only: true
    timeout_seconds: 30
    max_rows: 10000
    options:
      host: localhost
      database: analytics
      schema: public
```

이 migration이 없으면 기존 connector users가 깨진다.

---

## 13. 테스트 전략

### Domain / Config

- `options` serialization / validation
- migration from legacy connector shape

### Secret

- connector secret CRUD
- delete cascade on connector delete

### API

- `connector.test` success/failure
- `connector.save` persists config without raw secret
- `connector.list` returns masked metadata only

### UI

- Postgres wizard happy path
- test failed -> save blocked
- org policy blocked -> create disabled

---

## 14. 오픈 이슈

1. BigQuery OAuth를 `AuthProfileStore`와 바로 연결할지, connector 전용 secret payload로 둘지
2. desktop connector secret을 장기적으로 Electron main vault와 어떻게 정렬할지
3. connector save 직후 backend runtime refresh를 즉시 할지, 새 세션부터 반영할지

현재 기준 추천:

- BigQuery는 1차에서 service account JSON 우선
- save 직후 adapter registry 즉시 refresh
- desktop vault 완전 일원화는 후속 하드닝

---

## 15. 최종 권장 결론

이번 P1-10 connector GUI는 아래 원칙으로 구현하는 것이 가장 합리적이다.

- 모델은 `고정 코어 + options`
- secret은 `SecretStoragePort`
- surface는 `connector.*` WS RPC
- test는 read-only probe only
- rollout은 `Postgres first`

이렇게 가면 flexibility, validation, security, implementation cost 사이 균형이 가장 좋다.
