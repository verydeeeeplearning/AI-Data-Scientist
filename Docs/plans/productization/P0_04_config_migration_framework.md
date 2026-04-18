# P0-04: 설정/데이터 마이그레이션 프레임워크

**우선순위**: P0 — 베타 배포 차단 조건
**요구사항 섹션**: 5.9
**상태**: Complete (config.yaml migration 완료, 타 저장소는 post-beta)
**의존성**: P0-02 (secret storage 이전 migration 포함)
**최근 갱신**: 2026-04-15

## 범위 재조정 (2026-04-15)

**베타 출시 범위**: config.yaml migration runner + 자동 백업 + 실패 rollback. v1→v2→v3→v4
accrual chain 동작 확인, 작성 규약 문서화까지.

**post-beta deferral** (이유: 베타 스코프에서 하위 호환 문제 발생 가능성 낮음 — 아래 저장소들은
아직 신규 필드 추가 방식으로 변경 가능):
- SQLite session DB schema migration (현 스키마 안정, 다음 break 시점에 도입)
- auth profiles / domain KB / project store 를 공통 migration runner 에 연결
- migration 실패를 Electron UI 에서 사용자에게 노출 (현재는 CLI 로그만)

post-beta 착수 조건: 위 저장소 중 하나라도 backward-incompatible 변경이 필요해질 때.
그 시점에 본 plan 의 "신규 Migration 작성 규약" 7-step 절차 적용.

---

## 개요

설치형 제품은 출시 후 지속적으로 버전이 올라간다. 현재 `~/.ds-agent/config.yaml`,
`auth_profiles.json`, session DB, runtime event log 등 영구 저장소가 여러 개 있지만
**버전 필드도, 마이그레이션 로직도 없다**.

구버전 설정 파일로 신버전 앱 실행 시 예외 발생 또는 데이터 손상 위험.

---

## 현재 구현 상태 (2026-04-15 재감사)

완료:
- `MigrationSpec`, `MigrationResult`, `MigrationRunner` 추가
- `config.yaml` migration 누적: v1→v2 (legacy `provider.api_keys` 제거),
  v2→v3 (connector 정규화), v3→v4 (observability 기본값 추가:
  `sentry_dsn`/`sentry_environment`/`telemetry_enabled`/`error_reporting_enabled`)
- `CURRENT_CONFIG_SCHEMA_VERSION = 4` (`config/schema.py:35`)
- `load_config()`에서 secret 이전 후 config schema migration 자동 실행
- migration 전 `.migration-backups/` 자동 백업 생성
- 자동 테스트: 순차 migration, idempotent, rollback, legacy config 로드/백업 생성
  (`tests/unit/application/test_migration_runner.py` green)

남은 항목 (post-beta 재평가 가능):
- SQLite session DB schema migration
- auth profiles / domain KB / project store를 공통 migration runner에 연결
- migration 실패 결과를 Electron UI에서 사용자에게 노출하는 경로

---

## 신규 Migration 작성 규약 (2026-04-15)

새 schema 변경이 필요할 때 다음 절차를 따른다. 베타 이후 운영 단계에서도 동일 규약 적용.

### 0. 변경 가능 여부 사전 점검
- **하위 호환 가능하면 migration 없이 진행**: 신규 필드를 `Optional` 또는 default 값을
  가진 형태로 schema 에 추가하는 것만으로 충분하면 굳이 schema version 을 올리지 않는다.
- **migration 이 필요한 경우**:
  - 기존 필드 의미가 변경됨 (e.g. unit, type, 위치)
  - 기존 필드 제거 (legacy field 가 더 이상 사용되지 않음)
  - 기존 필드 정규화 (e.g. flat → nested, snake_case 통일)
  - 새 필드인데 기존 사용자 데이터로부터 값을 유도해야 함

### 1. Schema bump
`src/ds_agent/config/schema.py`:
```python
CURRENT_CONFIG_SCHEMA_VERSION = 5  # ← bump
```
같은 PR 안에서만 bump. 절대로 schema version 만 올리고 migration 을 다음 PR 로 미루지 말 것.

### 2. Migration 함수 작성
`src/ds_agent/infrastructure/migration/config_migrations.py`:
```python
def migrate_config_v4_to_v5(data: dict[str, Any]) -> dict[str, Any]:
    """One-line description of what this migration changes."""
    migrated = deepcopy(data)
    # 변환 로직. data 인자는 직접 변경하지 말 것 (deepcopy 반환).
    migrated["_schema_version"] = CURRENT_CONFIG_SCHEMA_VERSION
    logger.info("config_migration_v4_to_v5", ...)  # 식별 가능한 키만 로그
    return migrated
```

