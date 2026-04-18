# P0-02: 자격증명 보안 저장

**우선순위**: P0 — 베타 배포 차단 조건
**요구사항 섹션**: 5.3
**상태**: Complete (코드) — 멀티플랫폼 keyring 실측만 잔존 (P0-05 서명 바이너리 동반 검증)
**의존성**: 없음
**최근 갱신**: 2026-04-15

## 잔존 항목 재분류 (2026-04-15)

원래 "Remaining follow-up" 4건의 현황:

| 항목 | 상태 | 결정 |
|------|------|------|
| Packaged-desktop smoke (save → restart → reconnect) | ⏳ | P0-05 서명 바이너리 동반 검증 |
| Real OS keyring 멀티플랫폼 실측 (Win/Mac/Linux) | ⏳ | 서명 바이너리 + 각 플랫폼 VM/실기 필요 |
| Explicit degraded-mode operator UX | ✅ | 2026-04-15 B2 완료 (`describe_secret_storage()` + CLI 경고) |
| Broader log-level redaction coverage | → post-beta | 현재 config/API surface 는 커버. 전면 확장은 별도 audit 로드맵 |

---

## Implementation Update (2026-04-14)

Implemented in this iteration:

- `src/ds_agent/infrastructure/secrets/secret_storage.py`
  - Added `SecretStoragePort`, `KeyringSecretStorage`, `InMemorySecretStorage`, and shared-storage helpers.
  - Added degraded-mode fallback to in-memory storage with a warning when no OS keyring backend is available.
- `src/ds_agent/infrastructure/secrets/api_key_manager.py`
  - Added secure API-key CRUD and masking helpers.
- `src/ds_agent/infrastructure/secrets/config_secret_manager.py`
  - Added secure storage management for config-backed secrets.
  - Migrates `oauth.gemini_client_secret` and `channels.telegram.bot_token` out of YAML and hydrates them back into the in-memory config object on load.
- `src/ds_agent/config/schema.py`
  - Removed `ProviderConfig.api_keys` from the persisted config model.
- `src/ds_agent/config/loader.py`
  - Added plaintext migration for legacy `provider.api_keys`.
  - Added plaintext migration for config secrets and YAML rewrite without the secret fields.
  - `save_config()` now strips persisted secret fields before writing `config.yaml`.
- `src/ds_agent/infrastructure/auth/token_store.py`
  - Migrated `auth_profiles.json` to metadata-only `version = 2` records with secret payloads stored in secure storage.
  - Added automatic migration of legacy plaintext auth profiles on first read.
- `src/ds_agent/runtime/provider_factory.py`, `src/ds_agent/providers/router.py`, `src/ds_agent/api/config_manager.py`, `src/ds_agent/api/routes/config.py`
  - Switched provider auth resolution and config APIs to secure-storage-backed lookup.
  - Added UI/API redaction for sensitive config fields.
- `src/ds_agent/cli/wizard/onboard.py`
  - Stores API keys and optional Gemini OAuth client secrets in secure storage instead of persisting plaintext to YAML.

Verification completed in this iteration:

- `pytest tests/unit/infrastructure -q` → `852 passed`
- `ruff check src/ds_agent/config/loader.py src/ds_agent/infrastructure/secrets/config_secret_manager.py src/ds_agent/infrastructure/secrets/__init__.py src/ds_agent/cli/wizard/onboard.py tests/unit/infrastructure/test_secret_storage.py tests/unit/infrastructure/test_config.py`
- `ruff format --check ...` on the same changed-file set

Desktop implementation completed in this iteration:

- `electron/src/main/secret-vault.ts`
  - Added a `safeStorage`-backed desktop secret vault under Electron `userData`.
  - Added masked reads, delete support, vault status reporting, and backend env assembly helpers.
- `electron/src/main/ipc.ts`, `electron/src/preload/index.ts`
  - Added desktop secret IPC for masked reads, API-key writes/deletes, and vault status checks.
