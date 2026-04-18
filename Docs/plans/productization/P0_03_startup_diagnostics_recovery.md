# P0-03: 시작 진단 및 복구

**우선순위**: P0 — 베타 배포 차단 조건
**요구사항 섹션**: 5.8
**상태**: Complete
**의존성**: 없음

---

## Implementation Update (2026-04-14)

Implemented in this iteration:

- `electron/src/main/python-backend.ts`
  - Added startup preflight checks for packaged binary presence and executable access.
  - Added structured startup result typing with classified failure reasons.
  - Added startup health verification via `GET /health` after the `READY:<port>:<token>` handshake.
  - Added automatic free-port fallback and bounded retry handling for startup failures.
- `electron/src/main/index.ts`
  - Startup no longer falls through to the main app window when the backend fails.
  - Backend failure now opens a dedicated diagnostics surface instead of continuing with a broken session.
- `electron/src/main/window.ts`
  - Added diagnostic-window routing with serialized startup diagnostics.
- `electron/src/renderer/App.tsx`
  - Added diagnostic screen boot path that bypasses WebSocket app initialization.
- `electron/src/renderer/components/diagnostic/DiagnosticPanel.tsx`
  - Added a renderer-side startup diagnostics UI with reason-specific guidance, environment summary, and copyable technical details.
  - Added startup support-bundle export from the diagnostics screen.
- `electron/src/renderer/hooks/useWebSocket.ts`
  - Added disconnect-reason classification for post-connect failures.
  - Added backend `/health` probing to distinguish probable backend crashes from plain WebSocket closure.
  - Added reconnect-state tracking so the renderer can show recovery-specific messaging instead of a generic disconnect banner.
- `electron/src/renderer/components/layout/DisconnectOverlay.tsx`
  - Added reason-aware copy for `reconnecting`, `ws_closed`, `backend_crashed`, and `network_error`.
- `electron/src/renderer/App.tsx` and `electron/src/renderer/hooks/useChat.ts`
  - Wired classified disconnect reasons from the shared WebSocket provider into the renderer overlay path.
- `electron/src/main/diagnostics-collector.ts`
  - Added support-bundle assembly with sanitized startup diagnostics, config snapshot, runtime-event tail, path inventory, and recent Electron main-process logs.
- `electron/src/main/ipc.ts`, `electron/src/preload/index.ts`
  - Added Electron IPC for saving a support bundle to disk from the renderer.

Implemented to close the remaining gap:

- `electron/src/renderer/components/diagnostic/DiagnosticPanel.tsx`
  - Added guided recovery steps tailored per startup failure reason.
  - Added direct actions to reveal the backend location, open the logs folder, and copy the recovery plan.
- `electron/src/main/ipc.ts`, `electron/src/preload/index.ts`
  - Added shell-reveal support so the diagnostic UI can take the operator directly to the relevant local paths.
- `electron/src/main/python-backend.ts`
  - Added startup diagnostics fields for app/log locations and richer main-process diagnostic logging.

Non-blocking follow-up ideas:

- ZIP packaging or multi-file attachment packaging for support handoff convenience

## 개요

현재 Electron 앱 시작 흐름은 backend spawn 실패 시 `console.error`만 출력하고
앱은 계속 로드된다. 사용자는 빈 화면이나 연결 오류만 보게 된다.

**현재 `index.ts` 문제**:
```typescript
} catch (err) {
  console.error('[main] Failed to start backend:', err);
  // Continue anyway — user can start backend manually  ← 비개발자 불가
}
```

**현재 `DisconnectOverlay.tsx` 문제**:
- 'connecting' / 'disconnected' 두 상태만 있음
- 연결 실패 원인(binary 없음 / port 충돌 / crash / timeout)을 구분하지 않음

**목표**:
- Backend 시작 실패 원인을 분류하고 사용자가 이해할 수 있는 진단 UI 표시
- 복구 가능한 문제(port 충돌)는 자동 복구
- 복구 불가 시 진단 정보 + 지원 채널 안내

---

## 현재 코드 분석

### python-backend.ts 현재 흐름

```typescript
// 현재 시작 로직
MAX_RESTARTS = 3          // 최대 재시작 횟수
timeout = 30초            // READY 신호 대기
READY:<port> 신호로 포트 확인
```

