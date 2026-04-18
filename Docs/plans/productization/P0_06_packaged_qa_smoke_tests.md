# P0-06: 패키지 QA & 스모크 테스트

**우선순위**: P0 — 베타 배포 차단 조건
**요구사항 섹션**: 5.14
**상태**: In Progress (Phase 1 + 4 + 5 + Electron diagnostic smoke 완료 · 서명 binary 대상 full E2E 만 잔존, P0-05 의존)
**의존성**: P0-05 (서명된 installer 필요 — Phase 2/3 에 한정)

---

## 구현 현황 (2026-04-14)

### 완료
- **Phase 1 Backend Binary Smoke** (`tests/smoke/`)
  - `conftest.py`: `PACKAGED_BINARY_PATH` env 또는 `dist/ds-agent-backend/ds-agent-api(.exe)`
    자동 탐지. spawn → `READY:` 신호 대기 (timeout 30s) → cleanup. stderr drainer 스레드.
    바이너리 미존재 시 `pytest.skip` (개발자 경험 보호).
  - `test_backend_binary.py` (5 cases):
    - `/health` 200 + `{status: "ok"}`
    - `/api/status` 스키마 (`model`/`mode`/`activeSessions`)
    - `/api/config` 도달성 (200/401/403 허용)
    - stderr `ImportError` / `ModuleNotFoundError` / `DLL load failed` 부재
    - 프로세스 생존 검증
- **Phase 4 CI** (`.github/workflows/smoke.yml`)
  - PR/main push 마다 Windows runner 에서 PyInstaller 빌드 → smoke suite 실행.
    실패 시 stderr / `_internal/` 로그 artifact 업로드.
- **Phase 5 회귀 매트릭스** (`tests/smoke/REGRESSION_MATRIX.md`)
  - 13 항목 critical user journey 체크리스트 + 자동화 상태 표시.
- **로컬 헬퍼** (`scripts/run_smoke.py`)
  - `--build` 옵션으로 백엔드 빌드 + smoke 실행 원샷.
- **README** (`tests/smoke/README.md`) — 사용법 / CI 안내.
- **검증**: 기존 `dist/ds-agent-backend/ds-agent-api.exe` 기준 5/5 green.

### Phase 2/3 (Electron Playwright) 부분 완료 (2026-04-15)
- **완료**: `electron/tests/smoke/diagnostic-window.spec.ts` — backend startup 실패 시
  P0-03 diagnostic window 가 분류된 reason ("Backend binary was not found") 으로 표출되는지
  검증. `npm run test:e2e:smoke` 로 실행. 빌드된 renderer + 강제 실패 백엔드 명령으로
  Vite/Python 의존 없이 동작.
- 추가된 product hooks (운영에도 유용):
  - `DS_AGENT_BACKEND_COMMAND` / `DS_AGENT_BACKEND_ARGS` — 백엔드 명령 오버라이드
  - `DS_AGENT_E2E_USE_BUILT_RENDERER=1` — Vite dev server 없이 build 결과물 로드
- **잔존 (P0-05 의존)**: 서명된 installer 대상 clean install → 온보딩 → 샘플 분석 →
  세션 복원 등 happy path E2E. 회귀 매트릭스 #6, #7, #11 해당.

---

---

## 개요

소스 기반 테스트(현재 263개)는 패키지된 제품을 보장하지 않는다.
PyInstaller 번들링 실패, 누락된 리소스, 경로 하드코딩, DLL 충돌 등은
소스 레벨 테스트에서 잡히지 않는다.

**목표**: 패키지된 앱 기준으로 critical user journey를 자동/반자동 검증.

---

## 테스트 계층

```
Level 1: Binary smoke test     — 백엔드 바이너리 단독 실행 가능 여부
Level 2: API smoke test        — 백엔드 HTTP 엔드포인트 응답 여부
Level 3: Installer test        — installer 설치 → 앱 실행 → 기본 동작
Level 4: E2E user journey      — Playwright로 완전한 사용자 흐름
Level 5: Upgrade test          — N-1 → N 버전 업그레이드 후 데이터 보존
```

---

## 구현 Phase 계획

### Phase 1: Backend Binary Smoke Test

**새 파일**: `tests/smoke/test_backend_binary.py`

