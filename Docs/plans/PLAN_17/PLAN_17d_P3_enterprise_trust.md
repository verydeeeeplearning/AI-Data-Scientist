# Phase 3: Enterprise Trust — 엔터프라이즈 신뢰·거버넌스

**Status**: Pending
**Started**: -
**Last Updated**: 2026-04-13
**Parent**: `PLAN_17_ROADMAP_MASTER.md`
**선행 조건**: Phase 1 (Data Autonomy) + Phase 2 (Runtime Autonomy) 완료
**후행 Phase**: P6 (Advanced Autonomy)

---

## 1. Overview

### 왜 Enterprise Trust인가

에이전트가 자율적으로 데이터에 접근하고 장시간 실행하게 되면, "왜 이렇게 했는지"를 남기고, "어디까지 허용할지"를 정밀하게 제어하는 체계가 필수다. "잘했다"보다 **"왜 믿어야 하는가"**가 중요하다.

현재 3단계 supervision mode (auto/supervised/step-by-step)는 "도구 수준" 접근 제어다. 현업에서는 **action × data sensitivity × environment × confidence** 기반의 다차원 정책이 필요하다.

### 성공 기준

- [ ] Policy-Based Approval: action × sensitivity × env × confidence 기반 승인 동작
- [ ] Full Lineage: dataset → feature recipe → model config → evaluation → deployment 추적
- [ ] PIIRedactionHook: PII 컬럼 자동 감지 + 마스킹 동작
- [ ] Experiment Registry: 로그 → 운영 체계 승격 (snapshot + recipe + decision memo)
- [ ] Reproducibility: 실험 코드를 재현 가능한 형태로 내보내기

---

## 2. Architecture Decisions (Clean Architecture)

### Layer Mapping

| Layer | Components | Responsibility |
|-------|-----------|---------------|
| **Domain** | `ApprovalPolicy` (Entity), `LineageRecord` (Entity), `PIIClassification` (VO) | 승인 정책 규칙, 계보 레코드, PII 분류 |
| **Application** | `PolicyEvaluator`, `LineageCaptureService`, `PIIRedactionHook`, `MetricContractHook` | 정책 평가, 계보 수집, PII 마스킹, 지표 계약 |
| **Infrastructure** | `ApprovalPolicyStore`, `LineageStore`, `PIIDetector` (regex + NER) | 정책 저장, 계보 저장, PII 탐지 엔진 |
| **Presentation** | `policy_check` tool, `lineage_capture` tool | LLM에 노출되는 도구 |

### OpenClaw 참조 패턴

| OpenClaw 패턴 | DS Agent 적용 |
|--------------|--------------|
| Three-Level Security ("deny"/"allowlist"/"full") | Policy-Based Approval의 기본 수준 |
| Approval Socket (Unix socket + token) | 외부 승인 핸들러 연동 |
| File Operand SHA256 Tracking | 데이터셋 snapshot hash로 재현성 보장 |
| Approval Request TTL (30min timeout) | 승인 대기 타임아웃 |
| Command Preview (safe truncated) | SQL 쿼리 미리보기 (비밀 마스킹) |
| Ask Levels ("off"/"on-miss"/"always") | Approval fatigue 관리 |

---

## 3. Implementation Phases (TDD)

### Phase 3-1: Policy-Based Approval

**Goal**: action × sensitivity × env × confidence 기반 다차원 승인 제어

#### RED: Write Failing Tests First

- [ ] **Test 3-1.1**: 정책 매칭 — action + sensitivity 조합
  - File: `tests/unit/application/test_policy_evaluator.py`
  - Scenario: action="sql_query" + data_sensitivity="pii" → approval_required
  - Expected: Tests FAIL

- [ ] **Test 3-1.2**: 정책 매칭 — 저위험 작업 자동 승인
  - File: `tests/unit/application/test_policy_evaluator.py`
  - Scenario: action="file_read" + sensitivity="public" + env="dev" → auto_approve
  - Expected: Tests FAIL

- [ ] **Test 3-1.3**: Standing Approval — 반복 승인 패턴 학습
  - File: `tests/unit/application/test_policy_evaluator.py`
  - Scenario: 같은 action 3회 연속 승인 → 4번째부터 auto (standing approval)
  - Expected: Tests FAIL

- [ ] **Test 3-1.4**: Confidence 기반 — 에이전트 확신도 낮을 때 승인 요구
  - File: `tests/unit/application/test_policy_evaluator.py`
  - Scenario: confidence < 0.5 + action="model_deploy" → approval_required
  - Expected: Tests FAIL

