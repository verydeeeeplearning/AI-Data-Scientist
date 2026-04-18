# Phase 5: Operations & Continuous Improvement — 운영·모니터링·도메인 확장

**Status**: Pending
**Started**: -
**Last Updated**: 2026-04-13
**Parent**: `PLAN_17_ROADMAP_MASTER.md`
**선행 조건**: Phase 1 (Data Autonomy) + Phase 2 (Runtime Autonomy) 완료
**후행 Phase**: P6 (Advanced Autonomy)

---

## 1. Overview

### 왜 Operations인가

이 단계가 없으면 에이전트는 "분석가"이지 "오너"가 아니다. 현업에서 신뢰받으려면:
- 온라인/오프라인 성능 괴리를 감지하고
- Data drift, concept drift를 모니터링하고
- A/B 테스트를 설계·분석하고
- Retrain vs rollback vs no-action을 판단할 수 있어야 한다

또한 범용 스킬만으로는 도메인별 뉘앙스를 놓친다. 금융·의료·마케팅 각각의 가드레일과 플레이북이 필요하다.

### 성공 기준

- [ ] Drift Monitoring: PSI > 0.1 경고, > 0.2 위험 → 자동 알림
- [ ] A/B Test Analysis: power analysis, SRM check, sequential testing
- [ ] Retrain/Rollback Decision: 자동 판단 프레임워크
- [ ] Domain Skill Packs: 금융/의료/마케팅 중 1개 이상 완성
- [ ] ExperimentDesignHook: 실험 관련 분석에서 자동 트리거

---

## 2. Architecture Decisions (Clean Architecture)

### Layer Mapping

| Layer | Components | Responsibility |
|-------|-----------|---------------|
| **Domain** | `DriftMetric` (VO), `ExperimentResult` (VO), `RemediationDecision` (VO) | 드리프트 지표, 실험 결과, 대응 판단 |
| **Application** | `DriftAnalyzer`, `ABTestAnalyzer`, `RemediationService`, `ExperimentDesignHook`, `DriftDetectionHook` | 드리프트 분석, A/B 분석, 대응 결정, 자동 트리거 |
| **Infrastructure** | `ModelMonitorSensor` 활성화, `DriftStore`, `ExperimentStore` | 센서 데이터 수집, 영구 저장 |
| **Presentation** | `drift_monitor`, `ab_test` tools | LLM에 노출되는 도구 |

---

## 3. Implementation Phases (TDD)

### Phase 5-1: Drift Monitoring

**Goal**: 모델 입력/출력 분포 변화를 자동으로 감지하고 알림

#### RED: Write Failing Tests First

- [ ] **Test 5-1.1**: PSI 계산 정확성
  - File: `tests/unit/application/test_drift_analyzer.py`
  - Scenario: 기준 분포 [0.3, 0.3, 0.4] vs 현재 [0.2, 0.3, 0.5] → PSI 계산
  - Expected: Tests FAIL

- [ ] **Test 5-1.2**: KL Divergence 계산
  - File: `tests/unit/application/test_drift_analyzer.py`
  - Scenario: 두 분포 → KL divergence 값
  - Expected: Tests FAIL

- [ ] **Test 5-1.3**: 임계치 기반 알림
  - File: `tests/unit/application/test_drift_analyzer.py`
  - Scenario: PSI > 0.2 → "danger" 레벨 알림
  - Expected: Tests FAIL

- [ ] **Test 5-1.4**: 피처별 드리프트 분석
  - File: `tests/unit/application/test_drift_analyzer.py`
  - Scenario: 10개 피처 → 각각 PSI 계산 → 상위 3개 드리프트 피처 식별
  - Expected: Tests FAIL

- [ ] **Test 5-1.5**: `DriftDetectionHook` — 모델 평가 시 자동 드리프트 체크
  - File: `tests/unit/application/test_drift_hook.py`
  - Scenario: evaluate_model 완료 시 → 학습 데이터 vs 평가 데이터 분포 비교
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 5-1.6**: Domain Value Object
  - File: `src/ds_agent/domain/value_objects/drift.py`
  - `DriftMetric`: feature_name, metric_type (PSI/KL/KS), value, threshold, level (ok/warning/danger)
  - `DriftReport`: metrics (List[DriftMetric]), overall_status, top_drifting_features, timestamp

