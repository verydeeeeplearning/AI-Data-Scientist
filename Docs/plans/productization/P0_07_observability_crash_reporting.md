# P0-07: 관찰 가능성 & 크래시 리포팅

**우선순위**: P0 — 베타 배포 차단 조건
**요구사항 섹션**: 5.13
**상태**: Complete (코드 측 — DSN/인프라 조달 후 활성화)
**의존성**: P0-03 (진단 정보 수집 기반)
**최근 감사일**: 2026-04-15 (재감사 후 정정 — 초기 감사가 실재 구현을 누락했음)

---

## 개요

제품은 버그 없이 출시되지 않는다. 중요한 것은 "버그가 생겼을 때 지원 가능한가"다.

현재:
- structlog 기반 로그는 존재 (`src/ds_agent/`)
- runtime event log 존재
- **크래시 리포팅 없음** — 지원팀이 사용자 문제를 재현 불가
- **support bundle 없음** — 사용자 1클릭으로 진단 정보 내보내기 불가
- **에러 코드 체계 없음** — "오류가 발생했습니다" 수준

---

## 현재 구현 상태 (2026-04-15 재감사 — 정정)

> ⚠️ 직전 감사(2026-04-15 1차) 가 잘못된 결론을 냈음. 실제 코드를 다시 읽어보니
> Sentry, telemetry consent UX, 에러 코드 카탈로그 모두 통합 완료 상태.
> 활성화에 필요한 것은 외부 결정 (DSN, environment) 뿐.

완료 (a: support bundle 트랙):
- `SupportBundleExporter` 추가: 설정, 상태 스냅샷, 시스템 정보, 버전 정보, migration 상태, runtime 로그를 redaction 후 ZIP으로 export
- `POST /api/support/bundle` HTTP 엔드포인트 추가
- Electron IPC `support:exportBundle` 및 Settings > Support UI 추가
- 자동 검증 추가: support bundle 내 secret 미포함 단위 테스트와 API route 테스트

완료 (b: crash reporting 트랙):
- **Backend**: `src/ds_agent/infrastructure/observability/sentry_backend.py`
  - Sentry SDK 통합 (`sentry_sdk`, `FastApiIntegration`, `LoggingIntegration`)
  - `_state` 머신: `dsn`, `environment`, `error_reporting_enabled`, `telemetry_enabled`
  - `before_send` redaction (secret field tokens + regex 패턴: anthropic key, OpenAI key,
    Google OAuth, Telegram bot token 등 6개 카테고리)
- **Config schema**: `ObservabilityConfig` (`config/schema.py:126`) —
  `sentry_dsn`, `sentry_environment`, `telemetry_enabled`, `error_reporting_enabled`
- **Migration**: `migrate_config_v3_to_v4` 가 신규 배포에 observability 기본값 자동 주입
- **Env override**: `DS_AGENT_SENTRY_DSN` 환경변수로 DSN 런타임 주입 가능
  (`config/loader.py:107`)
- **Electron main**: `electron/src/main/observability.ts` 가 `@sentry/electron/main`
  통합 (renderer + main + native crash 모두 커버)
- **활성화 조건**: DSN 만 설정되면 자동 init. DSN 없으면 silent no-op (개발 환경 안전)

완료 (c: 에러 코드 카탈로그):
- `src/ds_agent/api/error_mapping.py` — 도메인별 에러 코드 매핑
  (DSA-SYS-*, DSA-LLM-*, DSA-SAND-*, DSA-FILE-*, DSA-AUTH-*)
- `present_rpc_exception()` 이 RPC 예외를 catalog code + 사용자 메시지 + technical
  message + warnings 로 변환하여 UI 에 전달
- 사용처: `connector.test` 등 모든 RPC 핸들러에서 일관 사용

완료 (telemetry consent UX):
- `OnboardingWizard.tsx` 의 ObservabilityChoice 단계 — 3가지 선택지 노출:
  `none` / `crash_only` / `crash_and_telemetry`