규칙:
- **Idempotent**: 같은 입력으로 두 번 실행해도 동일 결과 (자동 테스트가 검증)
- **Pure**: 외부 I/O 금지, 입력 dict 만 변환
- **Logging**: secret 이나 PII 없이 변경 양상만 (e.g. `legacy_field_removed=True`)
- **마지막 줄**: `_schema_version` 을 `CURRENT_CONFIG_SCHEMA_VERSION` 으로 갱신

### 3. Registry 등록
같은 파일 하단의 `CONFIG_MIGRATIONS` 리스트에 새 `MigrationSpec` 추가:
```python
MigrationSpec(
    store="config",
    from_version=4,
    to_version=CURRENT_CONFIG_SCHEMA_VERSION,
    description="Short description.",
    migrate=migrate_config_v4_to_v5,
),
```
`from_version` 은 직전 단계, `to_version` 은 항상 `CURRENT_CONFIG_SCHEMA_VERSION`.

### 4. 테스트 추가
`tests/unit/application/test_migration_runner.py` 에 다음 케이스 추가:
- v(N-1) → vN 단일 step 변환 정확성
- v(<N-1) → vN 누적 chain (예: v1 → v5 직행)
- Idempotent (vN 입력으로 다시 돌렸을 때 변동 없음)
- 영향 받는 도메인 객체로 `DSAgentConfig.model_validate` 가 통과하는지

### 5. 백업 / 롤백 확인
- `MigrationRunner` 가 `.migration-backups/<timestamp>/` 에 원본을 자동 백업 — 별도 작업 불필요
- 사용자 직접 롤백 시나리오: 백업 디렉토리 → 원본 자리로 복원 + 구버전 앱 사용
- **Destructive migration 금지**: 정보 손실이 발생하는 변환은 별도 confirmation flow 필요
  (현재 v1→v2 의 api_keys 제거가 유일한 예외 — 보안 사유로 plaintext 평문 제거 불가피)

### 6. 문서 업데이트
- 본 plan 파일의 "현재 구현 상태" 섹션에 새 migration 한 줄 추가
- `CHANGELOG` 가 있다면 사용자 영향 명시 (어떤 필드가 어떻게 바뀌는지)
- v1→v2 처럼 보안/거버넌스 영향이 있는 경우 release notes 에 별도 강조

### 7. 다른 저장소 migration (auth profiles, session DB 등)
현재 `MigrationRunner` 는 `store="config"` 만 활성. 다른 저장소를 추가하려면:
- 해당 저장소의 read/write 인터페이스에 `_schema_version` 또는 동등한 versioning 도입
- `MigrationSpec(store="<name>", ...)` 등록
- runner 호출 지점 (`load_config()` 같은 boot path) 에 `runner.run_for_store("<name>")`
  추가
- 저장소별 백업 디렉토리 분리

---

## 현재 저장소 목록

| 저장소 | 경로 | 현재 버전 관리 |
|--------|------|--------------|
| Config YAML | `~/.ds-agent/config.yaml` | ✗ |
| Auth profiles | `~/.ds-agent/auth_profiles.json` | v1 필드만 있음 |
| Session DB | `~/.ds-agent/sessions.db` (SQLite) | ✗ |
| Runtime event log | `~/.ds-agent/events/` | ✗ |
| Domain KB | `~/.ds-agent/domain_kb.json` | ✗ |
| Project store | `~/.ds-agent/projects/` | ✗ |

---

## 아키텍처 설계

### Migration 프레임워크 구조

```
Domain:
  MigrationSpec           — (from_version, to_version, description, migrate_fn)
  MigrationResult         — (success, migrated_count, errors, backed_up_paths)

Application:
  MigrationRunner         — 모든 저장소의 migration 조율
    ├─ 각 Store의 current version 감지
    ├─ 필요한 migration 순서 결정
    ├─ 백업 생성 → migration 실행 → 결과 기록
    └─ 실패 시 rollback

Infrastructure:
  ConfigMigrationStore    — config.yaml 마이그레이션
  AuthProfileMigrationStore — auth_profiles.json 마이그레이션 (P0-02 연동)
  SessionDbMigrationStore — SQLite schema 마이그레이션
  DomainKbMigrationStore  — domain_kb.json 마이그레이션
```

### 버전 관리 방식

**Config YAML 버전 추가**:
```yaml
# ~/.ds-agent/config.yaml
_schema_version: 2   # ← 신규 추가 (없으면 version 1로 간주)
provider:
  default_model: anthropic/claude-sonnet-4-6
  max_budget_usd: 10.0
# api_keys 필드 v2에서 완전 제거 (P0-02 연동)
```