- [ ] **Test 3-1.5**: 비가역 작업 이중 확인
  - File: `tests/unit/application/test_policy_evaluator.py`
  - Scenario: action="delete_file" → double_check (두 번 확인)
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 3-1.6**: Domain Entity
  - File: `src/ds_agent/domain/entities/approval_policy.py`
  - `ApprovalPolicy`:
    - rules: List[PolicyRule]
    - standing_approvals: Dict[str, StandingApproval]
  - `PolicyRule`:
    - action_pattern: glob (예: "sql_*", "file_write", "*")
    - data_sensitivity: public / internal / pii / restricted
    - environment: dev / staging / prod
    - confidence_threshold: float (0.0 ~ 1.0)
    - decision: auto / approval / double_check / deny

- [ ] **Task 3-1.7**: Application Service
  - File: `src/ds_agent/application/services/policy_evaluator.py`
  - `PolicyEvaluator`:
    - `evaluate(action, sensitivity, env, confidence) → PolicyDecision`
    - `record_approval(action, approved_by)` → standing approval 후보
    - `promote_to_standing(action)` → 반복 승인 → auto로 승격

- [ ] **Task 3-1.8**: PermissionHook 확장
  - 기존 `PermissionHook`에 PolicyEvaluator 통합
  - 기존 3-mode 호환 유지 + 정책 기반 세분화 추가

- [ ] **Task 3-1.9**: 정책 설정 Config
  ```yaml
  approval:
    default_mode: policy  # legacy(3-mode) / policy(new)
    rules:
      - action: "sql_query"
        data_sensitivity: pii
        decision: approval
      - action: "file_read"
        decision: auto
      - action: "model_deploy"
        confidence_threshold: 0.7
        decision: approval
    standing_approval:
      threshold: 3  # N회 연속 승인 시 자동화
  ```

#### Quality Gate

- [ ] 정책 매칭 정확성 확인
- [ ] Standing approval 동작 확인
- [ ] 기존 3-mode 호환성 유지

---

### Phase 3-2: Full Lineage Capture

**Goal**: dataset snapshot → feature recipe → model config → evaluation → deployment 전체 추적

#### RED: Write Failing Tests First

- [ ] **Test 3-2.1**: 데이터셋 lineage 기록
  - File: `tests/unit/application/test_lineage_service.py`
  - Scenario: data_loader 실행 → {file_path, sha256, schema, row_count, timestamp} 기록
  - Expected: Tests FAIL

- [ ] **Test 3-2.2**: 피처 레시피 lineage
  - File: `tests/unit/application/test_lineage_service.py`
  - Scenario: feature_engineer 실행 → {변환 코드, 파라미터, 순서, input_data_hash} 기록
  - Expected: Tests FAIL

- [ ] **Test 3-2.3**: 모델 config lineage
  - File: `tests/unit/application/test_lineage_service.py`
  - Scenario: model_trainer 실행 → {하이퍼파라미터, 랜덤 시드, 환경 정보} 기록
  - Expected: Tests FAIL

- [ ] **Test 3-2.4**: End-to-end lineage 조회
  - File: `tests/unit/application/test_lineage_service.py`
  - Scenario: 모델 ID → 전체 계보 (데이터 → 피처 → 모델 → 평가) 역추적
  - Expected: Tests FAIL

- [ ] **Test 3-2.5**: Decision Memo 기록
  - File: `tests/unit/application/test_lineage_service.py`
  - Scenario: 모델 선택 시 → "LightGBM 선택 이유: baseline 대비 +5%, 해석 가능성" 기록
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 3-2.6**: Domain Entity
  - File: `src/ds_agent/domain/entities/lineage.py`
  - `LineageRecord`:
    - id, record_type (dataset / feature / model / evaluation / deployment / decision)
    - parent_id (이전 단계 참조)
    - content: dict (유형별 상세 정보)
    - session_id, timestamp

- [ ] **Task 3-2.7**: Application Service
  - File: `src/ds_agent/application/services/lineage_capture_service.py`
  - `LineageCaptureService`:
    - `capture_dataset(path, schema, row_count)` → sha256 자동 계산
    - `capture_feature(code, params, input_data_id)`
    - `capture_model(hyperparams, seed, env_info, feature_id)`
    - `capture_evaluation(metrics, holdout_data_id, model_id)`
    - `capture_decision(what, why, alternatives_considered)`
    - `trace(model_id) → List[LineageRecord]` — 전체 계보 역추적