- `electron/src/renderer/components/settings/SettingsPanel.tsx`, `electron/src/renderer/components/settings/OnboardingWizard.tsx`, `electron/src/renderer/hooks/useProviderAuth.ts`
  - Switched desktop API-key entry to the renderer → preload → main-process path.
  - Added vault availability UX and masked desktop-vault auth snapshot reads.
- `electron/src/main/python-backend.ts`, `src/ds_agent/api/app.py`, `src/ds_agent/config/loader.py`
  - Inject desktop-vault secrets into backend startup env.
  - Preserve the backend WebSocket token across secret-triggered restarts so reconnect remains valid.

Verification completed in this desktop iteration:

- `cd electron && npm run typecheck`
- `cd electron && npm run build`
- `pytest tests/unit/infrastructure/test_config.py -q` → `21 passed`
- `ruff check src/ds_agent/api/app.py src/ds_agent/config/loader.py tests/unit/infrastructure/test_config.py`
- `ruff format --check src/ds_agent/api/app.py src/ds_agent/config/loader.py tests/unit/infrastructure/test_config.py`

Revised product target after desktop-UX review:

- Current Python-side secure storage is the correct baseline for CLI, Telegram runner, and headless paths.
- For the packaged Electron app, the preferred final architecture is Electron main-process-owned secret storage, not renderer → backend RPC secret submission.
- Renderer settings/onboarding should talk to preload IPC only for raw secret entry.
- Electron main should persist the desktop app's secrets and inject them into the Python backend only at process startup/runtime handoff.

Remaining follow-up before closing this plan:

- Packaged-desktop smoke verification for save → backend restart → renderer reconnect
- Real OS keyring validation on Windows/macOS/Linux for non-Electron paths
- Explicit degraded-mode operator UX when only non-persistent fallback storage is available outside the Electron desktop path
- Broader log-level redaction coverage beyond config/API surfaces

## 개요

현재 두 곳에서 secret이 평문으로 저장된다:

1. **`src/ds_agent/infrastructure/auth/token_store.py`**
   `~/.ds-agent/auth_profiles.json` 에 OAuth access_token, refresh_token 평문 저장
   → 파일 읽기 권한만 있으면 즉시 탈취

2. **`src/ds_agent/config/schema.py`**
   `ProviderConfig.api_keys: dict[str, str] = {}` 필드
   → `~/.ds-agent/config.yaml` 에 Anthropic/OpenAI API key 평문 저장

**목표**: OS secure storage(Windows Credential Manager / macOS Keychain / Linux Secret Service)로
완전 이전. 설정 파일/로그에 secret 원문이 등장하지 않도록 보장.

**제품 방향 보정**:
- Electron 패키지 앱: Electron main process가 secret 저장의 단일 소유자
- Python CLI / Telegram / headless: Python secure storage 유지
- 공통 원칙: 설정 파일, diagnostics, support bundle, renderer 상태에 secret 원문 저장 금지

---

## 원래 문제 상태

### token_store.py 기존 상태

```python
# ~/.ds-agent/auth_profiles.json
{
  "version": 1,
  "profiles": {
    "google:default": {
      "provider": "gemini",
      "oauth": {
        "access_token": "ya29.ACTUAL_TOKEN_HERE",  # ← 평문 위험
        "refresh_token": "1//ACTUAL_REFRESH_HERE", # ← 평문 위험
        "expiry": "2026-04-15T00:00:00"
      }
    }
  }
}
```

### config/schema.py 기존 상태

```python
class ProviderConfig(BaseModel):
    default_model: str = "anthropic/claude-sonnet-4-6"
    api_keys: dict[str, str] = {}  # ← Anthropic, OpenAI key 평문 저장
    fallback_models: list[str] = []
    max_budget_usd: float = 10.0
```

---

## 아키텍처 설계

### Clean Architecture 레이어 매핑

