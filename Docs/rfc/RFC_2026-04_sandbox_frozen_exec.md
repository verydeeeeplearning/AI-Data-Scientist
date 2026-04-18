# RFC — Packaged Sandbox Execution via Self-Reexec Subcommand

**작성일**: 2026-04-18
**상태**: approved (2026-04-18, 자율 판단 위임 기준)
**관련**: `Docs/plans/PLAN_llm_oauth_and_ml_execution_2026-04-18.md` Phase 2/3, `src/ds_agent/tools/sandbox.py:201`
**배경**: `POST_RELEASE_FALLBACK_ANALYSIS.md` §3.1, S16-FB2 implicit gap

## 1. 문제

`src/ds_agent/tools/sandbox.py:201~207`은 LLM이 생성한 Python 코드를 별도 subprocess로 실행하기 위해 `asyncio.create_subprocess_exec(sys.executable, script_path, ...)`를 사용한다.

이 호출은 두 가지 가정에 의존한다:
1. `sys.executable`이 임의의 `.py` 스크립트를 실행 가능한 Python 인터프리터이다.
2. 실행 환경에 필요한 ML 라이브러리(sklearn, xgboost, lightgbm, matplotlib 등)가 설치되어 있다.

가정 1은 source 모드(`uv run python ...`)에서만 성립한다. PyInstaller onedir 번들(`dist/ds-agent-backend/ds-agent-api.exe`)의 경우 `sys.executable`은 **bootloader exe**이며, 이는 embedded Python을 가지되 외부에서 임의 `.py` 스크립트를 실행할 CLI를 제공하지 않는다 (argparse가 `--host`/`--port`만 수용). 실증:

```
$ ./dist/ds-agent-backend/ds-agent-api.exe /tmp/probe.py
usage: ds-agent-api.exe [-h] [--host HOST] [--port PORT]
ds-agent-api.exe: error: unrecognized arguments: /tmp/probe.py
```

→ **Packaged 배포의 sandbox 경로 전면 작동 불능.** Electron UI에서 ML 코드 실행 불가.

## 2. 목표

1. Packaged 모드에서도 sandbox가 LLM-generated Python 코드를 실행 가능.
2. 외부 Python 인터프리터 의존 0 (사용자에게 "Python 설치하세요" 요구 없음).
3. Source 모드 기존 동작 무변경.
4. `SandboxPort` 계약 불변, Clean Architecture 레이어 위치 유지.

## 3. 설계: Self-Reexec 서브커맨드

### 3.1 개요

`ds-agent-api.exe`에 `--mode {server,exec}` argparse 추가.

- `--mode server` (default): 기존 FastAPI 서버 기동. 기존 호출자(Electron launcher 등) 무수정.
- `--mode exec SCRIPT_PATH`: embedded Python으로 지정 스크립트 실행, exit. stdin/stdout/stderr/returncode는 일반 Python 프로세스와 동일 시그널링.

### 3.2 sandbox.py 분기

```python
def _build_exec_command(script_path: str) -> list[str]:
    if getattr(sys, "frozen", False):
        # Packaged: self-reexec via subcommand
        return [sys.executable, "--mode", "exec", script_path]
    # Source: direct Python invocation
    return [sys.executable, script_path]
```

`ProcessSandbox.execute()`는 이 helper 호출 결과를 그대로 `create_subprocess_exec`에 전달.

### 3.3 argparse 구현 위치

`src/ds_agent/api/app.py`의 `main()` 진입점(또는 `__main__.py`)에서:

```python
parser = argparse.ArgumentParser(...)
parser.add_argument("--mode", choices=["server", "exec"], default="server")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=0)
parser.add_argument("script_path", nargs="?")

args, unknown = parser.parse_known_args()

if args.mode == "exec":
    if not args.script_path:
        sys.stderr.write("--mode exec requires SCRIPT path\n")
        sys.exit(2)
    runpy.run_path(args.script_path, run_name="__main__")
    return
# else: server path
```

### 3.4 Process 격리 속성

서브커맨드 방식에서도 다음은 유지:
- 별도 OS 프로세스 (격리)
- stdout/stderr 분리
- 타임아웃 (asyncio wait_for)
- `cwd` 제어
- preamble wrapping (policy enforcement는 sandbox가 스크립트 내용 rewrite)

sandbox의 정책 체크 (`parse_violations`, `block_subprocess`)는 스크립트 내용 기반이므로 실행 방식 변경과 무관.

## 4. 대안 비교

| 대안 | 장점 | 단점 | 채택? |
|------|------|------|:----:|
| **self-reexec 서브커맨드** (본 RFC) | 외부 의존 0, 단일 번들, 기존 `sys.executable` 사용 유지 | argparse 표면 확장, exec 모드 오용 가능 | ✅ |
| 외부 Python 탐색 (`shutil.which`) | 구현 단순 | 사용자가 Python + ML libs 별도 설치 필요. Electron UX 훼손. | ❌ |
| Embedded Python zipfile 별도 배포 | 완전 격리 | 유지비 큼, Windows PATH 충돌 | ❌ |
| Docker 기반 sandbox | 완벽 격리 | Docker 설치 요구, macOS/Windows 비호환 UX | ❌ |
| In-process exec() | 서브프로세스 0 | 보안 붕괴 (sandbox 실제 격리 없음) | ❌ |

## 5. 보안 고려

1. `--mode exec`는 `runpy.run_path`로 임의 Python 실행 가능. 하지만 **실행 권한은 원 프로세스와 동일** → 추가 privilege escalation 없음.
2. sandbox의 정책(`block_subprocess`, 타임아웃)은 호출자(sandbox.py)가 preamble로 스크립트 내용 변조해서 달성. exec 모드 자체는 중립.
3. `--mode exec`가 외부에서 호출되는 공격 표면은 Electron IPC 경계에 의존. Electron 코드가 `--mode exec`를 user input 기반으로 구성하지 않도록 별도 감사 필요.
4. CI에서 `--mode exec` 테스트는 fixture 스크립트만 실행, user-controlled 경로 금지.

## 6. 테스트 계획

- Unit: `_build_exec_command`의 frozen/non-frozen 분기 (mock)
- Integration: `--mode exec` 서브커맨드가 fixture 스크립트 실행 후 stdout/returncode 정확
- E2E: Packaged exe에 `--mode exec smoke_ml.py` 실행 후 sklearn/pandas OK

## 7. Rollback

argparse 추가 라인 + `_build_exec_command` helper 제거. sandbox.py:201을 원래의 `[sys.executable, script_path]`로 복귀.

## 8. 적용 일정

본 RFC 채택 즉시 `PLAN_llm_oauth_and_ml_execution_2026-04-18.md` Phase 2 착수.