**Migration Registry**:
```python
MIGRATIONS: list[MigrationSpec] = [
    MigrationSpec(
        store="config",
        from_version=1, to_version=2,
        description="Remove api_keys field, move to secure storage",
        migrate=migrate_config_v1_to_v2,
    ),
    MigrationSpec(
        store="auth_profiles",
        from_version=1, to_version=2,
        description="Move OAuth tokens from plaintext to secure storage",
        migrate=migrate_auth_v1_to_v2,  # P0-02의 migration.py 사용
    ),
    # 향후 migration 추가 예시:
    # MigrationSpec(store="config", from_version=2, to_version=3, ...)
]
```

---

## 구현 Phase 계획 (TDD)

### Phase 1: MigrationSpec + MigrationRunner 기반

#### RED

**파일**: `tests/unit/application/test_migration_runner.py`

```python
def test_no_migration_needed_when_current():
    runner = MigrationRunner(migrations=MIGRATIONS)
    store = {"_schema_version": 2, "provider": {}}
    result = runner.run_for_store("config", store)
    assert result.migrated_count == 0

def test_migration_applied_in_order():
    migrations = [
        MigrationSpec("config", 1, 2, "step 1", lambda d: {**d, "_schema_version": 2, "step1": True}),
        MigrationSpec("config", 2, 3, "step 2", lambda d: {**d, "_schema_version": 3, "step2": True}),
    ]
    runner = MigrationRunner(migrations=migrations)
    data = {"_schema_version": 1}
    result = runner.run_for_store("config", data)
    assert result.final_data["_schema_version"] == 3
    assert result.final_data["step1"] is True
    assert result.final_data["step2"] is True

def test_migration_is_idempotent():
    runner = MigrationRunner(migrations=MIGRATIONS)
    data = {"_schema_version": 1, "provider": {"api_keys": {"anthropic": "key"}}}
    result1 = runner.run_for_store("config", data)
    result2 = runner.run_for_store("config", result1.final_data)
    assert result2.migrated_count == 0  # 두 번 실행해도 동일

def test_backup_created_before_migration(tmp_path):
    runner = MigrationRunner(migrations=MIGRATIONS, backup_dir=tmp_path)
    runner.run_for_store("config", {"_schema_version": 1, ...})
    backups = list(tmp_path.glob("config_v1_*.yaml"))
    assert len(backups) == 1

def test_rollback_on_migration_failure(tmp_path):
    def failing_migrate(data): raise ValueError("simulated failure")
    migrations = [MigrationSpec("config", 1, 2, "fail", failing_migrate)]
    runner = MigrationRunner(migrations=migrations, backup_dir=tmp_path)
    result = runner.run_for_store("config", {"_schema_version": 1})
    assert not result.success
    # 원본 파일 복원 확인
    assert result.rolled_back is True
```

#### GREEN

**새 파일**: `src/ds_agent/application/migration/migration_runner.py`

```python
@dataclass
class MigrationSpec:
    store: str
    from_version: int
    to_version: int
    description: str
    migrate: Callable[[dict], dict]

@dataclass
class MigrationResult:
    success: bool
    migrated_count: int
    final_data: dict
    errors: list[str] = field(default_factory=list)
    backed_up_paths: list[Path] = field(default_factory=list)
    rolled_back: bool = False

class MigrationRunner:
    def __init__(
        self,
        migrations: list[MigrationSpec],
        backup_dir: Path | None = None,
    ) -> None:
        self._migrations = migrations
        self._backup_dir = backup_dir or Path("~/.ds-agent/.migration-backups").expanduser()

    def run_for_store(self, store: str, data: dict) -> MigrationResult:
        current_version = data.get("_schema_version", 1)
        applicable = [
            m for m in self._migrations
            if m.store == store and m.from_version >= current_version
        ]
        applicable.sort(key=lambda m: m.from_version)

        if not applicable:
            return MigrationResult(success=True, migrated_count=0, final_data=data)

        # Backup 먼저
        backup_path = self._create_backup(store, data, current_version)

        # Migration 순차 적용
        current = data
        count = 0
        try:
            for spec in applicable:
                if current.get("_schema_version", 1) == spec.from_version:
                    current = spec.migrate(current)
                    count += 1
                    logger.info("migration_applied", store=store,
                                from_v=spec.from_version, to_v=spec.to_version)
        except Exception as e:
            # Rollback
            logger.error("migration_failed", store=store, error=str(e))
            return MigrationResult(
                success=False, migrated_count=count,
                final_data=data,  # 원본 반환
                errors=[str(e)],
                backed_up_paths=[backup_path],
                rolled_back=True,
            )

        return MigrationResult(
            success=True,
            migrated_count=count,
            final_data=current,
            backed_up_paths=[backup_path],
        )

    def _create_backup(self, store: str, data: dict, version: int) -> Path:
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self._backup_dir / f"{store}_v{version}_{ts}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return path
```