**누락된 것**:
- binary 파일 존재 여부 사전 확인
- port 충돌 감지 및 자동 재시도
- crash 원인 분류 (binary 없음 / 권한 없음 / 포트 충돌 / Python 오류)
- MAX_RESTARTS 초과 후 진단 정보 수집

---

## 아키텍처 설계

### 진단 흐름도

```
app.whenReady()
     │
     ▼
StartupHealthManager.run()
     │
     ├─ 1. PreflightCheck
     │   ├─ binary 존재 여부 확인
     │   ├─ binary 실행 권한 확인
     │   └─ port 사용 가능 여부 확인
     │       └─ [포트 충돌] → 다음 가용 포트로 자동 전환
     │
     ├─ 2. BackendSpawn
     │   ├─ spawn python-backend
     │   ├─ 30초 내 READY:<port> 대기
     │   └─ 실패 시 stderr 캡처 → 원인 분류
     │
     ├─ 3. HealthCheck
     │   ├─ HTTP GET /health endpoint 호출
     │   └─ WebSocket 연결 가능 여부 확인
     │
     └─ 성공 → createMainWindow()
         실패 → DiagnosticPanel 표시
```

### 실패 원인 분류 (StartupFailureReason)

```typescript
enum StartupFailureReason {
  BINARY_NOT_FOUND        = "binary_not_found",       // 바이너리 파일 없음
  BINARY_PERMISSION_DENIED = "binary_permission_denied", // 실행 권한 없음
  PORT_IN_USE             = "port_in_use",            // 포트 이미 사용 중
  PYTHON_ERROR            = "python_error",           // Python 예외 발생
  TIMEOUT                 = "startup_timeout",        // 30초 내 READY 없음
  ANTIVIRUS_BLOCKED       = "antivirus_blocked",      // AV가 실행 차단
  CRASH_LOOP              = "crash_loop",             // MAX_RESTARTS 초과
  HEALTH_CHECK_FAILED     = "health_check_failed",    // 포트 열렸으나 응답 없음
}
```

---

## 구현 Phase 계획 (TDD)

### Phase 1: PreflightCheck 모듈

#### RED

**파일**: `tests/unit/electron/main/test_preflight_check.ts`

```typescript
describe('PreflightCheck', () => {
  it('detects missing binary', async () => {
    const result = await preflightCheck({ binaryPath: '/nonexistent/path' });
    expect(result.ok).toBe(false);
    expect(result.reason).toBe(StartupFailureReason.BINARY_NOT_FOUND);
  });

  it('detects port conflict and finds next available', async () => {
    // 포트 사용 중 상황 mocking
    const result = await preflightCheck({ port: USED_PORT });
    expect(result.ok).toBe(true);
    expect(result.resolvedPort).not.toBe(USED_PORT);
  });

  it('passes when binary exists and port available', async () => {
    const result = await preflightCheck({ binaryPath: REAL_BINARY, port: FREE_PORT });
    expect(result.ok).toBe(true);
  });
});
```

#### GREEN

**새 파일**: `electron/src/main/preflight-check.ts`

```typescript
import fs from 'fs';
import net from 'net';
import path from 'path';
import { app } from 'electron';

export interface PreflightResult {
  ok: boolean;
  reason?: StartupFailureReason;
  resolvedPort?: number;
  detail?: string;
}

export async function preflightCheck(opts: {
  binaryPath?: string;
  port: number;
}): Promise<PreflightResult> {
  // 1. Binary 존재 확인 (packaged mode)
  if (app.isPackaged && opts.binaryPath) {
    if (!fs.existsSync(opts.binaryPath)) {
      return {
        ok: false,
        reason: StartupFailureReason.BINARY_NOT_FOUND,
        detail: `Binary not found: ${opts.binaryPath}`,
      };
    }
    // 실행 권한 확인 (Unix)
    try {
      fs.accessSync(opts.binaryPath, fs.constants.X_OK);
    } catch {
      return { ok: false, reason: StartupFailureReason.BINARY_PERMISSION_DENIED };
    }
  }

  // 2. Port 가용 여부 확인
  const freePort = await findFreePort(opts.port);
  return { ok: true, resolvedPort: freePort };
}

async function findFreePort(startPort: number, maxAttempts = 10): Promise<number> {
  for (let port = startPort; port < startPort + maxAttempts; port++) {
    if (await isPortFree(port)) return port;
  }
  throw new Error('No free port found');
}

function isPortFree(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => { server.close(); resolve(true); });
    server.listen(port);
  });
}
```