```python
"""
패키지된 ds-agent-api 바이너리 기준 스모크 테스트.
CI에서 PACKAGED_BINARY_PATH 환경변수로 바이너리 경로 전달.
"""
import subprocess, os, time, requests

BINARY = os.environ.get("PACKAGED_BINARY_PATH", "dist/ds-agent-api")

@pytest.fixture(scope="module")
def running_backend():
    port = 19999
    proc = subprocess.Popen(
        [BINARY, "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # READY 신호 대기 (최대 30초)
    deadline = time.time() + 30
    while time.time() < deadline:
        line = proc.stdout.readline().decode()
        if f"READY:{port}" in line:
            break
    else:
        proc.kill()
        pytest.fail("Backend did not emit READY signal within 30s")
    yield f"http://localhost:{port}", proc
    proc.terminate()

def test_health_endpoint(running_backend):
    base_url, _ = running_backend
    resp = requests.get(f"{base_url}/health", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"

def test_version_endpoint(running_backend):
    base_url, _ = running_backend
    resp = requests.get(f"{base_url}/version", timeout=5)
    assert resp.status_code == 200
    assert "version" in resp.json()

def test_chat_endpoint_responds(running_backend):
    base_url, _ = running_backend
    resp = requests.post(
        f"{base_url}/api/chat",
        json={"message": "ping", "mode": "auto"},
        timeout=10,
    )
    # 200 또는 auth error (401) 허용 — 바이너리가 살아있다는 것만 확인
    assert resp.status_code in (200, 401, 422)

def test_imports_all_present(running_backend):
    """패키지에 필수 모듈이 포함됐는지 확인 (백엔드 시작 자체가 검증)"""
    base_url, proc = running_backend
    # stderr에 ImportError가 없어야 함
    # proc.stderr는 non-blocking read 필요
    assert "ImportError" not in proc.stderr.read1(1024).decode()
    assert "ModuleNotFoundError" not in proc.stderr.read1(1024).decode()
```

---

### Phase 2: Electron App E2E (Playwright)

**새 파일**: `tests/e2e/test_app_startup.spec.ts`

```typescript
import { test, expect, _electron as electron } from '@playwright/test';
import path from 'path';

const APP_PATH = process.env.PACKAGED_APP_PATH
  ?? path.join(__dirname, '../../electron/dist/win-unpacked/DS Agent.exe');

test.describe('App Startup', () => {
  test('app launches and shows onboarding or main screen', async () => {
    const app = await electron.launch({ args: [APP_PATH] });
    const page = await app.firstWindow();

    // 30초 내 로딩 완료
    await page.waitForLoadState('domcontentloaded', { timeout: 30_000 });

    // 빈 화면이 아니어야 함
    const title = await page.title();
    expect(title).toBeTruthy();

    // DiagnosticPanel이 표시되지 않아야 함 (백엔드 정상 시작)
    const diagnosticPanel = page.locator('[data-testid="diagnostic-panel"]');
    await expect(diagnosticPanel).not.toBeVisible({ timeout: 5_000 });

    await app.close();
  });

  test('disconnect overlay disappears after reconnect', async () => {
    const app = await electron.launch({ args: [APP_PATH] });
    const page = await app.firstWindow();
    await page.waitForLoadState('domcontentloaded');

    // 초기에 연결 완료 상태여야 함
    const overlay = page.locator('[data-testid="disconnect-overlay"]');
    await expect(overlay).not.toBeVisible({ timeout: 15_000 });

    await app.close();
  });
});
```

**새 파일**: `tests/e2e/test_first_run.spec.ts`

```typescript
test.describe('First Run (Clean State)', () => {
  let tempDir: string;

  test.beforeEach(async () => {
    // 새 임시 디렉토리 → 완전한 첫 실행 시뮬레이션
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ds-agent-test-'));
  });

  test.afterEach(async () => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  test('onboarding screen appears on first launch', async () => {
    const app = await electron.launch({
      args: [APP_PATH],
      env: { ...process.env, DS_AGENT_HOME: tempDir },
    });
    const page = await app.firstWindow();
    await page.waitForLoadState('domcontentloaded', { timeout: 30_000 });

    // 온보딩 화면이 표시되어야 함
    const onboarding = page.locator('[data-testid="onboarding-wizard"]');
    await expect(onboarding).toBeVisible({ timeout: 10_000 });

    await app.close();
  });

  test('can complete onboarding with demo mode', async () => {
    const app = await electron.launch({
      args: [APP_PATH],
      env: { ...process.env, DS_AGENT_HOME: tempDir },
    });
    const page = await app.firstWindow();
    await page.waitForLoadState('domcontentloaded', { timeout: 30_000 });

    // "데모 모드로 시작" 버튼 클릭
    await page.click('[data-testid="demo-mode-btn"]');

    // 메인 채팅 화면으로 전환 확인
    await expect(page.locator('[data-testid="chat-input"]')).toBeVisible({
      timeout: 15_000,
    });

    await app.close();
  });
});
```