- [ ] **Task 5-1.7**: DriftAnalyzer
  - File: `src/ds_agent/application/services/drift_analyzer.py`
  - PSI 계산: `Σ (P_i - Q_i) × ln(P_i / Q_i)` (binning + smoothing)
  - KL Divergence: `Σ P_i × ln(P_i / Q_i)`
  - KS Test: `scipy.stats.ks_2samp()`
  - 피처별 분석 + 전체 요약

- [ ] **Task 5-1.8**: `DriftDetectionHook`
  - File: `src/ds_agent/agent/ds_workflow_hooks.py`
  - Priority: 60
  - `post_tool_use()`: evaluate_model 또는 deploy_model 완료 시 트리거
  - 학습 데이터 분포 vs 현재 데이터 분포 비교
  - drift.detected 이벤트 emit

- [ ] **Task 5-1.9**: `drift_monitor` Tool
  - File: `src/ds_agent/tools/drift_tools.py`
  - Parameters: reference_data (또는 path), current_data (또는 path), features (optional)
  - 결과: DriftReport (피처별 PSI, 전체 상태, 권장 조치)

- [ ] **Task 5-1.10**: Standing Order 연동
  - "매일 12:00에 운영 중 모델의 입력 분포 체크" standing order
  - drift 감지 시 자동 보고서 생성 + Telegram/Slack 알림

#### Quality Gate

- [ ] PSI 계산 정확성 검증 (알려진 분포로 검증)
- [ ] 임계치 알림 동작 확인
- [ ] 피처별 드리프트 식별 정확성

---

### Phase 5-2: A/B Test Analysis

**Goal**: 실험 설계·분석 자동화 — power analysis, SRM check, sequential testing

#### RED: Write Failing Tests First

- [ ] **Test 5-2.1**: Power Analysis — 필요 표본 크기 계산
  - File: `tests/unit/application/test_ab_test.py`
  - Scenario: effect_size=0.05, alpha=0.05, power=0.8 → 필요 표본 크기 N
  - Expected: Tests FAIL

- [ ] **Test 5-2.2**: SRM Check — 샘플 비율 불일치 감지
  - File: `tests/unit/application/test_ab_test.py`
  - Scenario: expected 50/50 vs actual 48/52 (N=10000) → SRM p-value 계산
  - Expected: Tests FAIL

- [ ] **Test 5-2.3**: 유의성 판정 — t-test / chi-squared
  - File: `tests/unit/application/test_ab_test.py`
  - Scenario: 처리군 vs 대조군 데이터 → p-value, 신뢰구간, 효과 크기
  - Expected: Tests FAIL

- [ ] **Test 5-2.4**: `ExperimentDesignHook` — 실험 분석 시 자동 체크
  - File: `tests/unit/application/test_experiment_design_hook.py`
  - Scenario: 실험 데이터 분석 시 → SRM check 자동 실행 → power 충분성 확인
  - Expected: Tests FAIL

- [ ] **Test 5-2.5**: 조기 중단 판단 — Sequential Testing
  - File: `tests/unit/application/test_ab_test.py`
  - Scenario: 중간 결과에서 유의미 → 조기 중단 가능 여부 판단
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 5-2.6**: ABTestAnalyzer
  - File: `src/ds_agent/application/services/ab_test_analyzer.py`
  - `power_analysis(effect_size, alpha, power, test_type) → SampleSize`
  - `srm_check(control_n, treatment_n, expected_ratio) → SRMResult`
  - `analyze(control_data, treatment_data, metric_type) → ExperimentResult`
  - `sequential_test(data_stream, alpha_spending) → EarlyStopDecision`

- [ ] **Task 5-2.7**: `ExperimentDesignHook`
  - File: `src/ds_agent/agent/ds_workflow_hooks.py`
  - Priority: 42
  - 실험 관련 도구 사용 시 자동 트리거:
    - 데이터에 treatment/control 구분 → SRM check
    - A/B 분석 → power 충분성 확인
    - 결과 해석 → multiple comparison correction 권고

- [ ] **Task 5-2.8**: `ab_test` Tool
  - File: `src/ds_agent/tools/ab_test_tools.py`
  - Actions: design (power analysis), check (SRM + validity), analyze (결과 분석)