---

### Phase 2: StartupHealthManager

#### RED

**파일**: `tests/integration/electron/main/test_startup_health_manager.ts`

```typescript
it('classifies timeout as STARTUP_TIMEOUT', async () => {
  const manager = new StartupHealthManager({ timeoutMs: 100 });
  const result = await manager.start();
  // backend가 100ms 안에 READY 안 보내는 경우
  expect(result.ok).toBe(false);
  expect(result.reason).toBe(StartupFailureReason.TIMEOUT);
});

it('captures stderr for PYTHON_ERROR classification', async () => {
  // stderr에 "ModuleNotFoundError" 포함 시
  const result = await manager.start();
  expect(result.reason).toBe(StartupFailureReason.PYTHON_ERROR);
  expect(result.stderrSummary).toContain('ModuleNotFoundError');
});
```

#### GREEN

**수정 파일**: `electron/src/main/python-backend.ts`

```typescript
export interface BackendStartResult {
  ok: boolean;
  port?: number;
  token?: string;
  reason?: StartupFailureReason;
  stderrSummary?: string;
  diagnostics?: DiagnosticInfo;
}

export async function startPythonBackend(
  port: number = DEFAULT_PORT
): Promise<BackendStartResult> {
  // 1. Preflight
  const preflight = await preflightCheck({ binaryPath: getBinaryPath(), port });
  if (!preflight.ok) {
    return { ok: false, reason: preflight.reason, detail: preflight.detail };
  }
  const resolvedPort = preflight.resolvedPort!;

  // 2. Spawn
  const spawnResult = await spawnBackend(resolvedPort);
  if (!spawnResult.ok) {
    return {
      ok: false,
      reason: classifySpawnError(spawnResult.stderr),
      stderrSummary: spawnResult.stderr.slice(0, 500),
    };
  }

  // 3. Health check (HTTP + WS)
  const health = await checkHealth(resolvedPort, spawnResult.token);
  if (!health.ok) {
    return { ok: false, reason: StartupFailureReason.HEALTH_CHECK_FAILED };
  }

  return { ok: true, port: resolvedPort, token: spawnResult.token };
}

function classifySpawnError(stderr: string): StartupFailureReason {
  if (stderr.includes('Address already in use')) return StartupFailureReason.PORT_IN_USE;
  if (stderr.includes('Permission denied')) return StartupFailureReason.BINARY_PERMISSION_DENIED;
  if (stderr.includes('ModuleNotFoundError') || stderr.includes('ImportError'))
    return StartupFailureReason.PYTHON_ERROR;
  if (stderr.includes('Access is denied') || stderr.includes('被防病毒'))
    return StartupFailureReason.ANTIVIRUS_BLOCKED;
  return StartupFailureReason.PYTHON_ERROR;
}
```

---

### Phase 3: index.ts 실패 처리 + DiagnosticPanel

#### RED

```typescript
it('shows diagnostic panel on backend failure', async () => {
  // BackendStartResult.ok === false 시
  // window가 DiagnosticPanel URL을 로드해야 함
  expect(win.webContents.getURL()).toContain('diagnostic');
});
```

#### GREEN

**수정 파일**: `electron/src/main/index.ts`

```typescript
app.whenReady().then(async () => {
  const result = await startPythonBackend();

  if (!result.ok) {
    // 실패: DiagnosticPanel 창 열기
    createDiagnosticWindow({
      reason: result.reason!,
      stderrSummary: result.stderrSummary,
      diagnostics: await collectDiagnostics(),
    });
    return;
  }

  createMainWindow(result.port!, result.token!);
});
```

**새 파일**: `electron/src/main/diagnostic-window.ts`