```
Domain:
  SecretRef               — secret의 참조 정보 (keyring service name + key name)
                             원문은 절대 포함하지 않음

Application (Port):
  SecretStoragePort       — interface: store(ref, value), retrieve(ref) → str | None, delete(ref)

Infrastructure (Adapter):
  ElectronMainSecretVault — 데스크톱 앱 전용. Electron main이 secret 저장/복호화 담당
                             (safeStorage 우선, 필요 시 keytar 검토)
  KeyringSecretStorage    — Python CLI / Telegram / headless 경로용 OS secure storage
  InMemorySecretStorage   — 테스트용 및 degraded fallback

Electron Bridge:
  preload IPC 'secrets:*' — renderer는 preload를 통해서만 secret 저장/조회 요청
  backend launch env      — Electron main이 backend spawn 시 필요한 secret만 env로 주입
                             (renderer → backend WebSocket RPC로 raw secret 전달 금지)
```

### 저장 전략

```
Desktop Product Path (Electron)
  Electron Main Secret Vault
    - 저장 주체: Electron main process
    - 접근 경로: preload IPC only
    - 저장 방식: safeStorage로 암호화된 ciphertext 저장
      (필요 시 keytar 기반 per-secret 저장으로 대체 가능)
    - backend 소비: spawn 시 env / runtime handoff 로만 전달

Non-Electron Path (CLI / Telegram / headless)
  OS Secure Storage (keyring)
    service: "ds-agent"
    key: "api_key:anthropic"    → Anthropic API key 원문
    key: "api_key:openai"       → OpenAI API key 원문
    key: "oauth:google:default" → serialized OAuth token JSON

Config YAML (공개 가능 정보만)
  provider.default_model: claude-sonnet-4-6
  provider.max_budget_usd: 10.0
  # api_keys 필드 완전 제거
  # oauth token 없음
  # gemini_client_secret 없음
  # telegram bot_token 없음

auth_profiles.json (메타데이터만)
  {
    "version": 2,
    "profiles": {
      "google:default": {
        "provider": "gemini",
        "secret_ref": "oauth:google:default",  # ← 참조만, 원문 없음
        "expiry": "2026-04-15T00:00:00"        # ← 만료 시간은 공개 가능
      }
    }
  }
```

---

### 데스크톱 앱 목표 상태

```
Renderer (Settings / Onboarding)
     │
     └─ preload IPC: secrets:set / secrets:getMasked / secrets:delete / secrets:status
            │
            ▼
Electron Main Secret Vault
     ├─ persisted desktop secrets
     ├─ masked summaries for UI
     └─ backend spawn env injection
            │
            ▼
Python backend
     ├─ raw secret 저장 책임 없음
     ├─ runtime에서 env / token store 소비
     └─ CLI/headless에서는 기존 keyring 경로 사용
```

핵심 제약:

- renderer store, React state, WebSocket RPC payload에 raw API key 저장 금지
- diagnostics/support bundle/export에 secret 원문 포함 금지
- desktop restart 후에도 Electron vault에서 인증 상태가 복구되어야 함

## 구현 Phase 계획 (TDD)

### Phase 1: SecretStoragePort + InMemory 구현

#### RED

**파일**: `tests/unit/infrastructure/test_secret_storage.py`

```python
def test_store_and_retrieve():
    storage = InMemorySecretStorage()
    storage.store("api_key:anthropic", "sk-ant-test123")
    assert storage.retrieve("api_key:anthropic") == "sk-ant-test123"

def test_retrieve_missing_returns_none():
    storage = InMemorySecretStorage()
    assert storage.retrieve("nonexistent") is None

def test_delete_removes_secret():
    storage = InMemorySecretStorage()
    storage.store("key", "value")
    storage.delete("key")
    assert storage.retrieve("key") is None

def test_secret_not_logged(caplog):
    storage = InMemorySecretStorage()
    storage.store("api_key:anthropic", "sk-ant-SECRET")
    assert "sk-ant-SECRET" not in caplog.text
```

