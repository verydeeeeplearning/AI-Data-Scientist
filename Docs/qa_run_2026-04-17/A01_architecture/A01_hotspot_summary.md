# A01 Hotspot Summary

## `src/ds_agent/api/ws_handler.py`

- 4,034 lines
- `WsRpcHandler` 1개 클래스가 transport validation, error presentation, 80개 RPC method routing, request handler 구현을 함께 보유한다.
- 같은 파일의 `AppState`가 config/session/runtime/policy/provider/auth/connector 관련 composition 역할과 facade 역할을 동시에 맡고 있다.
- 파일 내부에 `Public entry point`, `RPC Method Handlers`, `Portfolio Manager RPC`, `Learning Governance RPC`, `Method routing table`, `Internal helpers`, `Public facade` 섹션 주석은 있으나, 실제 책임은 여전히 단일 파일에 고밀도로 집중돼 있다.

## `electron/src/main/ipc.ts`

- 1,377 lines
- `registerMainIpcHandlers()` 안에 `ipcMain.handle(...)` 33개와 `ipcMain.on(...)` 3개가 모여 있다.
- 다루는 책임이 창 제어, 파일/대화상자, 시크릿 저장소, observability, support bundle, 샘플 로딩, 인증/인증서, task contract CRUD, delivery pack render/dispatch까지 넓게 퍼져 있다.
- 파일 후반부에는 preview, filename sanitize, staged export cleanup, hidden PDF render, backend HTTP bridge 같은 보조 유틸리티도 같이 들어 있다.

## `electron/src/renderer/components/mission/MissionBriefPanel.tsx`

- 798 lines
- helper 3개 + 단일 React component 1개 구조다.
- 컴포넌트 내부에 `useState` 11개, `useMemo` 3개, `useEffect` 2개, action handler 8개가 들어 있다.
- task contract 상태 전이, assumption verification, delivery pack build, artifact render, dispatch, path reveal, editor/drawer/dialog UI까지 한 컴포넌트가 모두 담당한다.
- 렌더링 구조는 읽을 수 있지만, workflow state machine과 delivery UI가 분리되지 않아 변경 영향 범위가 넓다.
