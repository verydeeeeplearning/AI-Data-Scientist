# P0-01: 코드 실행 샌드박싱

**우선순위**: P0 — 베타 배포 차단 조건 (보안 최상위 리스크)
**요구사항 섹션**: 5.11.A
**상태**: Complete (Phase 1–4 + 메모리 제한 + Phase 3 UI 모두 완료, 2026-04-15)
**의존성**: 없음 (독립 구현 가능)

---

## 구현 현황 (2026-04-14)

### 완료
- **Phase 1 Domain**: `SandboxPolicy`, `SandboxViolation`, `SandboxExecutionResult`, `ViolationKind`
  in `src/ds_agent/domain/entities/sandbox.py` (외부 dependency 0)
- **Phase 1 Tests**: `tests/unit/domain/test_sandbox_policy.py` (21 cases, all green)
- **Application port**: `CodeExecutorPort` in `src/ds_agent/application/ports/code_executor_port.py`
- **Phase 2 Runtime Preamble**: `src/ds_agent/infrastructure/sandbox/preamble.py`
  - `builtins.open` / `io.open` / `os.open` runtime wrappers
  - `os.remove`/`unlink`/`rmdir`/`rename`/`replace` write-guards
  - `os.system` / `os.exec*` / `os.spawn*` / `os.popen` blocked
  - data_dirs 에 대한 read-only 적용
  - SANDBOX_VIOLATION 센티넬 기반 parent ↔ child 통신 (`parse_violations`)
- **Phase 2 Executor 통합**: `ProcessSandbox`가 `runtime_policy` 주입 시 preamble을 자동 wrap
  하고 stderr에서 violation 파싱 → `SandboxResult.violations` 채움
- **Integration tests**: `tests/integration/infrastructure/test_subprocess_sandbox.py`
  (workspace 내부 write 통과, 외부 write 차단, data_dir read-only, os.system 차단,
  timeout, pandas read→transform→write 사이클 정상, preamble 파싱 round-trip — 12 cases green)

### Phase 4 DI/Config (완료 2026-04-14)
- **Schema**: `SandboxConfig` pydantic 모델 (`config/schema.py`) —
  `enabled`, `timeout_seconds`, `max_memory_mb`, `block_subprocess`,
  `approved_hosts`, `data_dirs`. `DSAgentConfig.sandbox` 로 노출.
- **Composition root**: `agent/factory.py::_publish_sandbox_policy` 에서
  pydantic 모델을 도메인 `SandboxPolicy` 로 변환하여
  `tools/sandbox_context.set_active_sandbox_config` 로 process-global 발행.
- **Tool 팩토리 연동**: `tools/sandbox.py::create_sandbox` →
  `sandbox_context.resolve_policy` 가 발행된 policy 와 per-call workspace 를 병합.
- **Entrypoint 연동**: `api/agent_session_registry.py`, `cli/main.py`,
  `gateway/telegram_runner.py` 모두 `create_agent(..., sandbox_config=...)` 전달.
- **Tests**: `tests/unit/infrastructure/test_sandbox_context.py` (4),
  `tests/unit/infrastructure/test_sandbox_config_wiring.py` (4) — 모두 green.

### 메모리 제한 enforcement (완료 2026-04-14)
- **POSIX**: `resource.setrlimit(RLIMIT_AS, ...)` — virtual address space cap.
- **Windows**: `ctypes` 기반 Job Object — `CreateJobObjectW` →
  `JOB_OBJECT_LIMIT_PROCESS_MEMORY` 설정 → `AssignProcessToJobObject(GetCurrentProcess())`
  (nested job, Windows 8+). 핸들 truncation 방지를 위해 모든 ctypes 호출에
  명시적 `argtypes`/`restype`. 실패 시 `resource` violation을 non-blocking으로 emit.
