# P0-05: 코드 서명 및 배포 파이프라인

**우선순위**: P0 — 베타 배포 차단 조건
**요구사항 섹션**: 5.1
**상태**: In Progress (파이프라인 인프라 완료, 인증서 조달 대기)
**의존성**: 없음

---

## 2026-04-15 진행 상황

| 항목 | 상태 | 구현 위치 |
|------|------|-----------|
| PyInstaller AV 하드닝 (UPX off) | ✅ | `ds-agent-api.spec` |
| Windows / macOS 서명 래퍼 스크립트 | ✅ | `scripts/sign_backend.py` |
| VirusTotal 자동 스캔 스크립트 | ✅ | `scripts/check_av_clean.py` |
| electron-builder 서명/notarize 설정 | ✅ | `electron/electron-builder.yml` |
| macOS hardened runtime entitlements | ✅ | `electron/resources/entitlements.mac.plist` |
| GitHub Actions 서명 파이프라인 | ✅ | `.github/workflows/build-release.yml` |
| EV 인증서 조달 (Windows) | ⏳ 대기 | GitHub secrets `WINDOWS_CERT_PFX_B64` |
| Apple Developer ID 조달 (macOS) | ⏳ 대기 | GitHub secrets `MACOS_CERT_P12_B64` 외 |
| SmartScreen / Gatekeeper 실제 검증 | ⏳ 대기 | 인증서 적용 후 fresh VM 테스트 |

인증서 secret 이 없을 때 CI 는 조용히 서명 스텝을 건너뛰고 미서명 installer 를
업로드하므로 파이프라인 자체는 포크 / 테스트 빌드에서도 검증 가능하다.

---

## 개요

현재 `scripts/build_all.py`로 빌드는 가능하지만 **코드 서명이 없다**.
미서명 installer는 다음 문제를 야기:

- Windows SmartScreen: "이 앱을 실행할 수 없습니다" 차단 경고
- macOS Gatekeeper: "확인할 수 없는 개발자" 경고
- 기업 환경: 관리자 정책으로 미서명 앱 실행 자동 차단
- 주요 AV 솔루션(Defender, AhnLab 등) false positive 검출

---

## 서명 전략

### Windows

| 항목 | 내용 |
|------|------|
| 인증서 | EV Code Signing Certificate (DigiCert / Sectigo) |
| 도구 | `signtool.exe` (Windows SDK) |
| 대상 | `ds-agent-api.exe` (PyInstaller), `ds-agent-setup.exe` (NSIS installer) |
| SmartScreen | EV 인증서 사용 시 SmartScreen 즉시 통과 |
| 비용 | EV 인증서 ~$200-400/년, 물리 USB 토큰 또는 HSM |

### macOS

| 항목 | 내용 |
|------|------|
| 인증서 | Apple Developer ID Application |
| 도구 | `codesign`, `xcrun notarytool` |
| 대상 | 앱 번들 전체 + embedded dylib |
| Notarization | Apple 서버에 업로드 → 승인 → staple |
| 비용 | Apple Developer 계정 $99/년 |

### Linux

서명 없음. AppImage / .deb / .rpm 배포.
SHA256 체크섬 파일을 릴리스와 함께 제공.

---

## 구현 Phase 계획

### Phase 1: CI/CD 서명 파이프라인 (GitHub Actions)

**새 파일**: `.github/workflows/build-release.yml`

```yaml
name: Build & Sign Release

on:
  push:
    tags: ['v*']
  workflow_dispatch:
    inputs:
      channel:
        type: choice
        options: [stable, beta, internal]

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }

      - name: Setup Node
        uses: actions/setup-node@v4
        with: { node-version: '20' }

      - name: Build Python backend
        run: python scripts/build_backend.py

      - name: Sign backend binary
        env:
          CERT_PFX_B64: ${{ secrets.WINDOWS_CERT_PFX_B64 }}
          CERT_PASSWORD: ${{ secrets.WINDOWS_CERT_PASSWORD }}
        run: |
          echo "$CERT_PFX_B64" | base64 -d > cert.pfx
          signtool sign /f cert.pfx /p "$CERT_PASSWORD" \
            /tr http://timestamp.digicert.com /td sha256 /fd sha256 \
            dist/ds-agent-api.exe

      - name: Build Electron installer
        env:
          CSC_LINK: ${{ secrets.WINDOWS_CERT_PFX_B64 }}
          CSC_KEY_PASSWORD: ${{ secrets.WINDOWS_CERT_PASSWORD }}
        run: |
          cd electron
          npm run build:win

      # electron-builder가 자동으로 installer 서명
      - name: Verify signature
        run: signtool verify /pa dist/ds-agent-setup.exe

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: windows-installer
          path: electron/dist/*.exe

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Import Apple certificate
        env:
          CERT_P12_B64: ${{ secrets.MACOS_CERT_P12_B64 }}
          CERT_PASSWORD: ${{ secrets.MACOS_CERT_PASSWORD }}
          KEYCHAIN_PASSWORD: ${{ secrets.MACOS_KEYCHAIN_PASSWORD }}
        run: |
          echo "$CERT_P12_B64" | base64 -d > cert.p12
          security create-keychain -p "$KEYCHAIN_PASSWORD" build.keychain
          security import cert.p12 -k build.keychain -P "$CERT_PASSWORD" -A
          security set-key-partition-list -S apple-tool:,apple: -s -k "$KEYCHAIN_PASSWORD" build.keychain
          security list-keychains -d user -s build.keychain

      - name: Build backend + Electron
        run: python scripts/build_all.py

      - name: Notarize
        env:
          APPLE_ID: ${{ secrets.APPLE_ID }}
          APPLE_APP_PASSWORD: ${{ secrets.APPLE_APP_PASSWORD }}
          APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
        run: |
          xcrun notarytool submit electron/dist/DS\ Agent.dmg \
            --apple-id "$APPLE_ID" \
            --password "$APPLE_APP_PASSWORD" \
            --team-id "$APPLE_TEAM_ID" \
            --wait
          xcrun stapler staple electron/dist/DS\ Agent.dmg

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: macos-dmg
          path: electron/dist/*.dmg
```

