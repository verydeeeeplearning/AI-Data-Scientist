# S-ml-stack-packaging — ML Stack Install + Frozen Sandbox + Bundle

**실행일**: 2026-04-18
**스코프**: DS Agent가 실제로 ML 모델링을 실행할 수 있도록 세 단계 동시 복원
**근거**: 2026-04-18 사용자 지적 — "sklearn 안쓴다며" / "실제 ML 기반 모델링을 진행하면 뭐 쓸라고?"
**관련 문서**:
- `Docs/plans/PLAN_llm_oauth_and_ml_execution_2026-04-18.md` Phase 0~3
- `Docs/rfc/RFC_2026-04_sandbox_frozen_exec.md`
- `Docs/rfc/RFC_2026-04_ml_deps_policy.md`

## 배경 (실태)

이전 sprint S-packaging-numpy는 "진짜 실패 0건"을 선언했으나, 2026-04-18 사용자 질의로 두 가지 더 깊은 결함이 드러남:

1. **`.venv`에 ML stack 미설치** — `pyproject.toml`에 scikit-learn/xgboost/lightgbm/matplotlib/seaborn 선언 없음. LLM 프롬프트는 "Available: ..."로 주장하나 실제 `import sklearn`은 `ModuleNotFoundError`.
2. **Packaged 모드 sandbox 작동 불가** — `tools/sandbox.py:201`은 `sys.executable script_path` 형식으로 subprocess spawn. PyInstaller onedir 번들에서 `sys.executable`은 bootloader exe이며 argparse가 positional 인자 거부 → `unrecognized arguments` 에러로 sandbox 전면 불능.

## 변경

### Phase 0: RFC 2건

- `Docs/rfc/RFC_2026-04_sandbox_frozen_exec.md` — self-reexec `--mode exec` 서브커맨드 설계. 외부 Python 의존 0.
- `Docs/rfc/RFC_2026-04_ml_deps_policy.md` — scikit-learn 등 core 의존성 정책, DL framework 제외 근거.

### Phase 1: ML stack core 의존성 추가

`pyproject.toml` `[project.dependencies]`에 추가:
- `numpy>=1.26`, `scipy>=1.11`, `pandas>=2.2` (명시)
- `scikit-learn>=1.5`, `xgboost>=2.0`, `lightgbm>=4.3`
- `matplotlib>=3.8`, `seaborn>=0.13`
- `optuna>=3.5`, `joblib>=1.3`

`.venv` site-packages 크기: 기존 대비 **+400-450 MB** 증가 → 566 MB 총량.

### Phase 2: Sandbox frozen-mode + `--mode exec` 서브커맨드

- `src/ds_agent/tools/sandbox.py`: `_build_exec_command(script_path)` helper 신설. `sys.frozen` 감지 시 `[exe, "--mode", "exec", script_path]`, 아니면 기존 `[python, script_path]`.
- `src/ds_agent/api/app.py`: argparse 확장 — `--mode {server,exec}` (기본 server) + positional `script`. `--mode exec` 선택 시 `runpy.run_path`로 스크립트 실행, exit code 승계.

### Phase 3: PyInstaller 번들 확장

`ds-agent-api.spec`:
- `from PyInstaller.utils.hooks import collect_submodules, collect_data_files` 추가
- ML hidden imports: `sklearn / xgboost / lightgbm / matplotlib / seaborn / optuna / joblib` 전부 `collect_submodules`로 수집
- ML datas: `matplotlib` 폰트, `seaborn` 스타일, `sklearn` 데이터 → `collect_data_files`
- `excludes`에서 sklearn/matplotlib 제거 (이전 S-packaging-numpy에서 유지되었던 항목)
- DL framework(torch/tensorflow/cv2)는 여전히 excludes (RFC §3.2)

## TDD 증거

### Phase 1 테스트 (RED→GREEN)