#### Quality Gate

- [ ] Power analysis 계산 정확성 (scipy 결과와 비교)
- [ ] SRM 감지 정확성
- [ ] Sequential testing 정확성

---

### Phase 5-3: Retrain/Rollback Decision

**Goal**: drift 또는 성능 저하 감지 시 자동 판단 프레임워크

#### RED: Write Failing Tests First

- [ ] **Test 5-3.1**: 판단 매트릭스 — 상황별 올바른 결정
  - File: `tests/unit/application/test_remediation.py`
  - Scenario: PSI > 0.2 + 성능 -5% → "retrain" 권고
  - Scenario: PSI < 0.1 + 성능 -2% → "no_action" (노이즈)
  - Scenario: 갑작스런 성능 -20% → "rollback" + 긴급 알림
  - Expected: Tests FAIL

- [ ] **Test 5-3.2**: Retrain 트리거 — standing order 연동
  - File: `tests/unit/application/test_remediation.py`
  - Scenario: retrain 결정 → 자동 모델 재학습 트리거
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 5-3.3**: RemediationService
  - File: `src/ds_agent/application/services/remediation_service.py`
  - 판단 매트릭스:
    | PSI | 성능 변화 | 결정 |
    |-----|---------|------|
    | < 0.1 | < -2% | no_action (노이즈) |
    | < 0.1 | -2% ~ -5% | monitor (주시) |
    | 0.1 ~ 0.2 | < -5% | retrain (권고) |
    | > 0.2 | any | retrain (긴급) |
    | any | > -10% | rollback + 긴급 알림 |

- [ ] **Task 5-3.4**: `retrain-vs-rollback` Skill
  - File: `src/ds_agent/skills/builtin/retrain-vs-rollback.md`
  - 의사결정 트리 + 근거 기록 가이드

#### Quality Gate

- [ ] 판단 매트릭스 정확성
- [ ] 긴급 상황 에스컬레이션 동작

---

### Phase 5-4: Domain Skill Packs

**Goal**: 금융·의료·마케팅 도메인별 가드레일과 플레이북

#### RED: Write Failing Tests First

- [ ] **Test 5-4.1**: 금융 스킬 로딩 및 적용
  - File: `tests/unit/skills/test_domain_skills.py`
  - Scenario: 금융 도메인 설정 → financial-ts-modeling 스킬 활성화
  - Expected: Tests FAIL

- [ ] **Test 5-4.2**: 도메인 가드레일 — walk-forward validation 강제
  - File: `tests/unit/skills/test_domain_skills.py`
  - Scenario: 금융 시계열 + random split → WARNING (walk-forward 사용 권고)
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 5-4.3**: 금융 도메인 Pack
  - Files: `src/ds_agent/skills/domain/finance/`
  - `financial-ts-modeling.md`:
    - Walk-forward validation 필수
    - Regime awareness (시장 국면 변화)
    - Look-ahead bias 검사 강화
  - `risk-metric-suite.md`:
    - VaR, Expected Shortfall, Sharpe Ratio
    - 규제 보고 형식 (Basel III)
  - `look-ahead-bias-guard.md`:
    - LeakageDetectionHook에 금융 특화 패턴 추가
    - 미래 가격 참조, 사후 분류 기준 사용 등

- [ ] **Task 5-4.4**: 의료 도메인 Pack
  - Files: `src/ds_agent/skills/domain/healthcare/`
  - `survival-analysis.md`:
    - Censoring 처리 (right/left/interval)
    - Cox PH 비례위험 가정 검증
    - Kaplan-Meier, log-rank test
  - `hipaa-compliance.md`:
    - 자동 de-identification (Safe Harbor / Expert Determination)
    - 18개 HIPAA identifier 목록
    - 감사 로그 강화

- [ ] **Task 5-4.5**: 마케팅 도메인 Pack
  - Files: `src/ds_agent/skills/domain/marketing/`
  - `uplift-modeling.md`:
    - CATE (Conditional Average Treatment Effect) 추정
    - S-learner, T-learner, X-learner, Causal Forest
    - 처치군/대조군 설계 가이드
  - `attribution-modeling.md`:
    - Last-touch, multi-touch, Shapley value
    - 채널 중복, 시간 지연 효과 보정
  - `ltv-prediction.md`:
    - Contractual vs non-contractual 모델
    - BG/NBD, Pareto/NBD
    - 코호트 기반 LTV

