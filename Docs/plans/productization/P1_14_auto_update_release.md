# P1-14: 자동 업데이트 & 릴리스 관리

**우선순위**: P1 (P0-05 코드 서명 이후 구현)
**요구사항 섹션**: 5.10
**상태**: In Progress (런타임 + UI 완료, 서명 인증서 조달 대기)
**의존성**: P0-05 (코드 서명 필수), P0-04 (migration framework)

---

## 2026-04-15 진행 상황

| 항목 | 상태 | 구현 위치 |
|------|------|-----------|
| electron-updater 런타임 통합 | ✅ | `electron/src/main/auto-updater.ts` |
| 시작 후 5분 / 이후 4시간 주기 체크 | ✅ | `scheduleRecurring()` |
| 실패 시 24시간 후 재시도 | ✅ | `scheduleRetry()` |
| 채널 분기 (stable/beta/internal) | ✅ | `DS_AGENT_UPDATE_CHANNEL` 환경변수 |
| Update 알림 배너 UI | ✅ | `electron/src/renderer/components/layout/UpdateNotification.tsx` |
| IPC bridge (check/download/install) | ✅ | `main/auto-updater.ts`, `preload/index.ts` |
| electron-log 연동 | ✅ | `log.transports.file` |
| 한국어/영어 번역 | ✅ | `i18nStore` update.* 키 |
| 실제 서명된 installer 배포 → 업데이트 흐름 검증 | ⏳ | P0-05 인증서 조달 후 |
| Release notes 인앱 표시 | ⏳ | `ReleaseNotesPanel` 미구현 (fallback: GitHub Releases URL 열기) |

---

## 주요 설계 포인트

- `app.isPackaged === false` 일 때 updater 는 no-op. Dev 빌드는 배너를 보지 못함.
- `autoDownload = false` — 사용자가 "다운로드" 를 누르기 전까지는 네트워크 트래픽 없음.
- 에러는 로그/배너로 알리고 현재 버전은 계속 정상 동작 (fallback 안전장치).
- `DS_AGENT_UPDATE_CHANNEL=beta` 로 빌드하면 beta 채널만 조회.
- 다수 창이 열려 있어도 `BrowserWindow.getAllWindows()` 로 모두 브로드캐스트.

---

## 현재 상태

`electron/electron-builder.yml`에 publish 설정 존재하나
**실제 auto updater 런타임 통합 미확인**.

---

## 구현 Phase 계획

### Phase 1: electron-updater 런타임 통합

**수정 파일**: `electron/src/main/index.ts`

```typescript
import { autoUpdater } from 'electron-updater';

function setupAutoUpdater() {
  // 로그 설정
  autoUpdater.logger = require('electron-log');
  (autoUpdater.logger as any).transports.file.level = 'info';

  // 업데이트 확인 (앱 시작 후 5분, 이후 매 4시간)
  setTimeout(() => autoUpdater.checkForUpdates(), 5 * 60 * 1000);
  setInterval(() => autoUpdater.checkForUpdates(), 4 * 60 * 60 * 1000);

  // 이벤트 핸들러
  autoUpdater.on('update-available', (info) => {
    mainWindow.webContents.send('updater:update-available', {
      version: info.version,
      releaseDate: info.releaseDate,
      releaseNotes: info.releaseNotes,
    });
  });

  autoUpdater.on('download-progress', (progress) => {
    mainWindow.webContents.send('updater:download-progress', {
      percent: Math.round(progress.percent),
      bytesPerSecond: progress.bytesPerSecond,
    });
  });

  autoUpdater.on('update-downloaded', (info) => {
    mainWindow.webContents.send('updater:update-ready', {
      version: info.version,
    });
  });

  autoUpdater.on('error', (err) => {
    mainWindow.webContents.send('updater:error', { message: err.message });
  });
}

// IPC: 사용자가 "지금 설치" 클릭 시
ipcMain.handle('updater:install', () => {
  autoUpdater.quitAndInstall(false, true);  // 재시작 후 설치
});
```

---

### Phase 2: Update 알림 UI

**새 파일**: `electron/src/renderer/components/layout/UpdateNotification.tsx`

