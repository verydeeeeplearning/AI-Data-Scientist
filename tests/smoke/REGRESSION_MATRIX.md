# Critical User Journey — 릴리스 회귀 매트릭스

**P0-06 산출물**. 베타/릴리스 빌드 직전에 이 매트릭스의 모든 항목이
green이거나 의도적으로 deferred 인지 확인한 뒤 publish 한다.

| # | 시나리오 | 자동화 경로 | 상태 |
|---|---------|-----------|------|
| 1 | Backend binary 부팅 (`READY:` 신호) | `tests/smoke/test_backend_binary.py::TestPackagingHealth` | ✅ |
| 2 | `/health` 200 OK | `tests/smoke/test_backend_binary.py::TestHealthSurface::test_health_endpoint_returns_ok` | ✅ |
| 3 | `/api/status` 스키마 (`model`/`mode`/`activeSessions`) | `tests/smoke/test_backend_binary.py::TestHealthSurface::test_status_endpoint_responds` | ✅ |
| 4 | `/api/config` 도달성 (auth 미설정 시 401 허용) | `tests/smoke/test_backend_binary.py::TestHealthSurface::test_config_endpoint_responds` | ✅ |
| 5 | stderr `ImportError` / `ModuleNotFoundError` / `DLL load failed` 부재 | 동 위 `test_no_module_import_errors_in_stderr` | ✅ |
| 6 | Clean install → Electron 앱 첫 실행 화면 | **TODO**: 패키지된 Electron 앱 필요. `tests/e2e/electron_first_run.spec.ts` (Playwright) — 아직 미구현 | ⏳ |
| 7 | Onboarding → Demo 모드 진입 | **TODO**: Phase 6 의 후속 (Playwright) | ⏳ |
| 8 | API key 입력 → provider 인증 성공 | **TODO**: 보안상 secret 입력은 packaged-app 환경에서만 검증 | ⏳ |
| 9 | CSV 업로드 → 첫 분석 응답 | **TODO**: WebSocket E2E (`tests/e2e/test_ws_e2e.py` 가 backend-only로 부분 커버) | 🟡 부분 |
| 10 | v1 config (`api_keys` 포함) → v2 마이그레이션 | `tests/integration/...` (P0-04 에서 검증, 패키지 회귀 검증은 ⏳) | 🟡 부분 |
| 11 | 앱 재시작 → 세션 복원 | **TODO** (Electron E2E) | ⏳ |
| 12 | Uninstall → 모든 바이너리 제거 | 수동 — Windows: `Get-Package`, macOS: `/Applications` 체크 | 수동 |
| 13 | AV/SmartScreen 환경 설치 | 수동 — P0-05 코드 서명 의존 | 수동 |

## 자동화 실행 방법

### 로컬
```bash
# 기존 dist/ 바이너리 사용
python scripts/run_smoke.py

# 깨끗하게 다시 빌드 후 실행
python scripts/run_smoke.py --build

# 다른 위치의 바이너리
PACKAGED_BINARY_PATH=/path/to/ds-agent-api python -m pytest tests/smoke -m smoke
```

### CI
`.github/workflows/smoke.yml` 가 PR/main push 마다 자동 실행. Windows runner 에서
PyInstaller 빌드 → smoke suite. 향후 macOS/Linux runner 추가 예정.

## 미구현 (Backlog)

- **Electron Playwright E2E** (#6, #7, #8, #11): packaged Electron 앱이 빌드된
  환경에서만 의미 있음. P0-05 (서명) 와 함께 다음 세션에서 추가.
- **macOS / Linux smoke**: 현재 워크플로우는 Windows runner 만. PyInstaller
  spec 이 cross-platform 가능하므로 매트릭스 확장 가능.
- **세션 복원 회귀** (#11): backend 만의 reload 시나리오는 별도 integration
  으로 가능. Electron 측 persistence 는 packaged 앱 필요.
- **Upgrade 회귀** (#10 의 packaged 부분): N-1 → N installer 페어가 준비된
  후 시나리오 추가.