- 결과가 `errorReportingEnabled` + `telemetryEnabled` 로 분리되어 config 에 저장
- IPC `observability:setConsent` (`ipc.ts:308`) — Electron main 상태와 backend config
  양쪽에 즉시 반영

남은 항목 (외부 결정/조달):
- Sentry DSN 발급 + environment 명명 규약 (production/beta/dev) — 운영 결정
- Sentry 프로젝트 분리 정책 (단일 프로젝트 vs CLI/Electron 분리) — 운영 결정

---

## 구현 Phase 계획

### Phase 1: Sentry 크래시 리포팅 통합

#### Python Backend

**수정 파일**: `src/ds_agent/api/app.py` (또는 main 진입점)

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

def init_sentry(dsn: str | None, environment: str = "production") -> None:
    if not dsn:
        return  # DSN 없으면 비활성화 (개발 환경)

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=0.1,           # 10% 성능 추적
        profiles_sample_rate=0.05,        # 5% 프로파일링
        before_send=redact_secrets,       # secret 제거
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=logging.ERROR),
        ],
    )

def redact_secrets(event: dict, hint: dict) -> dict:
    """Sentry 이벤트에서 secret 제거."""
    if "extra" in event:
        for key in list(event["extra"].keys()):
            if any(s in key.lower() for s in ["key", "token", "secret", "password"]):
                event["extra"][key] = "***REDACTED***"
    return event
```

**수정 파일**: `src/ds_agent/config/schema.py`

```python
class ObservabilityConfig(BaseModel):
    sentry_dsn: str | None = None        # 환경변수 또는 config로 설정
    sentry_environment: str = "production"
    telemetry_enabled: bool = False      # opt-in 기본값
    error_reporting_enabled: bool = True
```

#### Electron Renderer

**수정 파일**: `electron/src/renderer/main.tsx`

```typescript
import * as Sentry from '@sentry/electron/renderer';

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  environment: import.meta.env.MODE,
  beforeSend(event) {
    // 사용자 개인정보 제거
    delete event.user?.email;
    delete event.user?.username;
    return event;
  },
});
```

**수정 파일**: `electron/src/main/index.ts`

```typescript
import * as Sentry from '@sentry/electron/main';

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  onFatalError: (err) => {
    // 크래시 직전 진단 정보 저장
    collectAndSaveDiagnostics(err);
  },
});
```

---

### Phase 2: Error Code 체계

**새 파일**: `src/ds_agent/domain/errors/error_catalog.py`

```python
"""
DS Agent Error Code Catalog.
Format: DSA-{CATEGORY}-{NUMBER}

Categories:
  AUTH  — 인증/자격증명
  TOOL  — tool 실행
  LLM   — LLM provider
  FILE  — 파일/데이터
  SYS   — 시스템
  SAND  — 샌드박스
"""

@dataclass(frozen=True)
class ErrorCode:
    code: str
    user_message: str      # 비개발자용 메시지
    support_message: str   # 지원팀용 메시지
    recovery_hint: str     # 복구 방법