- [ ] **Task 3-2.8**: Hook 통합 — 자동 lineage 수집
  - 기존 Hook의 post_tool_use에서 자동으로 LineageCaptureService 호출:
    - `data_loader` 완료 → capture_dataset
    - `feature_engineer` 완료 → capture_feature
    - `train_model` 완료 → capture_model
    - `evaluate_model` 완료 → capture_evaluation

- [ ] **Task 3-2.9**: Infrastructure — LineageStore
  - File: `src/ds_agent/infrastructure/persistence/lineage_store.py`
  - SQLite 테이블: lineage_records (id, type, parent_id, content_json, session_id, created_at)
  - 인덱스: parent_id, session_id

- [ ] **Task 3-2.10**: `lineage_capture` Tool
  - LLM이 명시적으로 decision memo를 기록하거나 계보를 조회할 수 있는 인터페이스

#### Quality Gate

- [ ] 전체 파이프라인에서 자동 lineage 수집 확인
- [ ] 역추적 조회 정확성 확인
- [ ] Decision memo 기록 확인

---

### Phase 3-3: PIIRedactionHook

**Goal**: PII 컬럼 자동 감지 및 마스킹 강제

#### RED: Write Failing Tests First

- [ ] **Test 3-3.1**: PII 패턴 감지 — 이메일, 전화번호, 주민번호
  - File: `tests/unit/application/test_pii_redaction.py`
  - Scenario: DataFrame에 "email" 컬럼 → PII_DETECTED 경고
  - Expected: Tests FAIL

- [ ] **Test 3-3.2**: 자동 마스킹 — PII 컬럼 해싱
  - File: `tests/unit/application/test_pii_redaction.py`
  - Scenario: PII 감지 + auto_mask=true → 컬럼값 SHA256 해싱
  - Expected: Tests FAIL

- [ ] **Test 3-3.3**: 보고서 내 PII 차단
  - File: `tests/unit/application/test_pii_redaction.py`
  - Scenario: generate_report 결과에 이메일 주소 포함 → WARNING + 마스킹
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 3-3.4**: `PIIRedactionHook` 구현
  - File: `src/ds_agent/agent/builtin_hooks.py`
  - Priority: 12 (PermissionHook=10 이후)
  - 감지 패턴:
    - 컬럼명: email, phone, ssn, address, name, birthday, ip_address
    - 데이터 패턴: 이메일 regex, 전화번호 regex, 주민번호 regex
    - 타입: 자유 텍스트 필드 (잠재적 PII)
  - 대응: WARNING (기본) 또는 자동 마스킹 (config 설정)

- [ ] **Task 3-3.5**: PIIDetector
  - File: `src/ds_agent/infrastructure/pii_detector.py`
  - Regex 기반 패턴 매칭 + 컬럼명 규칙
  - 확장 가능: NER 모델 (Phase 6)

#### Quality Gate

- [ ] 알려진 PII 패턴 전부 감지
- [ ] 오탐률 허용 범위 (경고만이므로 높아도 무방)
- [ ] 마스킹 후 원본 복원 불가 확인 (단방향 해시)

---

### Phase 3-4: Experiment Registry 승격

**Goal**: ExperimentLog를 운영 수준 레지스트리로 승격

#### RED: Write Failing Tests First

- [ ] **Test 3-4.1**: 실험에 dataset snapshot hash 연결
  - File: `tests/unit/infrastructure/test_experiment_registry.py`
  - Scenario: 실험 기록 시 input data SHA256 자동 첨부
  - Expected: Tests FAIL

- [ ] **Test 3-4.2**: 실험 비교 — 2개 실험의 차이점 자동 추출
  - File: `tests/unit/infrastructure/test_experiment_registry.py`
  - Scenario: exp-001 vs exp-002 → {changed: [features, model], same: [data, eval_set]}
  - Expected: Tests FAIL

- [ ] **Test 3-4.3**: 실험 트리 조회 — parent-child 관계
  - File: `tests/unit/infrastructure/test_experiment_registry.py`
  - Scenario: exp-001의 children 조회 → [exp-002, exp-003]
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 3-4.4**: ExperimentLog 확장
  - 기존 JSONL 구조에 추가 필드:
    - `parent_experiment_id` (실험 분기)
    - `dataset_hash` (입력 데이터 해시)
    - `feature_recipe_hash` (피처 변환 코드 해시)
    - `decision_memo` (이 실험을 왜 시작했는지)
    - `deployment_link` (배포 위치, 있으면)