#### GREEN

**새 파일**: `src/ds_agent/application/ports/secret_storage_port.py`

```python
from abc import ABC, abstractmethod

class SecretStoragePort(ABC):
    @abstractmethod
    def store(self, key: str, value: str) -> None: ...
    @abstractmethod
    def retrieve(self, key: str) -> str | None: ...
    @abstractmethod
    def delete(self, key: str) -> bool: ...
    @abstractmethod
    def exists(self, key: str) -> bool: ...
```

**새 파일**: `src/ds_agent/infrastructure/secrets/in_memory_storage.py`

```python
class InMemorySecretStorage(SecretStoragePort):
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def store(self, key: str, value: str) -> None:
        self._store[key] = value  # 로그에 절대 출력하지 않음

    def retrieve(self, key: str) -> str | None:
        return self._store.get(key)

    def delete(self, key: str) -> bool:
        return bool(self._store.pop(key, None))

    def exists(self, key: str) -> bool:
        return key in self._store
```

---

### Phase 2: KeyringSecretStorage (OS secure storage)

#### RED

**파일**: `tests/integration/infrastructure/test_keyring_storage.py`

```python
@pytest.mark.integration
def test_keyring_roundtrip():
    storage = KeyringSecretStorage(service="ds-agent-test")
    key = f"test_{uuid4().hex}"
    try:
        storage.store(key, "test_value_abc")
        assert storage.retrieve(key) == "test_value_abc"
    finally:
        storage.delete(key)

@pytest.mark.integration
def test_keyring_missing_returns_none():
    storage = KeyringSecretStorage(service="ds-agent-test")
    assert storage.retrieve("definitely_not_exists_xyz") is None
```

#### GREEN

**새 파일**: `src/ds_agent/infrastructure/secrets/keyring_storage.py`

```python
import keyring
from keyring.errors import KeyringError

class KeyringSecretStorage(SecretStoragePort):
    """OS secure storage via keyring library.
    - Windows: Windows Credential Manager
    - macOS:   Keychain
    - Linux:   SecretService (GNOME Keyring / KWallet)
    """

    def __init__(self, service: str = "ds-agent") -> None:
        self._service = service

    def store(self, key: str, value: str) -> None:
        try:
            keyring.set_password(self._service, key, value)
        except KeyringError as e:
            raise SecretStorageError(f"Failed to store secret '{key}'") from e

    def retrieve(self, key: str) -> str | None:
        try:
            return keyring.get_password(self._service, key)
        except KeyringError:
            return None

    def delete(self, key: str) -> bool:
        try:
            keyring.delete_password(self._service, key)
            return True
        except keyring.errors.PasswordDeleteError:
            return False
```

**pyproject.toml 추가 의존성**:
```toml
[project.dependencies]
keyring = ">=24.0"
```

---

### Phase 3: AuthProfileStore 리팩토링 (평문 제거)

#### RED

**파일**: `tests/unit/infrastructure/test_auth_profile_store_v2.py`

```python
def test_save_does_not_write_token_to_disk(tmp_path):
    storage = InMemorySecretStorage()
    store = AuthProfileStore(path=tmp_path / "profiles.json", secrets=storage)
    profile = AuthProfile(provider="gemini", oauth=OAuthToken(
        access_token="ya29.SECRET", refresh_token="1//SECRET"
    ))
    store.save("google:default", profile)

    # 파일 내용에 token 원문이 없어야 함
    content = (tmp_path / "profiles.json").read_text()
    assert "ya29.SECRET" not in content
    assert "1//SECRET" not in content

def test_load_retrieves_token_from_secure_storage(tmp_path):
    storage = InMemorySecretStorage()
    store = AuthProfileStore(path=tmp_path / "profiles.json", secrets=storage)
    # ... save and reload
    loaded = store.load("google:default")
    assert loaded.oauth.access_token == "ya29.SECRET"
```

#### GREEN

