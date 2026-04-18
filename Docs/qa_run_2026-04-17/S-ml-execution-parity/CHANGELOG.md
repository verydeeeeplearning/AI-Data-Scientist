# S-ml-execution-parity (Phase 6) — ML 실행 경로 source/frozen 대칭 증명

**실행일**: 2026-04-18
**스코프**: sandbox `execute_code` 경로가 source 모드와 packaged(frozen) 모드에서 **byte-identical 결정성**을 보장함을 실증
**근거**: `PLAN_llm_oauth_and_ml_execution_2026-04-18.md` Phase 6

## 3-way 커버리지 맵 (본 Phase 반영)

| Layer | Tier | 증거 |
|:-----:|:----:|------|
| LLM 응답 | API (OpenAI) | S16 VCR cassette 9/9 byte-identical |
| LLM 응답 | OAuth (Codex) | S22 subprocess fixture 5/5 byte-identical |
| LLM 응답 | OAuth (Gemini CLI) | Phase 4 (진행 예정) |
| **Tool call / sandbox 실행** | **source vs frozen** | **Phase 6 본 sprint — 8/8 pass, byte-identical on deterministic fields** ✅ |

## 설계 의도

3-Tier 채널(CLI/Telegram/Electron)이 모두 **공유된 backend**를 거쳐 `ProcessSandbox.execute_code` 경로로 수렴함. 따라서 3채널 parity 주장은 다음으로 분해 가능:

1. **LLM 응답 parity**: 동일 프롬프트 → 동일 응답 (cassette로 보장)
2. **Tool call 생성 parity**: agent core 결정성 (기존 테스트 범위)
3. **Sandbox 실행 parity**: 동일 코드 → 동일 출력 (본 Phase가 증명)

본 Sprint는 3번을 source/frozen 두 실행 모드에 대해 증명. 5 channels → 1 sandbox 구조 덕분에 이는 3채널 전체 대칭성의 **최후 보증**.

## 구현

### 신규 파일

- `tests/integration/sandbox/test_ml_execution_parity.py` — 8 테스트
  1. `test_source_sandbox_runs_iris_fit` — source 모드 `ProcessSandbox.execute()`로 sklearn iris fit → accuracy ≥ 0.9
  2. `test_frozen_exec_runs_iris_fit` — packaged exe `--mode exec`로 동일 코드 → accuracy ≥ 0.9
  3. `test_source_and_frozen_byte_identical_on_deterministic_fields` — 두 모드의 sklearn 버전 + iris_accuracy SHA-256 동일
  4. `test_build_exec_command_reuse_in_both_modes` — `_build_exec_command` helper 계약 확인
  5. `test_packaged_exe_can_import_ml_module[sklearn|xgboost|lightgbm|pandas]` — 4개 ML 모듈 전수 packaged import 성공

### 결정성 기준

Deterministic fields:
- `sklearn=<version>` (환경 pinning)
- `iris_accuracy=0.973684` (random_state=0, max_iter=500로 고정)

Non-deterministic (해시 제외):
- ProcessSandbox preamble 로그
- 실행 시간 / PID / temp 경로
- tool registration debug 로그

`_hash_deterministic_fields()`로 stdout에서 정규식 추출 후 해시 → 두 모드가 동일값 반환.

## 증거

```text
$ uv run pytest tests/integration/sandbox/test_ml_execution_parity.py -v
test_source_sandbox_runs_iris_fit PASSED
test_frozen_exec_runs_iris_fit PASSED
test_source_and_frozen_byte_identical_on_deterministic_fields PASSED
test_build_exec_command_reuse_in_both_modes PASSED
test_packaged_exe_can_import_ml_module[sklearn] PASSED
test_packaged_exe_can_import_ml_module[xgboost] PASSED
test_packaged_exe_can_import_ml_module[lightgbm] PASSED
test_packaged_exe_can_import_ml_module[pandas] PASSED
============================ 8 passed in 18.78s ==============================
```

두 모드 공통 결과:
- sklearn=1.8.0
- iris_accuracy=0.973684 (정확도 Hash 동일)

## Quality Gate

- [x] 8/8 tests pass
- [x] source/frozen 해시 100% 일치 (random_state 고정 덕분)
- [x] xgboost/lightgbm/pandas import 모두 packaged에서 성공
- [x] 기존 회귀 영향 없음
- [x] Clean Architecture: `ProcessSandbox` 계약 무수정, `_build_exec_command` helper만 재활용

## 제한사항 (scope 명시)

1. **LLM 미포함**: 코드 문자열은 고정. LLM → tool call 생성 경로는 S16/S22 cassette가 커버. 두 증거가 합쳐져야 풀 E2E.
2. **Real 3-Channel 실행 미포함**: CLI/Telegram/Electron에서 "실제로 agent를 띄워 iris 돌리는" 수준은 추후. 현 증거는 "이 코드가 두 sandbox 모드에서 동일 결과"를 증명.
3. **LLM 응답 다양성 미반영**: temperature=0.0 프롬프트로도 LLM 응답이 완벽 결정적이지 않을 수 있음 (provider 특성). Cassette replay로 이 문제 우회됨.
4. **Windows only 증거**: 다른 플랫폼(macOS/Linux)에서 xgboost.dll 대응 `libxgboost.dylib`/`.so`의 유사 이슈 가능. post-release 플랫폼 확장 시 재평가.

## Rollback

- `tests/integration/sandbox/test_ml_execution_parity.py` 삭제
- `tests/integration/sandbox/__init__.py` 삭제

## 후속 (Phase 4)

Gemini CLI OAuth 경로가 해결되면 Phase 6-B로:
- LLM cassette (S22 또는 Phase 4 신규) → agent core → `execute_code` → sandbox
- 3 채널 실 orchestrator로 DeliveryPack 해시 일치 증명

현 시점에선 Phase 6-A(본 sprint)로 **ML 실행 경로의 환경 대칭성**이 확보된 상태.