- [ ] **Task 3-4.5**: 실험 비교 유틸리티
  - File: `src/ds_agent/memory/experiment_compare.py`
  - `compare(exp_id_1, exp_id_2) → ExperimentDiff`

- [ ] **Task 3-4.6**: 실험 트리 조회
  - `get_tree(root_exp_id) → ExperimentTree`

#### Quality Gate

- [ ] 실험 기록에 dataset/feature hash 포함
- [ ] 실험 비교 결과 정확성
- [ ] 기존 ExperimentLog 호환성 유지

---

### Phase 3-5: Reproducibility Pipeline

**Goal**: 실험 코드를 재현 가능한 파이프라인으로 내보내기

#### RED: Write Failing Tests First

- [ ] **Test 3-5.1**: 실험을 독립 실행 가능한 Python 스크립트로 내보내기
  - File: `tests/unit/application/test_reproducibility.py`
  - Scenario: exp-006 → standalone_script.py (데이터 로딩 → 피처 → 모델 → 평가)
  - Expected: Tests FAIL

- [ ] **Test 3-5.2**: 환경 정보 캡처 — requirements.txt / pyproject.toml 생성
  - File: `tests/unit/application/test_reproducibility.py`
  - Scenario: 실험에 사용된 라이브러리 버전 → requirements.txt
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 3-5.3**: Reproducibility Exporter
  - File: `src/ds_agent/application/services/reproducibility_exporter.py`
  - `export_experiment(exp_id, format)`:
    - format="script" → Python 스크립트
    - format="notebook" → Jupyter 노트북
    - format="kedro" → Kedro 프로젝트 스켈레톤 (Phase 6)
  - 포함 항목: 데이터 경로, 피처 코드, 모델 설정, 평가 코드, 랜덤 시드, 환경 정보

- [ ] **Task 3-5.4**: 환경 스냅샷
  - Python 버전, pip freeze 결과 캡처
  - 실험 기록에 자동 첨부

#### Quality Gate

- [ ] 내보낸 스크립트가 독립적으로 실행 가능
- [ ] 동일 데이터 → 동일 결과 재현 확인 (seed 고정)

---

## 4. 정책 승인 매트릭스 (최종)

| Action | Data Sensitivity | Env | Confidence | Decision |
|--------|-----------------|-----|-----------|----------|
| file_read | public | any | any | **auto** |
| file_read | pii | any | any | **approval** |
| sql_query (SELECT) | internal | dev | any | **auto** |
| sql_query (SELECT) | pii | prod | any | **approval** |
| execute_code | any | any | any | **auto** (sandbox 격리) |
| train_model | any | any | any | **auto** |
| deploy_model | any | prod | < 0.7 | **approval** |
| deploy_model | any | prod | ≥ 0.7 | **auto** + audit |
| web_search | any | any | any | **auto** |
| file_write | any | prod | any | **approval** |
| delete | any | any | any | **double_check** |

### Approval Fatigue 방지

- Anthropic 데이터: 승인 요청의 93%가 승인됨
- 전략: 대부분을 자동화하고 예외만 사람이 보는 구조
- Standing Approval: 3회 연속 승인 → auto로 승격 + 감사 로그

---

## 5. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 정책 설정 오류로 민감 데이터 노출 | 낮음 | 매우높음 | 기본값은 restrictive, 명시적 허용만 |
| PII 오탐으로 분석 방해 | 중 | 낮음 | 경고만 (DENY 아님), 사용자 override 가능 |
| Lineage 저장 오버헤드 | 중 | 낮음 | 비동기 기록, 배치 저장 |
| Reproducibility 스크립트 실행 실패 | 중 | 중간 | 환경 스냅샷 포함, Docker 기반 재현 (선택적) |

---

## 6. Progress Tracking

- Phase 3-1 (Policy-Based Approval): 0%
- Phase 3-2 (Full Lineage Capture): 0%
- Phase 3-3 (PIIRedactionHook): 0%
- Phase 3-4 (Experiment Registry 승격): 0%
- Phase 3-5 (Reproducibility Pipeline): 0%
- **Overall Phase 3**: 0%

---

## Notes & Learnings

- [구현 중 발견 사항 기록]