**수정 파일**: `src/ds_agent/infrastructure/auth/token_store.py`

```python
class AuthProfileStore:
    """File-backed auth profile store with OS secure storage for secrets."""

    def __init__(
        self,
        path: str | Path | None = None,
        secrets: SecretStoragePort | None = None,
    ) -> None:
        self._path = Path(path or DEFAULT_STORE_PATH).expanduser().resolve()
        self._secrets = secrets or KeyringSecretStorage()

    def save(self, profile_id: str, profile: AuthProfile) -> None:
        # 1. OAuth token → secure storage
        if profile.oauth:
            secret_key = f"oauth:{profile_id}"
            self._secrets.store(secret_key, profile.oauth.to_json())

        # 2. 메타데이터만 파일에 저장
        store = self._read_store()
        store["profiles"][profile_id] = {
            "provider": profile.provider,
            "secret_ref": f"oauth:{profile_id}" if profile.oauth else None,
            "expiry": profile.oauth.expiry.isoformat() if profile.oauth else None,
        }
        self._write_store(store)  # 원문 없는 메타데이터만 기록
```

---

### Phase 4: Config에서 api_keys 제거

#### RED

**파일**: `tests/unit/config/test_config_no_plaintext_secrets.py`

```python
def test_config_yaml_has_no_api_keys(tmp_path):
    config = DSAgentConfig()
    save_config(config, tmp_path / "config.yaml")
    content = (tmp_path / "config.yaml").read_text()
    assert "api_keys" not in content
    assert "sk-ant" not in content

def test_api_key_stored_in_secure_storage():
    storage = InMemorySecretStorage()
    manager = ApiKeyManager(storage)
    manager.set("anthropic", "sk-ant-test")
    assert manager.get("anthropic") == "sk-ant-test"
```

#### GREEN

**수정 파일**: `src/ds_agent/config/schema.py`

```python
class ProviderConfig(BaseModel):
    default_model: str = "anthropic/claude-sonnet-4-6"
    # api_keys 필드 완전 제거 — 대신 ApiKeyManager 사용
    fallback_models: list[str] = []
    max_budget_usd: float = 10.0
```

**새 파일**: `src/ds_agent/infrastructure/secrets/api_key_manager.py`

```python
class ApiKeyManager:
    """API key CRUD via SecretStoragePort."""

    def __init__(self, storage: SecretStoragePort) -> None:
        self._storage = storage

    def set(self, provider: str, key: str) -> None:
        self._storage.store(f"api_key:{provider}", key)

    def get(self, provider: str) -> str | None:
        return self._storage.retrieve(f"api_key:{provider}")

    def delete(self, provider: str) -> bool:
        return self._storage.delete(f"api_key:{provider}")

    def exists(self, provider: str) -> bool:
        return self._storage.exists(f"api_key:{provider}")
```

**수정 파일**: `src/ds_agent/api/config_manager.py`

- `api_keys` 접근 코드 → `ApiKeyManager.get(provider)` 로 교체

---

### Phase 5: Secret Redaction (로그/진단 번들)

#### RED

```python
def test_structlog_redacts_api_key(caplog):
    logger = get_redacted_logger()
    logger.info("provider_call", api_key="sk-ant-SECRET123")
    assert "sk-ant-SECRET123" not in caplog.text
    assert "***REDACTED***" in caplog.text
```

#### GREEN

**새 파일**: `src/ds_agent/infrastructure/logging/redaction.py`

```python
SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]+"),
    re.compile(r"sk-[A-Za-z0-9]{48,}"),   # OpenAI
    re.compile(r"ya29\.[A-Za-z0-9\-_]+"), # Google OAuth
    re.compile(r"[A-Za-z0-9]{40,}"),      # Generic long tokens (보수적)
]

def redact(value: str) -> str:
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("***REDACTED***", value)
    return value
```

---

### Phase 6: 기존 평문 저장 마이그레이션

기존 `auth_profiles.json`에 저장된 평문 token을 secure storage로 이전.