- preamble 시작부에서 `_apply_memory_limit(max_memory_mb)` 자동 실행.
- **Tests** (`test_subprocess_sandbox.py::TestResourceLimits`):
  - `test_memory_limit_blocks_large_alloc` — 256MB cap에서 1GB 할당 실패.
  - `test_memory_limit_setup_failure_is_non_blocking` — `max_memory_mb=0` 비활성화 동작.
- **Windows 운영 메모**: VAS 기반이라 DLL mapping 포함. pandas/sklearn 사용 시
  최소 1024–2048MB 권장 (default 2048MB는 일반 워크로드 검증됨).

### Phase 3 UI (완료 2026-04-15)
- **Backend event emission**: `_ds_sandbox_runner.run_ds_sandbox` 가 `SandboxResult.violations`
  를 순회하며 `sandbox.violation` 이벤트(`{kind, detail, blocked, sessionId, runId, tool,
  timestamp}`) 를 emit. 스키마는 `api/event_schemas.SandboxViolationEvent` 로 고정.
  - **Tests**: `tests/unit/infrastructure/test_sandbox_runner_events.py` (5 cases — blocked
    filesystem, resource, multi-violation, success-no-emit, no-callable-emit guard).
- **Renderer types/store**: `types/events.SandboxViolationEvent`, `workflowStore` 에
  `sandboxViolations` slice (cap 50) + `recordSandboxViolation` /
  `acknowledgeSandboxViolation` / `clearSandboxViolations` 액션 추가.
  `useWorkflow.ts` 가 WS 이벤트 → 스토어 배선.
- **`SandboxApprovalModal.tsx`** (`components/sandbox/`): blocking modal — `approvals`
  의 oldest pending 을 우선 표출. `window.prompt` 제거 → textarea 로 freeform 응답.
  Esc = reject. multiple pending 시 카운터 표기. 기존 `ApprovalPanel` 은 history view 로 유지.
- **`SandboxViolationToast.tsx`**: 우측 하단 stack (max 3 visible). 8s auto-dismiss,
  수동 dismiss 가능. kind 별 아이콘 + blocked/flagged 색상 분기.
- **App 마운트**: `App.tsx` 의 connected 영역에 `<SandboxApprovalModal />` +
  `<SandboxViolationToast />` 추가.

### 잔존 (post-beta)
- 조직/팀 단위 approved_hosts 정책 동기화 (P2-15 와 합쳐 후속 처리)

---

---

## 개요

현재 DS Agent는 LLM이 생성한 Python 코드를 `execute_code` tool을 통해
사용자 머신에서 **직접 실행**한다. 비개발자 대상 배포 시 다음 위험이 존재한다:

- 파일 시스템 전체 접근 (사용자 Documents, Desktop 읽기/삭제)
- 임의 네트워크 호출 (데이터 외부 유출)
- `subprocess`, `os.system` 등으로 시스템 명령 실행
- 악의적인 CSV/파일 내 prompt injection으로 악성 코드 유도

**자율 Agent 정체성 유지 원칙**:
샌드박스는 실행 **환경**을 격리하는 것이지 LLM이 **무엇을 하기로 결정하는지**를
제한하지 않는다. LLM은 여전히 자율적으로 tool을 선택하고 코드를 생성한다.
샌드박스는 그 코드가 실행되는 격리된 컨테이너다.

---

## 현재 코드 분석

```
src/ds_agent/tools/
└── (execute_code tool 위치 확인 필요)
```

현재 실행 흐름:
1. LLM → `execute_code(code: str)` tool call
2. Tool이 Python `exec()` 또는 subprocess로 코드 직접 실행
3. stdout/stderr 캡처 → LLM에게 결과 반환

---

## 구현 옵션 비교

| 옵션 | 격리 강도 | 비개발자 부담 | ML 호환성 | 권장도 |
|------|----------|------------|----------|--------|
| **별도 프로세스 + allowlist** | 중 | 없음 | 완전 | ★★★★★ **1차 권장** |
| Docker 컨테이너 | 강 | Docker Desktop 필요 | 완전 | ★★★ (2차) |
| Pyodide (WebAssembly) | 강 | 없음 | 제한적 | ★★ (연구용) |
| RestrictedPython | 약 | 없음 | 완전 | ★ (보완용) |
| Windows Job Object + AppContainer | 중 | 없음 | 완전 | ★★★ (Windows 전용) |