```tsx
export function UpdateNotification() {
  const [updateState, setUpdateState] = useState<UpdateState>({ status: 'idle' });

  useEffect(() => {
    window.dsAgent.on('updater:update-available', (info) => {
      setUpdateState({ status: 'available', info });
    });
    window.dsAgent.on('updater:download-progress', ({ percent }) => {
      setUpdateState(s => ({ ...s, status: 'downloading', percent }));
    });
    window.dsAgent.on('updater:update-ready', (info) => {
      setUpdateState({ status: 'ready', info });
    });
  }, []);

  if (updateState.status === 'idle') return null;

  return (
    <div className="update-notification" role="status">
      {updateState.status === 'available' && (
        <>
          <span>새 버전 {updateState.info.version}이 있습니다</span>
          <Button size="sm" onClick={startDownload}>다운로드</Button>
          <Button size="sm" variant="ghost" onClick={dismiss}>나중에</Button>
        </>
      )}

      {updateState.status === 'downloading' && (
        <>
          <span>업데이트 다운로드 중... {updateState.percent}%</span>
          <ProgressBar value={updateState.percent} />
        </>
      )}

      {updateState.status === 'ready' && (
        <>
          <span>업데이트 준비 완료. 지금 설치하시겠습니까?</span>
          <Button size="sm" onClick={installUpdate}>지금 재시작</Button>
          <Button size="sm" variant="ghost" onClick={defer}>다음 시작 시</Button>
        </>
      )}
    </div>
  );
}
```

---

### Phase 3: Release Channel 분기

**수정 파일**: `electron/electron-builder.yml`

```yaml
publish:
  provider: github
  owner: <org>
  repo: ds-agent

# 채널별 업데이트 서버
win:
  publisherName: "DS Agent Inc."

# stable 채널: latest.yml
# beta 채널: beta.yml (--channel beta 빌드 시)
# internal 채널: alpha.yml
```

**수정 파일**: `src/ds_agent/config/schema.py`

```python
class AppConfig(BaseModel):
    update_channel: Literal["stable", "beta", "internal"] = "stable"
    auto_update: bool = True
    update_check_interval_hours: int = 4
```

**채널 설정 UI**:

```tsx
// 설정 → 업데이트
<Select
  label="업데이트 채널"
  options={[
    { value: 'stable', label: '안정 버전 (권장)' },
    { value: 'beta', label: '베타 버전 (새 기능 먼저 체험)' },
  ]}
/>
```

---

### Phase 4: Release Notes 내장

**새 파일**: `electron/src/renderer/components/settings/ReleaseNotesPanel.tsx`

```tsx
export function ReleaseNotesPanel() {
  const { data: releases } = useQuery('releases', fetchReleaseNotes);

  return (
    <div>
      <h3>업데이트 내역</h3>
      {releases?.map(release => (
        <div key={release.version} className="release-entry">
          <div className="release-header">
            <span className="version">{release.version}</span>
            <span className="date">{formatDate(release.date)}</span>
            {release.isCurrent && <Badge>현재 버전</Badge>}
          </div>
          <div
            className="release-notes"
            dangerouslySetInnerHTML={{ __html: sanitize(release.notes) }}
          />
        </div>
      ))}
    </div>
  );
}

async function fetchReleaseNotes() {
  // GitHub Releases API 또는 번들된 CHANGELOG
  const resp = await fetch('https://api.github.com/repos/org/ds-agent/releases?per_page=10');
  return resp.json();
}
```

---

### Phase 5: Update 실패 안전장치

```typescript
autoUpdater.on('error', (err) => {
  // 업데이트 실패해도 기존 버전 정상 동작
  logger.error('Auto update failed', err);
  mainWindow.webContents.send('updater:error', {
    message: '업데이트 다운로드 중 문제가 발생했습니다. 현재 버전은 정상 동작합니다.',
  });
  // 실패 후 24시간 뒤 재시도
  setTimeout(() => autoUpdater.checkForUpdates(), 24 * 60 * 60 * 1000);
});
```

---

## Quality Gate

- [ ] 앱 시작 후 자동으로 업데이트 확인
- [ ] "업데이트 있음" 알림 → 다운로드 → "지금 재시작" 흐름 E2E 테스트
- [ ] 업데이트 실패 시 기존 버전 정상 동작 확인
- [ ] stable / beta 채널 분기 동작 확인
- [ ] Release notes 앱 내에서 표시 확인
- [ ] 업데이트 후 사용자 데이터 보존 확인 (P0-04 migration 연동)
