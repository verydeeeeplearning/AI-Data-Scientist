# DS Agent Productization — Implementation Plan Index

**기준 문서**: `Docs/DS_AGENT_PRODUCTIZATION_REQUIREMENTS_2026-04-14.md`
**작성일**: 2026-04-14
**핵심 원칙**: 자율형 Agent 정체성 유지 — LLM is the orchestrator, 제품화는 LLM의 판단을 돕는 레이어

---

## 불변 원칙 (모든 계획에 공통 적용)

> LLM is the orchestrator. 코드가 flow를 결정하지 않는다.
> 제품화 작업은 LLM이 더 나은 환경에서 자율적으로 동작하도록 돕는 것이지,
> LLM의 판단을 하드코딩으로 대체하는 것이 아니다.

---

## Milestone A: Product Safety Baseline (P0 — 베타 출시 차단 조건)

| # | 파일 | 요구사항 섹션 | 상태 |
|---|------|-------------|------|
| P0-01 | [코드 실행 샌드박싱](./P0_01_code_execution_sandbox.md) | 5.11.A | Complete |
| P0-02 | [자격증명 보안 저장](./P0_02_secure_credential_storage.md) | 5.3 | Complete (코드) / 멀티플랫폼 keyring 실측 대기 |
| P0-03 | [시작 진단 및 복구](./P0_03_startup_diagnostics_recovery.md) | 5.8 | Complete |
| P0-04 | [설정/데이터 마이그레이션](./P0_04_config_migration_framework.md) | 5.9 | Complete (config.yaml) / 타 저장소는 post-beta |
| P0-05 | [코드 서명 및 배포 파이프라인](./P0_05_code_signing_distribution.md) | 5.1 | In Progress |
| P0-06 | [패키지 QA & 스모크 테스트](./P0_06_packaged_qa_smoke_tests.md) | 5.14 | In Progress |
| P0-07 | [관찰 가능성 & 크래시 리포팅](./P0_07_observability_crash_reporting.md) | 5.13 | Complete (코드) / DSN 조달 대기 |

---

## Milestone B: End-User Product UX (P1 — Public Beta 품질)

| # | 파일 | 요구사항 섹션 | 상태 |
|---|------|-------------|------|
| P1-08 | [Use-case 기반 온보딩](./P1_08_usecase_onboarding.md) | 5.2 | Complete |
| P1-09 | [Provider/Model 추상화 UX](./P1_09_provider_model_abstraction_ux.md) | 5.4 | Complete |
| P1-10 | [데이터 수집 UX](./P1_10_data_import_ux.md) | 5.5 | Complete |
| P1-11 | [비용 거버넌스 & 사용량 제어](./P1_11_cost_governance_usage.md) | 5.12 | Complete |
| P1-12 | [결과물 Export & 리포팅](./P1_12_artifact_export_reporting.md) | 5.7 | Complete |
| P1-13 | [i18n (한국어) & 접근성](./P1_13_i18n_accessibility.md) | 5.18 | Complete |
| P1-14 | [자동 업데이트 & 릴리스](./P1_14_auto_update_release.md) | 5.10 | In Progress |

---

## Milestone C: Release Operations (P0/P1 완료 후)

P0-05 (코드 서명), P0-06 (QA), P1-14 (자동 업데이트) 계획에 통합.

---

## Milestone D: Team & Enterprise (P2) — **베타 이후로 연기**

개인/팀 소규모 베타 런치 범위를 초과하는 기능. 엔터프라이즈 조달 요구가 발생한
시점에 재개. 현재 구현분(organization_store, admin console 일부)은 유지하되
**신규 feature 작업은 중단**.

| # | 파일 | 요구사항 섹션 | 상태 |
|---|------|-------------|------|
| P2-15 | [팀/엔터프라이즈 제어](./P2_15_team_enterprise_controls.md) | 5.16 | Deferred (post-beta) |
| P2-16 | [확장성 & 마켓플레이스](./P2_16_extensibility_marketplace.md) | 5.19 | Deferred (post-beta) |

---

## P0 완료 체크리스트 (베타 배포 차단 조건)

- [x] P0-01: Agent 생성 코드가 workspace 외부 파일 접근 시 자동 차단 확인 (런타임 preamble + 기존 정적 분석 2중 방어 + Phase 3 UI: blocking approval modal & violation toast 완료 2026-04-15)
- [x] P0-02: 디스크 상 평문 secret 저장 제거 (token_store.py, config schema)
- [x] P0-03: backend 시작 실패 원인 UI에서 분류/표시 가능
- [x] P0-04: 구버전 config 파일로 신버전 앱 실행 가능 (migration runner 동작)
- [~] P0-05: CI 서명 파이프라인 + electron-builder/spec 설정 완료. SmartScreen 통과는 EV 인증서 조달 후 실행 필요
- [~] P0-06: backend binary smoke green (5/5) + Electron diagnostic-window smoke green. Signed-installer clean-install/first-analysis E2E 는 P0-05 후속 작업
- [x] P0-07a: 1 클릭으로 support bundle export 가능
- [x] P0-07b: Sentry 기반 backend/Electron crash reporting 통합 완료 (`sentry_backend.py` + `@sentry/electron/main`). DSN 만 조달하면 활성화
- [x] P0-07c: `DSA-XXX-YYY` 에러 코드 카탈로그 (`api/error_mapping.py`) + 온보딩 telemetry consent 3-choice UI 구현됨

---

## 현재 코드베이스 핵심 파일 레퍼런스

```
src/ds_agent/
├── infrastructure/secrets/secret_storage.py      # [P0-02] OS keyring + fallback secret storage
├── infrastructure/secrets/config_secret_manager.py # [P0-02] config-backed secret migration/hydration
├── infrastructure/auth/token_store.py            # [P0-02] metadata-only auth profile store + secure payloads
├── config/schema.py                              # [P0-02] ProviderConfig.api_keys 제거 완료
├── config/loader.py                       # [P0-04] version 필드 추가, migration 진입점
├── api/config_manager.py                  # [P0-02][P0-04] persistent config 관리

electron/src/main/
├── secret-vault.ts                        # [P0-02] desktop safeStorage vault 구현 완료
├── ipc.ts                                 # [P0-02] desktop secret IPC surface 구현 완료
├── python-backend.ts                      # [P0-02][P0-03] backend launch env / 시작 진단 강화
├── index.ts                               # [P0-03] 실패 시 diagnostic panel 진입점
├── window.ts

electron/src/preload/
├── index.ts                               # [P0-02] renderer용 secret bridge 구현 완료

electron/src/renderer/components/
├── settings/SettingsPanel.tsx             # [P0-02] desktop secret 저장 UX 전환 구현 완료
├── settings/OnboardingWizard.tsx          # [P0-02] desktop onboarding secret 저장 전환 구현 완료
├── layout/DisconnectOverlay.tsx           # [P0-03] root-cause 분류 UI 추가 대상

electron/src/renderer/hooks/
├── useProviderAuth.ts                     # [P0-02] desktop vault masked auth snapshot 반영

scripts/
├── build_all.py
├── build_backend.py
├── sign_backend.py                        # [P0-05] Windows signtool / macOS codesign 래퍼
├── check_av_clean.py                      # [P0-05] VirusTotal 자동 스캔 (CI 선택)

.github/workflows/
├── build-release.yml                      # [P0-05] tag/dispatch 기반 서명 + 업로드 파이프라인

electron/
├── electron-builder.yml                   # [P0-05] CSC_LINK/notarize/draft publish 설정
├── resources/entitlements.mac.plist       # [P0-05] hardened runtime entitlements
```