---

### Phase 2: Config YAML v1 → v2 Migration

**새 파일**: `src/ds_agent/infrastructure/migration/config_migrations.py`

```python
def migrate_config_v1_to_v2(data: dict) -> dict:
    """
    v1 → v2: api_keys 필드를 config에서 제거.
    api_keys는 P0-02 SecretStoragePort로 이미 이전됨.
    이 migration은 config.yaml에서 api_keys 필드를 제거하는 것만 담당.
    """
    result = deepcopy(data)
    if "provider" in result and "api_keys" in result["provider"]:
        # api_keys가 아직 config에 남아있다면 제거 (이미 secure storage로 이전됐어야 함)
        del result["provider"]["api_keys"]
        logger.info("config_migration_v1_v2", removed_keys=True)
    result["_schema_version"] = 2
    return result
```

---

### Phase 3: 앱 시작 시 자동 Migration 실행

**수정 파일**: `src/ds_agent/config/loader.py`

```python
def load_config(config_path: Path | None = None) -> DSAgentConfig:
    """Load config with automatic migration."""
    resolved_path = config_path or get_default_config_path()

    data: dict = {}
    if resolved_path.exists():
        with open(resolved_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    # Migration 실행
    runner = MigrationRunner(migrations=CONFIG_MIGRATIONS)
    result = runner.run_for_store("config", data)

    if not result.success:
        logger.warning("config_migration_failed", errors=result.errors)
        # safe mode: 기본값으로 진행
        data = {}
    elif result.migrated_count > 0:
        # Migration 적용됨 → 파일 업데이트
        save_raw_config(result.final_data, resolved_path)
        data = result.final_data
    else:
        data = result.final_data

    return DSAgentConfig(**{k: v for k, v in data.items() if not k.startswith("_")})
```

---

### Phase 4: SQLite Schema Migration

Session DB가 SQLite이므로 Alembic 또는 자체 버전 테이블 사용.

**새 파일**: `src/ds_agent/infrastructure/migration/session_db_migrations.py`

```python
SESSION_DB_MIGRATIONS = [
    DbMigration(
        version=2,
        sql="""
        ALTER TABLE sessions ADD COLUMN workspace_id TEXT;
        ALTER TABLE sessions ADD COLUMN tags TEXT DEFAULT '[]';
        """,
        description="Add workspace_id and tags to sessions",
    ),
]

class SessionDbMigrator:
    def run(self, db_path: Path) -> MigrationResult:
        conn = sqlite3.connect(db_path)
        current = self._get_schema_version(conn)
        # 순차 적용
        ...

    def _get_schema_version(self, conn) -> int:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _schema_version
            (version INTEGER NOT NULL, applied_at TEXT)
        """)
        row = conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()
        return row[0] or 1
```

---

### Phase 5: Migration 결과 UI 표시

성공한 migration은 조용히 처리, 실패 시 사용자에게 알림.

**Electron IPC**: `migration:result` 이벤트

```typescript
// main process → renderer
ipcMain.handle('migration:get-result', async () => {
  return getMigrationResult(); // 시작 시 수집해둔 결과
});

// renderer: SettingsPanel 또는 startup 시 알림
if (migrationResult.errors.length > 0) {
  showNotification({
    type: 'warning',
    title: '설정 파일 업그레이드 중 문제가 발생했습니다',
    message: '일부 설정이 기본값으로 초기화됐습니다.',
    action: { label: '백업 파일 열기', fn: openBackupDir },
  });
}
```

---

## Quality Gate

- [x] 구버전 config.yaml (v1)으로 신버전 앱 정상 시작 확인
- [x] Migration 전 자동 백업 생성 확인
- [x] Migration 실패 시 데이터 유실 없이 원본 복원 확인
- [x] idempotent 테스트 (같은 migration 두 번 실행해도 동일 결과)
- [ ] SQLite schema migration 테스트 (v1 → v2 세션 DB)
- [ ] auth_profiles v1(평문) → v2(secret_ref) migration 확인 (P0-02 연동)

## 향후 Migration 추가 지침

새 migration 추가 시:
1. `from_version`, `to_version` 명시
2. `migrate` 함수는 순수 함수 (side effect 없음)
3. `idempotent` 보장 (같은 입력 → 같은 출력)
4. `tests/unit/application/test_migration_runner.py` 에 테스트 케이스 추가