- `tests/unit/tools/test_ml_deps_available.py`: 10 ML module import + sklearn mini fit-predict + matplotlib Agg backend. **12 tests pass**.
- `tests/unit/tools/test_code_execution_prompt_consistency.py`: 프롬프트 "Available:" 리스트 파싱 + 각 라이브러리 import 시도. **9 tests pass**.

### Phase 2 테스트 (RED→GREEN)

- `tests/unit/infrastructure/test_sandbox_frozen_mode.py`: `_build_exec_command` frozen/non-frozen 분기 4건. **PASS**.
- `tests/integration/api/test_exec_subcommand.py`: `--mode exec` 서브커맨드 6건 (exit code, 필수 인자, ML import smoke, help 텍스트). **PASS**.

### Phase 3 smoke (source 모드 예비 검증)

```text
$ uv run python scripts/smoke_packaged_ml.py
python=3.12.10 ...
frozen=False
sklearn=1.8.0
xgboost=3.2.0
lightgbm=4.6.0
iris_accuracy=0.9737
SMOKE_OK
```

## Quality Gate (종합)

- [x] `ruff check`: 모든 신규 파일 clean
- [x] scope pytest 753/753 pass (architecture/domain/application/sandbox/api)
- [x] `lint-imports`: 2 contracts KEPT
- [x] mypy baseline: 257 유지, 신규 error 0
- [x] Source smoke: iris 분류 97.4% accuracy
- [x] **Packaged smoke**: `ds-agent-api.exe --mode exec scripts/smoke_packaged_ml.py` → `frozen=True`, sklearn/xgboost/lightgbm 모두 import 성공, `iris_accuracy=0.9737`, `SMOKE_OK`, **exit 0**
- [x] Packaged backend 서버 기동: `ds-agent-api.exe --host 127.0.0.1 --port 8425` → 18 skill load, `api_started`, `READY:8425:<hash>`, `/health` 200 OK (startup ~1s)

### 번들 측정 (실측, 2026-04-18)

| 항목 | S-packaging-numpy | S-ml-stack-packaging | 증분 |
|------|:----------------:|:-------------------:|:----:|
| 빌드 시간 | 96.9s | 3단계(Analysis 재실행 포함, 최종 build_complete_log 184.6s) | +87s |
| exe (bootloader) | 25 MB | 57 MB | +32 MB |
| `_internal/` | 194 MB | 401 MB | +207 MB |
| 합계 | 218 MB | **458 MB** | +240 MB |

가장 큰 단일 기여자: `_internal/xgboost/lib/xgboost.dll` **143 MB**. numpy/scipy/sklearn/matplotlib/seaborn/lightgbm 합계는 추가 ~60 MB 수준. torch/tensorflow 미포함 덕분에 번들이 1GB 아래로 유지됨.

### Native DLL 수집 경로 (spec §ML_BINARIES)

- `collect_all("xgboost")` 실패 (xgboost.testing import 에러) → 우회: `collect_submodules` + `skip_substrings=("testing","dask","spark","federated")`
- xgboost.dll은 `.venv` 경로를 hard-coded로 추적해서 `binaries=[(src, "xgboost/lib")]` 명시 복사
- `lightgbm/bin/lib_lightgbm.dll`는 `collect_dynamic_libs`가 정상 수집

## Rollback

Phase 단위로 revert 가능:
- Phase 1: `pyproject.toml` revert + `uv sync`
- Phase 2: `src/ds_agent/api/app.py`, `tools/sandbox.py` revert
- Phase 3: `ds-agent-api.spec` revert + 재빌드

## 이월 (Phase 4/5/6)

- Phase 4 Gemini OAuth cassette (사용자 Gemini 구독 승인 필요)
- Phase 5 Codex OAuth subprocess fixture (사용자 ChatGPT Plus + `codex login` 필요)
- Phase 6 E2E iris 3-채널 parity (Phase 3+4+5 완료 후)
- Phase 7 문서 정합성 + 릴리스 판정 재평가