---

### Phase 3: Upgrade Test

**새 파일**: `tests/e2e/test_upgrade.spec.ts`

```typescript
test.describe('Upgrade from N-1 to N', () => {
  test('user data preserved after upgrade', async () => {
    const userHome = fs.mkdtempSync(path.join(os.tmpdir(), 'ds-agent-upgrade-'));

    // 1. N-1 버전으로 첫 실행 (시뮬레이션: 구버전 config 파일 생성)
    const oldConfig = {
      _schema_version: 1,
      provider: {
        default_model: 'anthropic/claude-sonnet-4-6',
        api_keys: {},  // v1 형식
      },
    };
    fs.writeFileSync(
      path.join(userHome, 'config.yaml'),
      yaml.dump(oldConfig),
    );

    // 2. 신버전 앱 실행
    const app = await electron.launch({
      args: [APP_PATH],
      env: { ...process.env, DS_AGENT_HOME: userHome },
    });
    const page = await app.firstWindow();
    await page.waitForLoadState('domcontentloaded', { timeout: 30_000 });

    // 3. 앱이 정상 로드됐는지 확인 (오류 화면 아님)
    await expect(page.locator('[data-testid="diagnostic-panel"]')).not.toBeVisible();

    // 4. config.yaml이 v2로 업그레이드됐는지 확인
    const updatedConfig = yaml.load(
      fs.readFileSync(path.join(userHome, 'config.yaml'), 'utf-8')
    ) as any;
    expect(updatedConfig._schema_version).toBe(2);
    expect(updatedConfig.provider?.api_keys).toBeUndefined();

    await app.close();
    fs.rmSync(userHome, { recursive: true, force: true });
  });
});
```

---

### Phase 4: CI 통합

**수정 파일**: `.github/workflows/build-release.yml` (Phase P0-05에서 이어서)

```yaml
  smoke-test-windows:
    needs: build-windows
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with: { name: windows-installer }

      - name: Install app
        run: |
          Start-Process -Wait -FilePath "ds-agent-setup.exe" -ArgumentList "/S"

      - name: Run backend smoke tests
        env:
          PACKAGED_BINARY_PATH: "C:/Users/runneradmin/AppData/Local/Programs/ds-agent/ds-agent-api.exe"
        run: |
          pip install pytest requests
          pytest tests/smoke/test_backend_binary.py -v

      - name: Run Electron E2E
        env:
          PACKAGED_APP_PATH: "C:/Users/runneradmin/AppData/Local/Programs/ds-agent/DS Agent.exe"
        run: |
          cd electron
          npm ci
          npx playwright install
          npx playwright test tests/e2e/ --reporter=html

      - name: Upload E2E report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: e2e-report
          path: electron/playwright-report/
```

---

### Phase 5: 회귀 테스트 매트릭스

**새 파일**: `tests/smoke/REGRESSION_MATRIX.md`

```markdown
## Critical User Journey 체크리스트 (릴리스 전 반드시 확인)

| # | 시나리오 | 자동화 | 확인 |
|---|---------|--------|------|
| 1 | Clean install → 앱 실행 | ✅ E2E | [ ] |
| 2 | First run → 온보딩 화면 표시 | ✅ E2E | [ ] |
| 3 | Demo 모드로 온보딩 완료 | ✅ E2E | [ ] |
| 4 | API key 입력 → 인증 성공 | ✅ E2E | [ ] |
| 5 | CSV 파일 업로드 | ✅ E2E | [ ] |
| 6 | 분석 요청 → Agent 응답 | ✅ E2E | [ ] |
| 7 | 앱 재시작 → 세션 복원 | ✅ E2E | [ ] |
| 8 | v1 config → v2 migration | ✅ E2E | [ ] |
| 9 | Uninstall → 바이너리 삭제 확인 | 수동 | [ ] |
| 10 | AV 환경에서 설치/실행 | 수동 | [ ] |
```

---

## Quality Gate

- [ ] Backend binary smoke test: health, version, chat 엔드포인트 통과
- [ ] First-run E2E: 온보딩 화면 표시 확인
- [ ] Demo mode E2E: 온보딩 완료 후 채팅 화면 전환 확인
- [ ] Upgrade E2E: v1 config → v2 migration 확인
- [ ] CI에서 자동 실행 (릴리스 draft 생성 전 gate)
- [ ] E2E 결과 리포트 artifact 저장
- [ ] 회귀 매트릭스 10개 항목 모두 확인
