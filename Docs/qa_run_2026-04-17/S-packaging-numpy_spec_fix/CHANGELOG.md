# S-packaging-numpy — PyInstaller spec numpy/scipy/pandas 복원

**실행일**: 2026-04-18
**스코프**: `ds-agent-api.spec` excludes 재평가로 S16-FB2 (packaged backend import failure) 해소
**근거**: `Docs/qa_run_2026-04-17/POST_RELEASE_FALLBACK_ANALYSIS.md` §3.1 — 유일한 "진짜 실패" 항목

## 배경

S16 (LLM record-replay)에서 packaged backend `dist/ds-agent-backend/ds-agent-api.exe` 실행 시 `ds_agent.agent.factory.create_agent` 경로의 tool import(`data_loader`, `data_profiler`, `sampling_utils`, `verifiers/*`, `ab_test_analyzer`)가 module-load time에 `numpy`/`scipy`/`pandas`를 요구하지만, 이전 spec에서는 이들이 excludes에 포함되어 있어 `ModuleNotFoundError`로 backend가 기동하지 못함. S16은 source backend (`uv run python -m ds_agent.api.app`)로 우회했으며 이 건은 P0-05(서명 인증서) 조달 후 C15 smoke 5/5 재실행의 blocker로 이월되어 있었음.

## 변경

### `ds-agent-api.spec`

**1. `excludes`에서 제거 (3개)**
- `numpy`
- `scipy`
- `pandas`

**2. `hiddenimports`에 명시 추가 (4개)**
- `numpy`
- `scipy`
- `scipy.stats`  (`ab_test_analyzer`가 `from scipy import stats` 사용)
- `pandas`

**3. 주석 명시**: 왜 sklearn / matplotlib는 여전히 제외인지 — 이 둘은 LLM 프롬프트(tools/modeling.py, tools/evaluation.py 등)에 **문자열로만** 등장. 실제 실행은 sandbox subprocess (`sys.executable` + tempfile script)에서 시스템 Python이 담당하므로 backend 번들에는 불필요.

### 유지되는 excludes

| 모듈 | 유지 근거 |
|------|----------|
| `tkinter` | backend FastAPI에 UI 없음 |
| `matplotlib` | 문자열 프롬프트 참조만, sandbox 외부에서 실행 |
| `sklearn` | 동일 (sandbox 외부 실행) |
| `cv2` | 미사용 |
| `torch` / `tensorflow` | 미사용, 패키지 크기 억제 |
| `pytest` / `ruff` / `mypy` | dev tool |

### 실측 증거 (grep 기반)

```text
src/ds_agent/application/services/ab_test_analyzer.py:8:import numpy as np
src/ds_agent/application/services/ab_test_analyzer.py:9:from scipy import stats
src/ds_agent/infrastructure/verifiers/common.py:10:import pandas as pd
src/ds_agent/infrastructure/verifiers/data.py:9:import pandas as pd
src/ds_agent/infrastructure/verifiers/statistical.py:9:import numpy as np
src/ds_agent/infrastructure/verifiers/statistical.py:10:import pandas as pd
src/ds_agent/tools/data_loader.py:74:import pandas as pd
src/ds_agent/tools/data_profiler.py:62:import pandas as pd
src/ds_agent/tools/data_profiler.py:63:import numpy as np
src/ds_agent/tools/sampling_utils.py:5:import pandas as pd
```

sklearn 실 import: **0건** (`grep -rE "^(import|from)\s+sklearn"` = 미해당. 문자열 참조만 존재).

## Quality Gate

- [x] Source-level import smoke: 10개 핵심 모듈(`factory`, `router`, `tools/data_*`, `verifiers/*`, `ab_test_analyzer`) 전수 OK
- [x] PyInstaller 빌드: `pyinstaller ds-agent-api.spec --clean --noconfirm` 성공 (exit 0, 96.9s)
- [x] Artifact 존재: `dist/ds-agent-backend/ds-agent-api.exe` (25 MB bootloader), `_internal/` 194 MB, 번들 합계 **218 MB** (이전 ~40 MB 대비 +178 MB — numpy/scipy/pandas 포함 비용)
- [x] `_internal/`에 `numpy/`, `scipy/`, `pandas/` + `numpy.libs/`, `scipy.libs/`, `pandas.libs/` DLL 디렉토리 전부 존재
- [x] Packaged backend 기동 smoke:
  - `ds-agent-api.exe --help` exit 0
  - `ds-agent-api.exe --host 127.0.0.1 --port 8423` startup ~1s, `api_started port=8423`
  - `READY:8423:6cd63ed8c439f1ae72abba5279aa12f26834cea07a43e0bb5f607d125c9ad2b6` 시그널 정상 발신
  - 18개 built-in skill 전수 load (`_internal/ds_agent/skills/builtin/*.md`)
  - `GET /health` → `200 OK {"status":"ok"}`
- [x] Import error 0건 — S16-FB2 해소
- [x] Scope pytest (`tests/unit/architecture/` + `tests/unit/domain/`): 221/221 pass, 1.34s
- [x] `lint-imports`: 2 contracts kept, 0 broken
- [x] `scripts/check_import_contracts.py`: ok

## S16-FB2 상태 전이

- 이전: `POST_RELEASE_FALLBACK_ANALYSIS.md` §2.2 **High severity, production packaging gap**
- 이후: **closed** — packaged backend가 import-time failure 없이 기동 가능
- 다만 C15 (코드 서명 smoke 5/5)는 여전히 P0-05 조달 대기 — 본 스프린트는 "signed build smoke의 선행 조건"을 해소하는 것에 한정

## 영향 분석

| 측면 | 실측/영향 |
|------|----------|
| 번들 크기 | **+178 MB** (40 → 218 MB). numpy/scipy/pandas + DLLs 포함. Electron installer 크기 증가 예상 |
| 시작 시간 | 기동 후 READY까지 ~1s (smoke 측정). 이전 source backend과 동급 |
| Electron 제품 경험 | backend spawn→READY 지연 미미. subprocess spawn timeout 여유 안에서 수용 |
| 보안 | 추가 attack surface 없음 (source backend에서 이미 동일 deps 사용 중) |
| 서명 빌드 (P0-05) | 번들 크기 증가로 서명 시간·배포 다운로드 크기 영향. GO 전환 후 가시화 필요 |

## Rollback

이 변경은 spec 3건 수정만 포함. 되돌릴 경우 3개 라인을 `excludes`에 재추가. 단 S16-FB2가 다시 열림.

## 후속

- P0-05(코드 서명 인증서) 조달 완료 시 서명 빌드 스모크 5/5 재실행 (C15 플랜)
- 번들 크기가 배포에 문제가 되면 `scipy` 서브모듈 단위 exclude 고려 (ex: `scipy.sparse`, `scipy.spatial` 등 미사용 항목)