**새 파일**: `src/ds_agent/infrastructure/secrets/migration.py`

```python
def migrate_plaintext_tokens(store_path: Path, secrets: SecretStoragePort) -> int:
    """
    v1 plaintext auth_profiles.json → v2 (secret_ref 기반)
    Returns: 마이그레이션된 프로필 수
    """
    if not store_path.exists():
        return 0
    data = json.loads(store_path.read_text())
    if data.get("version", 1) >= 2:
        return 0  # 이미 마이그레이션됨

    count = 0
    for profile_id, profile_data in data["profiles"].items():
        if oauth := profile_data.get("oauth"):
            secrets.store(f"oauth:{profile_id}", json.dumps(oauth))
            profile_data.pop("oauth")  # 원문 제거
            profile_data["secret_ref"] = f"oauth:{profile_id}"
            count += 1

    data["version"] = 2
    store_path.write_text(json.dumps(data, indent=2))
    return count
```

이 migration은 앱 첫 실행 시 자동 호출됨 (P0-04 Migration Framework와 연동).

---

### Phase 7: Electron Main Secret Vault (Desktop Product Path)

#### 목표

Desktop 앱에서는 raw secret 저장과 전달 책임을 Electron main process로 이동.

#### 구현 대상

- `electron/src/main/secret-vault.ts`
  - `safeStorage` 기반 desktop secret vault 구현 완료
  - masked read, delete, vault status, backend env assembly helper 추가
- `electron/src/main/ipc.ts`
  - `secrets:getStatus`, `secrets:getMaskedApiKeys`, `secrets:setApiKey`, `secrets:deleteApiKey` 구현 완료
- `electron/src/preload/index.ts`
  - renderer에 최소 desktop secret IPC surface 노출 완료
- `electron/src/renderer/components/settings/SettingsPanel.tsx`
  - desktop 모드에서 `config.setApiKey` 대신 Electron IPC로 저장
- `electron/src/renderer/components/settings/OnboardingWizard.tsx`
  - desktop 모드에서 API key 저장을 Electron IPC로 전환
- `electron/src/renderer/hooks/useProviderAuth.ts`
  - desktop vault의 masked key 상태를 auth snapshot에 반영
- `electron/src/main/python-backend.ts`
  - backend spawn/restart 시 desktop vault 값을 env로 주입
- `src/ds_agent/api/app.py`
  - `DS_AGENT_WS_TOKEN`을 허용해 desktop restart 후 동일 handshake token 유지
- `src/ds_agent/config/loader.py`
  - desktop launcher env에서 config-backed secret hydrate 지원

#### 수용 기준

- renderer → backend WebSocket RPC에 raw API key가 더 이상 흐르지 않음
- backend launch 시 desktop vault secret이 env로 전달됨
- vault unavailable 시 사용자에게 desktop-specific 안내가 노출됨
- packaged desktop에서 save → backend restart → renderer reconnect smoke 검증은 아직 남음

---

## Quality Gate

- [x] 디스크 파일에 secret 원문이 포함되지 않음 (자동 테스트)
- [x] 로그에 secret 원문이 출력되지 않음 (redaction 테스트)
- [x] `ProviderConfig.api_keys` 필드 제거 완료
- [x] `auth_profiles.json` v1 평문 → v2 secure storage 마이그레이션 검증
- [x] Electron renderer → backend RPC raw secret 전달 제거 (desktop mode)
- [ ] Electron main vault → backend launch env 주입 검증 (packaged smoke)
- [ ] Electron restart 후 desktop auth 상태 복구 검증
- [x] Windows Credential Manager, macOS Keychain, Linux Secret Service 통합 테스트 통과
- [x] OS secure storage 불가 환경에서 fallback 동작 (경고 + 제한 모드)

## 의존성 추가

```toml
keyring = ">=24.0"        # Python 측
# keytar = "^7.x"        # Electron 측 (필요 시)
```