ERROR_CATALOG: dict[str, ErrorCode] = {
    "DSA-AUTH-001": ErrorCode(
        code="DSA-AUTH-001",
        user_message="API 키가 유효하지 않습니다. 설정에서 API 키를 확인하세요.",
        support_message="LLM provider API key validation failed (401)",
        recovery_hint="설정 → API 키 → 재입력",
    ),
    "DSA-AUTH-002": ErrorCode(
        code="DSA-AUTH-002",
        user_message="Google 로그인 세션이 만료됐습니다. 다시 로그인이 필요합니다.",
        support_message="OAuth token refresh failed",
        recovery_hint="설정 → 연결된 계정 → 재인증",
    ),
    "DSA-TOOL-001": ErrorCode(
        code="DSA-TOOL-001",
        user_message="코드 실행 중 오류가 발생했습니다.",
        support_message="execute_code tool raised exception",
        recovery_hint="다른 방식으로 분석을 요청해보세요.",
    ),
    "DSA-SAND-001": ErrorCode(
        code="DSA-SAND-001",
        user_message="코드가 허용되지 않은 파일에 접근하려 했습니다. 보안상 차단됐습니다.",
        support_message="Sandbox filesystem violation",
        recovery_hint="Agent에게 workspace 경로 내 파일만 사용하도록 요청하세요.",
    ),
    "DSA-FILE-001": ErrorCode(
        code="DSA-FILE-001",
        user_message="파일을 읽을 수 없습니다. 파일 형식이나 인코딩을 확인하세요.",
        support_message="File read failed — encoding or format error",
        recovery_hint="CSV는 UTF-8, Excel은 .xlsx 형식을 권장합니다.",
    ),
    "DSA-LLM-001": ErrorCode(
        code="DSA-LLM-001",
        user_message="AI 서비스에 일시적인 문제가 있습니다. 잠시 후 다시 시도하세요.",
        support_message="LLM provider 5xx error or network timeout",
        recovery_hint="1-2분 후 재시도하거나 다른 모델을 선택하세요.",
    ),
    "DSA-LLM-002": ErrorCode(
        code="DSA-LLM-002",
        user_message="이번 달 사용 한도에 도달했습니다.",
        support_message="LLM provider rate limit or quota exceeded",
        recovery_hint="설정 → 비용 → 한도 조정, 또는 다른 provider 사용",
    ),
}
```

**사용 예시**:
```python
# tool 실행 시
raise DSAgentError(
    error_code="DSA-TOOL-001",
    original_error=e,
)

# LLM 호출 시
except RateLimitError:
    raise DSAgentError(error_code="DSA-LLM-002")
```

---

### Phase 3: Support Bundle Exporter

**새 파일**: `src/ds_agent/infrastructure/support/bundle_exporter.py`

```python
class SupportBundleExporter:
    """사용자 1클릭 → 진단 정보 ZIP 생성."""

    def __init__(self, config: DSAgentConfig, secrets: SecretStoragePort) -> None:
        self._config = config
        self._secrets = secrets

    def export(self, output_path: Path) -> Path:
        """진단 정보를 ZIP 파일로 내보냄. secret은 자동 redaction."""
        bundle_dir = output_path / f"ds-agent-support-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        bundle_dir.mkdir(parents=True)

        # 1. 시스템 정보
        self._write_system_info(bundle_dir / "system_info.json")

        # 2. 앱 버전 정보
        self._write_version_info(bundle_dir / "version.json")

        # 3. 설정 (secret redacted)
        self._write_redacted_config(bundle_dir / "config.yaml")

        # 4. 최근 로그 (secret redacted)
        self._write_redacted_logs(bundle_dir / "logs/")

        # 5. Runtime event log (최근 100개)
        self._write_event_log(bundle_dir / "event_log.jsonl")

        # 6. Migration 상태
        self._write_migration_state(bundle_dir / "migration_state.json")

        # ZIP 압축
        zip_path = output_path / f"{bundle_dir.name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in bundle_dir.rglob("*"):
                zf.write(file, file.relative_to(output_path))

        shutil.rmtree(bundle_dir)
        return zip_path

    def _write_redacted_config(self, path: Path) -> None:
        config_dict = self._config.model_dump()
        # api_keys, token 관련 필드 redact
        config_dict = self._deep_redact(config_dict)
        path.write_text(yaml.dump(config_dict))

    def _deep_redact(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: "***REDACTED***" if any(s in k.lower() for s in ["key", "token", "secret"])
                else self._deep_redact(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self._deep_redact(v) for v in obj]
        return obj

    def _write_system_info(self, path: Path) -> None:
        import platform
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "python_version": platform.python_version(),
            "arch": platform.machine(),
            "cpu_count": os.cpu_count(),
            "memory_gb": round(psutil.virtual_memory().total / 1e9, 1),
        }
        path.write_text(json.dumps(info, indent=2))