- [ ] **Task 5-4.6**: 도메인 Pack 로더
  - File: `src/ds_agent/skills/domain_pack_loader.py`
  - Config에서 `domain_pack: finance` 설정 → 해당 도메인 스킬 자동 로딩
  - 기존 SkillHub의 progressive disclosure와 통합

- [ ] **Task 5-4.7**: 도메인별 가드레일 Hook 확장
  - Config 기반으로 도메인별 추가 검증 규칙 활성화
  - 금융: walk-forward 강제, look-ahead bias 강화
  - 의료: HIPAA compliance check, censoring 처리 확인
  - 마케팅: SUTVA 가정 확인, uplift vs prediction 구분

#### Quality Gate

- [ ] 도메인 스킬 로딩 정확성
- [ ] 가드레일 동작 확인 (위반 시 WARNING)
- [ ] 기존 범용 스킬과 충돌 없음

---

### Phase 5-5: Parallel Experiment Execution (Nice-to-have)

**Goal**: 예산 내 최대 병렬 실험

#### RED: Write Failing Tests First

- [ ] **Test 5-5.1**: 2개 실험 병렬 실행
  - File: `tests/unit/application/test_parallel_experiment.py`
  - Scenario: exp-A (LightGBM) + exp-B (XGBoost) 동시 실행 → 두 결과 비교
  - Expected: Tests FAIL

- [ ] **Test 5-5.2**: 예산 분배 — 병렬 실험 간 예산 균등 분배
  - File: `tests/unit/application/test_parallel_experiment.py`
  - Scenario: 총 예산 $10 / 2 실험 → 각 $5
  - Expected: Tests FAIL

#### GREEN: Implement to Make Tests Pass

- [ ] **Task 5-5.3**: Parallel Experiment Manager
  - Subagent Framework (P2-4) 활용
  - 각 실험을 독립 subagent로 실행
  - 결과 merge + 최고 실험 선택

#### Quality Gate

- [ ] 병렬 실행 정확성 (결과 간 간섭 없음)
- [ ] 예산 분배 동작 확인

---

## 4. 모니터링 항목 매트릭스

| 대상 | 메트릭 | 임계치 | 조치 | 구현 |
|------|--------|--------|------|------|
| 입력 데이터 분포 | PSI, KL divergence | PSI > 0.1 경고, > 0.2 위험 | Retrain 제안 | P5-1 |
| 모델 성능 | Accuracy, Precision, Recall | 기준선 -5% 경고, -10% 위험 | 원인 분석 → retrain/rollback | P5-3 |
| 데이터 품질 | 결측률, 스키마 변동 | 결측률 >10%, 새 컬럼 출현 | 데이터 엔지니어 알림 | P5-1 |
| 피처 중요도 | Permutation importance drift | 상위 순위 변동 >30% | 피처 재설계 검토 | P5-1 |
| 예측 분포 | 예측값 분포 변화 | KS test p < 0.01 | 원인 분석 | P5-1 |

---

## 5. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| PSI 계산에서 빈 bin 발생 (log(0)) | 중 | 높음 | Laplace smoothing 적용 |
| A/B 테스트 오판 (false positive) | 중 | 높음 | Multiple comparison correction, sequential testing |
| Retrain 자동 트리거 비용 | 중 | 중간 | 비용 가드 + 승인 게이트 (auto가 아닌 권고) |
| 도메인 스킬 부정확 | 중 | 높음 | 도메인 전문가 리뷰, 테스트 케이스 |
| 병렬 실험 리소스 경쟁 | 중 | 중간 | 리소스 락, 순차 fallback |

---

## 6. Progress Tracking

- Phase 5-1 (Drift Monitoring): 0%
- Phase 5-2 (A/B Test Analysis): 0%
- Phase 5-3 (Retrain/Rollback): 0%
- Phase 5-4 (Domain Skill Packs): 0%
- Phase 5-5 (Parallel Experiments): 0%
- **Overall Phase 5**: 0%

---

## Notes & Learnings

- [구현 중 발견 사항 기록]
