# RFC — ML Dependencies Policy for DS Agent

**작성일**: 2026-04-18
**상태**: approved (2026-04-18, 자율 판단 위임 기준)
**관련**: `Docs/plans/PLAN_llm_oauth_and_ml_execution_2026-04-18.md` Phase 1/3

## 1. 문제

DS Agent의 LLM 프롬프트 (`src/ds_agent/tools/code_execution.py`)는 sandbox에서 "Available: pandas, numpy, sklearn, matplotlib, seaborn, lightgbm, xgboost"를 주장한다. `src/ds_agent/tools/modeling.py`, `evaluation.py` 등도 scikit-learn / LightGBM / XGBoost / Optuna 사용을 전제한 프롬프트를 생성한다.

2026-04-18 실측:
- `.venv`에 실제 설치된 ML 관련: **numpy 2.4.4 / pandas 3.0.2 / scipy 1.17.1만**.
- `pyproject.toml` `[project.dependencies]`에 sklearn/xgboost/lightgbm/matplotlib/seaborn 선언 없음.
- LLM이 프롬프트대로 `import sklearn` 코드를 생성하면 sandbox 실행이 `ModuleNotFoundError`로 실패.

→ **제품 주장과 설치 현황이 불일치**. "DS Agent"라는 이름에 부합하는 실제 모델링 경로 미검증.

## 2. 목표

1. 프롬프트에서 "Available"로 명시된 모든 라이브러리가 실제 환경(source + packaged)에 존재.
2. `pyproject.toml`에 core 의존성으로 고정 (optional extra 아님) → `uv sync` 1회로 완성.
3. DL 프레임워크(torch/tensorflow)는 범위 밖으로 분리.
4. 번들 크기 영향 수용 (사용자 명시 "모두 포함").

## 3. 스코프 정의

### 3.1 Core 의존성 (본 RFC 채택 시 추가)

| 라이브러리 | 용도 | 근거 |
|----------|-----|------|
| `scikit-learn` | 분류·회귀·클러스터링·전처리 기본 | `tools/modeling.py` 프롬프트 명시 |
| `xgboost` | gradient boosting | 동일 |
| `lightgbm` | gradient boosting | 동일 |
| `matplotlib` | 기본 플로팅 | `tools/evaluation.py`·`reporting.py` |
| `seaborn` | 통계 시각화 | 동일 |
| `optuna` | 하이퍼파라미터 튜닝 | `tools/modeling.py` |
| `joblib` | 모델 직렬화 | `tools/evaluation.py` 프롬프트 `joblib.dump` |

**예상 추가 설치 크기**: 400-500 MB (.venv). 번들 크기는 Phase 3에서 실측.

### 3.2 범위 외 (본 RFC 이후 별도 RFC)

| 라이브러리 | 사유 |
|----------|-----|
| `torch` / `torchvision` | 2-4 GB. 딥러닝은 본 Epic 범위 밖. 필요 시 `[project.optional-dependencies] dl = [...]` |
| `tensorflow` / `keras` | 동일 |
| `catboost` | 빌드 복잡, 사용자 요구 없으면 보류 |
| `statsmodels` | OK 후보, 현재 프롬프트 미명시 → 추가 안 함 |
| `plotly` / `bokeh` | matplotlib+seaborn만으로 충분, 중복 |
| `scikit-image` / `opencv` | 이미지 도메인 미지원 상태 |
| `pandas-stubs`, `scipy-stubs` | mypy 지원용. 본 Epic과 별개 유지 (post-release) |

## 4. 버전 전략

- 초기엔 **lower bound만** 지정 (`>=x.y`) → 유연한 uv 해석.
- 상한 고정은 CI 안정성 위험 발견 시에 도입.
- 초기 채택 버전 (Phase 1 착수 기준 latest):
  ```
  scikit-learn>=1.5
  xgboost>=2.0
  lightgbm>=4.3
  matplotlib>=3.8
  seaborn>=0.13
  optuna>=3.5
  joblib>=1.3
  ```

## 5. 프롬프트 정합성

### 5.1 Sync 의무

`tools/code_execution.py`의 "Available" 리스트 = `pyproject.toml` `[project.dependencies]`의 ML 서브셋.

자동화: `tests/unit/tools/test_code_execution_prompt_consistency.py`가 CI에서 리스트 파싱 + 실제 import 시도. 불일치 시 fail.

### 5.2 프롬프트 문구

matplotlib 사용 시 backend 명시 (GUI 없는 서버 환경 대응):
```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
```

이 관례는 `tools/evaluation.py`·`reporting.py` 프롬프트 내 예시 코드에 포함.

## 6. 번들 영향 평가 (Phase 3)

| 항목 | 현재 (S-packaging-numpy 직후) | 예상 (Phase 3 완료) |
|------|:--------------:|:---:|
| `_internal/` 크기 | 194 MB | 600-900 MB |
| exe 기동 시간 | ~1s | ~1-2s (numpy/scipy ready) |
| Electron installer | — | +400-700 MB |

사용자 수용. 서명 시간 증가도 수용.

## 7. Rollback

`pyproject.toml` revert + `uv sync` → `.venv` 원상. PyInstaller spec의 hiddenimports는 Phase 3에서 추가될 예정이므로 Phase 1 단독 rollback 단순.

## 8. 후속

- torch 요구 시 `[project.optional-dependencies] dl = ["torch>=2.5"]` 추가 + sandbox frozen 환경에 대한 재평가 RFC.
- 사용자 환경별(Windows/macOS/Linux) xgboost/lightgbm 네이티브 라이브러리 검증은 Phase 3 smoke에 포함.