**결정**: 1차는 **별도 프로세스 + 파일시스템 allowlist + 네트워크 gate** 조합.

---

## 아키텍처 설계

### Clean Architecture 레이어 매핑

```
Domain:
  SandboxPolicy           — allowlist 규칙 (workspace 경로, 허용 호스트)
  SandboxResult           — 실행 결과 (stdout, stderr, exit_code, violations)
  SandboxViolation        — 정책 위반 이벤트 (attempted_path, attempted_host)

Application (Port):
  CodeExecutorPort        — interface: execute(code) → SandboxResult

Infrastructure (Adapter):
  SubprocessSandboxExecutor  — implements CodeExecutorPort
    ├── FileSystemGate      — workspace allowlist 검증
    ├── NetworkGate         — approved host 검증 (차단 또는 사용자 승인 요청)
    └── ResourceLimiter     — timeout, memory, CPU 제한

Tools Layer:
  execute_code tool       — CodeExecutorPort 주입받아 호출 (DI)
```

### 격리 메커니즘

```
┌─────────────────────────────────────────────────┐
│  Main DS Agent Process                          │
│                                                 │
│  LLM → execute_code tool → CodeExecutorPort    │
│                                    │            │
│                                    ▼            │
│              SubprocessSandboxExecutor          │
│                    │                            │
└────────────────────┼────────────────────────────┘
                     │ spawn (restricted)
                     ▼
┌─────────────────────────────────────────────────┐
│  Sandbox Worker Process                         │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ Allowed:                                │   │
│  │   - Read/Write: ~/.ds-agent/workspace/  │   │
│  │   - Read:       data/ (uploaded files)  │   │
│  │   - Network:    approved_hosts only     │   │
│  │                                         │   │
│  │ Blocked:                                │   │
│  │   - Write: outside workspace            │   │
│  │   - Network: unapproved hosts           │   │
│  │   - subprocess / os.system              │   │
│  │   - sys.exit, os.kill                   │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  exec(code) → stdout/stderr → pipe to parent   │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 구현 Phase 계획 (TDD)

### Phase 1: Domain 정의 + FileSystem Gate

#### RED — 테스트 먼저

**파일**: `tests/unit/domain/test_sandbox_policy.py`

```python
# 테스트 케이스
def test_workspace_path_allowed():
    policy = SandboxPolicy(workspace_dir=Path("~/.ds-agent/workspace"))
    assert policy.is_path_allowed(Path("~/.ds-agent/workspace/output.csv")) is True

def test_outside_workspace_denied():
    policy = SandboxPolicy(workspace_dir=Path("~/.ds-agent/workspace"))
    assert policy.is_path_allowed(Path("~/Documents/secret.docx")) is False

def test_path_traversal_blocked():
    policy = SandboxPolicy(workspace_dir=Path("~/.ds-agent/workspace"))
    assert policy.is_path_allowed(Path("~/.ds-agent/workspace/../../etc/passwd")) is False

def test_uploaded_data_readable():
    policy = SandboxPolicy(workspace_dir=..., data_dirs=[Path("data/")])
    assert policy.is_path_allowed(Path("data/customers.csv"), mode="read") is True
    assert policy.is_path_allowed(Path("data/customers.csv"), mode="write") is False
```

**파일**: `tests/unit/infrastructure/test_filesystem_gate.py`

```python
def test_open_blocked_outside_workspace():
    # sandbox 내 open() 호출 가로채기 검증
    ...

def test_write_workspace_allowed():
    ...