```

---

### Phase 4: Electron "지원팀에 보내기" UI

**새 파일**: `electron/src/renderer/components/settings/SupportPanel.tsx`

```tsx
export function SupportPanel() {
  const [exporting, setExporting] = useState(false);
  const [exportPath, setExportPath] = useState<string | null>(null);

  const handleExport = async () => {
    setExporting(true);
    try {
      const path = await window.dsAgent.exportSupportBundle();
      setExportPath(path);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="support-panel">
      <h3>문제 해결 지원</h3>
      <p className="text-muted">
        진단 정보를 내보내 지원팀에 전달하면 빠른 해결에 도움이 됩니다.
        API 키 등 민감 정보는 자동으로 제외됩니다.
      </p>

      <Button onClick={handleExport} loading={exporting}>
        {exporting ? '수집 중...' : '진단 정보 내보내기'}
      </Button>

      {exportPath && (
        <div className="export-success">
          <CheckIcon />
          <span>저장됨: {exportPath}</span>
          <Button variant="ghost" onClick={() => openInExplorer(exportPath)}>
            폴더 열기
          </Button>
        </div>
      )}

      <div className="support-links">
        <a href="https://ds-agent.app/support">지원 문의</a>
        <a href="https://github.com/org/ds-agent/issues">GitHub Issues</a>
      </div>
    </div>
  );
}
```

**IPC 등록** (`electron/src/main/ipc-handlers.ts`):

```typescript
ipcMain.handle('support:export-bundle', async () => {
  const { filePath } = await dialog.showSaveDialog({
    defaultPath: `ds-agent-support-${Date.now()}.zip`,
    filters: [{ name: 'ZIP', extensions: ['zip'] }],
  });
  if (!filePath) return null;

  // Python backend API 호출
  const resp = await fetch(`http://localhost:${backendPort}/api/support/bundle`, {
    method: 'POST',
    body: JSON.stringify({ output_path: filePath }),
  });
  return (await resp.json()).path;
});
```

---

### Phase 5: Telemetry Opt-in UI

**원칙**: 기본값은 opt-out. 첫 실행 온보딩에서 동의 여부 묻기.

**새 파일**: `electron/src/renderer/components/onboarding/TelemetryConsent.tsx`

```tsx
export function TelemetryConsent({ onAccept, onDecline }: Props) {
  return (
    <div className="telemetry-consent">
      <h3>서비스 개선 참여</h3>
      <p>
        앱 사용 중 발생하는 오류 정보를 익명으로 수집하면
        더 빠른 버그 수정에 도움이 됩니다.
        <strong>개인 데이터, 분석 내용, API 키는 전혀 수집되지 않습니다.</strong>
      </p>
      <div className="actions">
        <Button variant="primary" onClick={onAccept}>참여할게요</Button>
        <Button variant="ghost" onClick={onDecline}>괜찮아요</Button>
      </div>
      <small>언제든 설정 → 개인정보에서 변경할 수 있습니다.</small>
    </div>
  );
}
```

---

## Quality Gate

- [ ] Python 예외가 Sentry에 자동 수집됨 (staging DSN 테스트)
- [ ] Electron renderer 크래시가 Sentry에 자동 수집됨
- [x] Support bundle ZIP에 secret 원문 없음 (자동 검증)
- [x] 지원팀이 bundle만으로 OS, 앱 버전, 최근 오류 파악 가능
- [ ] 에러 코드 체계 - 사용자 메시지에 DSA-XXX-YYY 코드 표시
- [ ] Telemetry opt-in/opt-out 설정 반영 확인
- [x] `test_support_bundle_no_secrets.py` 자동 테스트 통과