---

### Phase 2: electron-builder.yml 서명 설정

**수정 파일**: `electron/electron-builder.yml`

```yaml
appId: app.ds-agent.desktop
productName: DS Agent

win:
  target:
    - target: nsis
      arch: [x64]
  signingHashAlgorithms: [sha256]
  # CI에서 CSC_LINK, CSC_KEY_PASSWORD 환경변수로 서명
  # 로컬 개발에서는 서명 생략 (sign: false)
  sign: ${env.CI}

nsis:
  oneClick: false
  allowToChangeInstallationDirectory: true
  perMachine: false       # 관리자 권한 불필요 (per-user 설치)
  createDesktopShortcut: true
  createStartMenuShortcut: true
  shortcutName: DS Agent

mac:
  target:
    - target: dmg
      arch: [x64, arm64]  # Intel + Apple Silicon
  category: public.app-category.productivity
  notarize: true          # CI에서 자동 notarize

publish:
  provider: github
  owner: <org>
  repo: ds-agent
  releaseType: draft      # 수동으로 릴리스 확정

# Release 채널 구분
channels:
  stable:
    releaseType: release
  beta:
    releaseType: prerelease
  internal:
    releaseType: draft
```

---

### Phase 3: AV False Positive 대응

**체크리스트**:

1. **VirusTotal 제출**: 릴리스 전 `dist/ds-agent-api.exe` VirusTotal 제출
   - 70개 AV 엔진 스캔 결과 확인
   - false positive 있는 벤더에 개별 제출 (False Positive Submission)

2. **주요 AV 벤더 화이트리스트 제출**:
   - Microsoft MSRC (Windows Defender)
   - AhnLab (한국 시장 필수)
   - Kaspersky False Positive 신고
   - McAfee/Trellix 제출

3. **PyInstaller 대안 고려**:
   - PyInstaller 생성 바이너리는 AV false positive 빈도 높음
   - Nuitka (C 컴파일) 또는 cx_Freeze 대안 검토
   - 패킹 도구(UPX) 사용 금지 (AV 의심 증가)

4. **build_backend.py 수정**:
   ```python
   # UPX 비활성화 (false positive 방지)
   PyInstaller(['...', '--noupx', ...])
   ```

**새 파일**: `scripts/check_av_clean.py`

```python
"""
VirusTotal API로 빌드된 바이너리 자동 스캔.
VIRUSTOTAL_API_KEY 환경변수 필요.
탐지 수 > 0이면 경고 출력.
"""
```

---

### Phase 4: 설치 프로그램 QA

**수동 테스트 체크리스트**:

- [ ] Windows 11 fresh VM에서 installer 실행 → SmartScreen 경고 없음
- [ ] Windows 10 (1903 이상) 호환 확인
- [ ] per-user 설치 (관리자 권한 없이)
- [ ] 기존 버전 위 upgrade 설치 → 설정/데이터 보존
- [ ] uninstall 완료 → 바이너리 제거, 사용자 데이터는 선택적 보존
- [ ] macOS 13+ Gatekeeper 통과 확인
- [ ] Apple Silicon (arm64) 정상 동작 확인

---

## Required Secrets (GitHub Repository Secrets)

```
WINDOWS_CERT_PFX_B64      # EV 인증서 PFX base64
WINDOWS_CERT_PASSWORD      # PFX 암호
MACOS_CERT_P12_B64        # Apple Developer ID P12 base64
MACOS_CERT_PASSWORD        # P12 암호
MACOS_KEYCHAIN_PASSWORD    # CI keychain 임시 암호
APPLE_ID                   # Apple Developer 계정 이메일
APPLE_APP_PASSWORD         # App-specific password
APPLE_TEAM_ID              # Team ID
VIRUSTOTAL_API_KEY         # AV 스캔용 (선택)
```

---

## Quality Gate

- [ ] Windows 미서명 경고 없이 설치 완료 (SmartScreen 통과)
- [ ] macOS Gatekeeper 통과, notarization staple 확인
- [ ] VirusTotal 스캔 탐지 0개 (또는 알려진 false positive만)
- [ ] CI에서 자동 서명 → 릴리스 draft 생성 확인
- [ ] per-user 설치 (관리자 권한 없이) 확인
- [ ] upgrade 설치 시 사용자 데이터 보존 확인