```

#### GREEN — 최소 구현

**새 파일**: `src/ds_agent/domain/entities/sandbox.py`

```python
@dataclass(frozen=True)
class SandboxPolicy:
    workspace_dir: Path
    data_dirs: list[Path] = field(default_factory=list)
    approved_hosts: list[str] = field(default_factory=list)
    timeout_seconds: int = 120
    max_memory_mb: int = 2048

    def is_path_allowed(self, path: Path, mode: str = "readwrite") -> bool:
        resolved = path.expanduser().resolve()
        workspace = self.workspace_dir.expanduser().resolve()
        if resolved.is_relative_to(workspace):
            return True
        if mode == "read":
            for d in self.data_dirs:
                if resolved.is_relative_to(d.expanduser().resolve()):
                    return True
        return False

@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: int
    violations: list[SandboxViolation] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and len(self.violations) == 0

@dataclass
class SandboxViolation:
    type: Literal["filesystem", "network", "subprocess", "resource"]
    detail: str
    blocked: bool = True
```

**새 파일**: `src/ds_agent/application/ports/code_executor_port.py`

```python
from abc import ABC, abstractmethod
from ds_agent.domain.entities.sandbox import SandboxResult

class CodeExecutorPort(ABC):
    @abstractmethod
    def execute(self, code: str, context: dict | None = None) -> SandboxResult:
        ...
```

#### REFACTOR

- Path traversal 방어 로직 별도 유틸로 추출
- `SandboxPolicy` factory method for common presets

---

### Phase 2: SubprocessSandboxExecutor 구현

#### RED

**파일**: `tests/integration/infrastructure/test_subprocess_sandbox.py`

```python
def test_simple_code_executes():
    executor = SubprocessSandboxExecutor(policy=default_policy())
    result = executor.execute("print('hello')")
    assert result.stdout == "hello\n"
    assert result.success

def test_file_write_outside_workspace_blocked():
    executor = SubprocessSandboxExecutor(policy=default_policy())
    code = "open('/etc/passwd', 'w').write('hacked')"
    result = executor.execute(code)
    assert result.violations
    assert any(v.type == "filesystem" for v in result.violations)

def test_subprocess_blocked():
    result = executor.execute("import subprocess; subprocess.run(['ls'])")
    assert any(v.type == "subprocess" for v in result.violations)

def test_timeout_enforced():
    result = executor.execute("while True: pass", timeout_seconds=2)
    assert result.exit_code != 0
    assert "timeout" in result.stderr.lower()

def test_pandas_works_in_sandbox():
    code = """
import pandas as pd
df = pd.DataFrame({'a': [1,2,3]})
print(df.shape)
"""
    result = executor.execute(code)
    assert "(3, 1)" in result.stdout