```typescript
export function createDiagnosticWindow(info: DiagnosticInfo): BrowserWindow {
  const win = new BrowserWindow({ width: 520, height: 480, ... });
  // DiagnosticPanel React 컴포넌트 로드
  win.loadURL(`${rendererUrl}#/diagnostic?reason=${info.reason}`);
  return win;
}
```

**새 파일**: `electron/src/renderer/components/diagnostic/DiagnosticPanel.tsx`

```tsx
const REASON_MESSAGES: Record<StartupFailureReason, DiagnosticMessage> = {
  [StartupFailureReason.BINARY_NOT_FOUND]: {
    title: '앱 파일이 손상되었습니다',
    description: '다시 설치하면 해결될 수 있습니다.',
    actions: [
      { label: '재설치 안내 보기', href: 'https://ds-agent.app/reinstall' },
      { label: '진단 정보 복사', action: 'copy-diagnostics' },
    ],
  },
  [StartupFailureReason.ANTIVIRUS_BLOCKED]: {
    title: '보안 프로그램이 앱 실행을 차단했습니다',
    description: 'Windows Defender 또는 보안 소프트웨어가 ds-agent-api.exe를 차단하고 있습니다. 예외 처리가 필요합니다.',
    actions: [
      { label: '예외 처리 방법 보기', href: 'https://ds-agent.app/av-exception' },
      { label: '진단 정보 내보내기', action: 'export-diagnostics' },
    ],
  },
  [StartupFailureReason.PORT_IN_USE]: {
    title: '포트가 이미 사용 중입니다',
    description: '다른 프로그램이 같은 포트를 사용 중입니다. 앱을 재시작하면 자동으로 해결됩니다.',
    actions: [{ label: '앱 재시작', action: 'restart' }],
  },
  // ... 나머지 reason 처리
};

export function DiagnosticPanel({ reason, stderrSummary }: Props) {
  const msg = REASON_MESSAGES[reason];
  return (
    <div className="diagnostic-panel">
      <AlertIcon />
      <h2>{msg.title}</h2>
      <p>{msg.description}</p>
      {/* 오류 코드 (지원팀용) */}
      <code className="error-code">{reason}</code>
      {/* stderr 접을 수 있게 표시 */}
      {stderrSummary && <details><summary>기술 세부 정보</summary><pre>{stderrSummary}</pre></details>}
      <div className="actions">
        {msg.actions.map(action => <ActionButton key={action.label} {...action} />)}
      </div>
    </div>
  );
}
```

---

### Phase 4: DisconnectOverlay root-cause 분류

**수정 파일**: `electron/src/renderer/components/layout/DisconnectOverlay.tsx`

```tsx
// 현재: 'connecting' | 'disconnected' 두 상태
// 변경: DisconnectReason 추가

export type DisconnectReason =
  | 'ws_closed'        // WebSocket 정상 종료
  | 'backend_crashed'  // backend 프로세스 종료
  | 'network_error'    // 네트워크 오류
  | 'reconnecting';    // 재연결 시도 중

const REASON_COPY: Record<DisconnectReason, string> = {
  ws_closed: '연결이 끊겼습니다. 재연결 중...',
  backend_crashed: 'AI 엔진이 예상치 않게 종료됐습니다. 재시작 중...',
  network_error: '네트워크 오류가 발생했습니다.',
  reconnecting: '연결 중...',
};
```

---

### Phase 5: 진단 정보 수집 (support bundle 기초)

**새 파일**: `electron/src/main/diagnostics-collector.ts`

```typescript
export async function collectDiagnostics(): Promise<DiagnosticBundle> {
  return {
    timestamp: new Date().toISOString(),
    appVersion: app.getVersion(),
    osVersion: process.getSystemVersion?.() ?? os.release(),
    platform: process.platform,
    arch: process.arch,
    binaryPath: getBinaryPath(),
    binaryExists: fs.existsSync(getBinaryPath()),
    port: DEFAULT_PORT,
    logPath: getLogPath(),
    recentLogs: await readRecentLogs(50), // 최근 50줄
  };
}
```

---

## Quality Gate

- [ ] backend binary 없는 환경에서 DiagnosticPanel 표시 확인
- [ ] ANTIVIRUS_BLOCKED 원인 분류 UI 텍스트 확인
- [ ] PORT_IN_USE 자동 포트 전환 테스트
- [ ] MAX_RESTARTS 초과 시 진단 패널로 전환 (무한 재시작 없음)
- [ ] DisconnectOverlay에 backend_crashed 원인 표시 확인
- [ ] 진단 정보 수집 (collectDiagnostics) 테스트
- [ ] 사용자가 '기술 세부 정보' 없이도 다음 행동(재설치/예외처리) 파악 가능

## 관련 계획

- P0-07: 진단 정보 → support bundle export 연동