```

#### GREEN

**새 파일**: `src/ds_agent/infrastructure/sandbox/subprocess_executor.py`

```python
class SubprocessSandboxExecutor(CodeExecutorPort):
    """
    Spawn a restricted Python subprocess.
    Intercepts: open(), socket, subprocess via sitecustomize injection.
    """

    def __init__(self, policy: SandboxPolicy) -> None:
        self._policy = policy

    def execute(self, code: str, context: dict | None = None) -> SandboxResult:
        wrapper = self._build_wrapper(code, context or {})
        start = time.monotonic()

        proc = subprocess.Popen(
            [sys.executable, "-c", wrapper],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._restricted_env(),
            cwd=str(self._policy.workspace_dir),
        )
        try:
            stdout, stderr = proc.communicate(timeout=self._policy.timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            return SandboxResult(
                stdout="",
                stderr="Execution timeout exceeded",
                exit_code=-1,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        violations = self._parse_violations(stderr.decode())
        return SandboxResult(
            stdout=stdout.decode(),
            stderr=stderr.decode(),
            exit_code=proc.returncode,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            violations=violations,
        )

    def _build_wrapper(self, code: str, context: dict) -> str:
        """Inject policy enforcement before user code."""
        policy_json = json.dumps({
            "workspace": str(self._policy.workspace_dir.expanduser().resolve()),
            "data_dirs": [str(d.expanduser().resolve()) for d in self._policy.data_dirs],
            "approved_hosts": self._policy.approved_hosts,
        })
        return SANDBOX_PREAMBLE_TEMPLATE.format(
            policy_json=policy_json,
            user_code=code,
        )
```

**새 파일**: `src/ds_agent/infrastructure/sandbox/preamble.py`

```python
# SANDBOX_PREAMBLE_TEMPLATE
# Python 코드로 inject되어 sandbox 내 builtins를 재정의
# - open() → FileSystemGate 경유
# - socket.connect() → NetworkGate 경유
# - subprocess import → 차단
```

**수정 파일**: `src/ds_agent/tools/execute_code.py` (DI 전환)

```python
# Before: exec() 직접 호출
# After:  CodeExecutorPort 주입받아 호출
class ExecuteCodeTool(BaseTool):
    def __init__(self, executor: CodeExecutorPort) -> None:
        self._executor = executor

    def run(self, code: str) -> str:
        result = self._executor.execute(code)
        if result.violations:
            blocked = [v for v in result.violations if v.blocked]
            if blocked:
                return f"[SANDBOX BLOCKED] {blocked[0].detail}\n{result.stderr}"
        return result.stdout or result.stderr
```

---

### Phase 3: 사용자 승인 흐름 (Network Gate)

네트워크 호출 시 차단이 아닌 사용자 승인 옵션 제공.

**수정 파일**: `electron/src/renderer/components/` → `SandboxApprovalDialog.tsx`

```tsx
// 사용자에게 보여줄 다이얼로그
// "Agent가 외부 서버(api.openai.com)에 데이터를 전송하려 합니다."
// [허용] [차단] [이 세션에서 항상 허용]
```

**IPC 채널**: `sandbox:approve-network` (main ↔ renderer)

---

### Phase 4: 구성 통합 + DI

**수정 파일**: `src/ds_agent/infrastructure/config/` (composition root)

```python
# SandboxPolicy를 config에서 로드
sandbox_policy = SandboxPolicy(
    workspace_dir=Path(config.agent.workspace_dir),
    data_dirs=[Path(config.agent.data_dir)] if config.agent.data_dir else [],
    approved_hosts=config.sandbox.approved_hosts,
    timeout_seconds=config.sandbox.timeout_seconds,
)
executor = SubprocessSandboxExecutor(policy=sandbox_policy)
# ExecuteCodeTool에 주입
```

**수정 파일**: `src/ds_agent/config/schema.py`

```python
class SandboxConfig(BaseModel):
    enabled: bool = True
    timeout_seconds: int = 120
    max_memory_mb: int = 2048
    approved_hosts: list[str] = ["pypi.org", "files.pythonhosted.org"]
    block_subprocess: bool = True
```

---

## Quality Gate

- [ ] TDD: 모든 Phase에서 RED → GREEN → REFACTOR 순서 준수
- [ ] 테스트: workspace 외부 쓰기 자동 차단 확인
- [ ] 테스트: subprocess 호출 자동 차단 확인
- [ ] 테스트: pandas/numpy/sklearn 정상 동작 확인 (ML 호환성)
- [ ] 테스트: timeout 강제 종료 확인
- [ ] 테스트: path traversal 방어 확인
- [ ] 아키텍처: `CodeExecutorPort` 인터페이스로 execute_code tool 분리
- [ ] 아키텍처: Domain이 외부 라이브러리 미참조 확인
- [ ] **자율 Agent 원칙**: LLM이 생성하는 코드 자체는 제한 없음, 실행 환경만 격리

## 위험 및 대응

| 위험 | 대응 |
|------|------|
| ML 라이브러리가 내부적으로 subprocess 사용 | approved subprocess list 또는 ML별 예외 처리 |
| preamble injection이 긴 코드에서 파싱 오류 | wrapper 방식으로 코드 wrapping (f-string 대신 tempfile) |
| Windows에서 fork 동작 차이 | `spawn` 방식으로 통일 (Windows 기본) |
| sandbox process 좀비 프로세스 | subprocess.communicate() + timeout 강제 kill 보장 |
