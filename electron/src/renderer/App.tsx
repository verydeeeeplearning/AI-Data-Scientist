/**
 * Root component — orchestrates splash, onboarding, settings, chat, sidebar,
 * error handling, and keyboard shortcuts.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { DiagnosticPanel } from './components/diagnostic/DiagnosticPanel';
import { ErrorBoundary } from './components/layout/ErrorBoundary';
import { SplashScreen } from './components/layout/SplashScreen';
import { DisconnectOverlay } from './components/layout/DisconnectOverlay';
import { MainPanel } from './components/layout/MainPanel';
import { AreaMainPanel } from './components/layout/AreaMainPanel';
import { UpdateNotification } from './components/layout/UpdateNotification';
import { OnboardingWizard, type OnboardingResult } from './components/settings/OnboardingWizard';
import { SandboxApprovalModal } from './components/sandbox/SandboxApprovalModal';
import { SandboxViolationToast } from './components/sandbox/SandboxViolationToast';
import { SettingsPanel } from './components/settings/SettingsPanel';
import { GlobalDropOverlay } from './components/workspace/GlobalDropOverlay';
import { WsProvider } from './hooks/WsProvider';
import { useChat } from './hooks/useChat';
import { useDeepLinkListener } from './hooks/useDeepLinkListener';
import { useAgent } from './hooks/useAgent';
import { useModels } from './hooks/useModels';
import { usePolicy } from './hooks/usePolicy';
import { useProjects } from './hooks/useProjects';
import { useProviderAuth } from './hooks/useProviderAuth';
import { useRuntimeEvents } from './hooks/useRuntimeEvents';
import { useRuntime } from './hooks/useRuntime';
import { useUsageSummary } from './hooks/useUsageSummary';
import { useWorkflow } from './hooks/useWorkflow';
import { useConfigStore } from './stores/configStore';
import { useAgentStore } from './stores/agentStore';
import { useChatStore } from './stores/chatStore';
import type { UploadedFileResult } from './domain/workspace/uploadedFile';

function getBackendPort(): number {
  const params = new URLSearchParams(window.location.search);
  const port = params.get('port');
  return port ? parseInt(port, 10) : 18790;
}

function getScreen(): 'main' | 'diagnostic' {
  const params = new URLSearchParams(window.location.search);
  return params.get('screen') === 'diagnostic' ? 'diagnostic' : 'main';
}

function getStartupPayload(): Record<string, unknown> | null {
  const params = new URLSearchParams(window.location.search);
  const payload = params.get('startup');
  if (!payload) return null;

  try {
    const parsed = JSON.parse(payload);
    return typeof parsed === 'object' && parsed !== null ? parsed as Record<string, unknown> : null;
  } catch (error) {
    console.error('[app] failed to parse startup payload:', error);
    return null;
  }
}

function getWsToken(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get('token') ?? '';
}

function AppInner() {
  // WIRE-07: useChat and useAgent now share a single WebSocket via WsProvider
  const { sendMessage, abort, status, disconnectReason, on } = useChat();
  const { rpc, refreshFiles, changeModel, changeQualityPreset, changeMode, uploadFile } = useAgent();
  useDeepLinkListener();

  // Subscribe to DS workflow events (harness warnings, quality, experiments, budget)
  useWorkflow(on, rpc, status === 'connected');
  useRuntime(on, rpc, status === 'connected');
  useRuntimeEvents(on, rpc, status === 'connected');
  usePolicy(on, rpc, status === 'connected');
  useProviderAuth(on, rpc, status === 'connected');
  useUsageSummary(status === 'connected');
  useProjects(rpc, status === 'connected');
  const {
    showOnboarding,
    setShowOnboarding,
    showSettings,
    setShowSettings,
    setFirstRun,
    resetOnboarding,
    useIaV2,
  } = useConfigStore();
  const { mode, setMode, setModel, setQualityPreset } = useAgentStore();
  const { messages } = useChatStore();

  // Model catalog from backend
  const { grouped: modelGroups } = useModels(rpc, status === 'connected');

  // Track if we've ever connected (to distinguish splash from disconnect)
  const [hasConnected, setHasConnected] = useState(false);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (status === 'connected') setHasConnected(true);
  }, [status]);

  // Auto-focus chat input on connect
  useEffect(() => {
    if (status === 'connected' && !showOnboarding) {
      setTimeout(() => chatInputRef.current?.focus(), 100);
    }
  }, [status, showOnboarding]);

  // Onboarding complete — wizard already persists model + use_case via rpc('config.set');
  // here we sync the local UI store and dismiss the modal. The starter prompt is
  // handed off through configStore.pendingStarterPrompt and consumed by ChatInput.
  const handleOnboardingComplete = useCallback((result: OnboardingResult) => {
    setModel(result.model);
    setQualityPreset(result.qualityPreset);
    setFirstRun(false);
    setShowOnboarding(false);
  }, [setFirstRun, setModel, setQualityPreset, setShowOnboarding]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Ctrl+, → toggle settings
      if (!useIaV2 && e.ctrlKey && e.key === ',') {
        e.preventDefault();
        setShowSettings(!showSettings);
        return;
      }

      // Ctrl+M → cycle mode
      if (e.ctrlKey && e.key === 'm') {
        e.preventDefault();
        const modes: ('auto' | 'supervised' | 'step-by-step')[] = ['auto', 'supervised', 'step-by-step'];
        const idx = modes.indexOf(mode);
        const next = modes[(idx + 1) % modes.length];
        changeMode(next);
        setMode(next);
        return;
      }

      // Escape → close panels
      if (e.key === 'Escape') {
        if (showSettings) setShowSettings(false);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [showSettings, setShowSettings, mode, changeMode, setMode, useIaV2]);

  // Splash screen — only before first connection
  if (!hasConnected && status !== 'connected') {
    return <SplashScreen status={status} />;
  }

  // Onboarding — first run
  if (showOnboarding) {
    return <OnboardingWizard onComplete={handleOnboardingComplete} rpc={rpc} groups={modelGroups} />;
  }

  return (
    <>
      {useIaV2 ? (
        <AreaMainPanel
          onSend={sendMessage}
          onAbort={abort}
          onRefreshFiles={refreshFiles}
          onChangeModel={changeModel}
          onChangeQualityPreset={changeQualityPreset}
          onChangeMode={changeMode}
          onUploadFile={uploadFile as (file: File) => Promise<UploadedFileResult>}
          onRestartOnboarding={resetOnboarding}
          disabled={status !== 'connected'}
          modelGroups={modelGroups}
          rpc={rpc}
        />
      ) : (
        <MainPanel
          onSend={sendMessage}
          onAbort={abort}
          onRefreshFiles={refreshFiles}
          onChangeModel={changeModel}
          onChangeQualityPreset={changeQualityPreset}
          onChangeMode={changeMode}
          onUploadFile={uploadFile as (file: File) => Promise<UploadedFileResult>}
          onOpenSettings={() => setShowSettings(true)}
          disabled={status !== 'connected'}
          modelGroups={modelGroups}
        />
      )}

      {/* Disconnect overlay — only after initial connection, when messages exist */}
      {hasConnected && status !== 'connected' && messages.length > 0 && (
        <DisconnectOverlay status={status} reason={disconnectReason} />
      )}

      {showSettings && (
        <SettingsPanel
          onClose={() => setShowSettings(false)}
          onChangeModel={changeModel}
          onChangeQualityPreset={changeQualityPreset}
          onChangeMode={changeMode}
          onRestartOnboarding={resetOnboarding}
          rpc={rpc}
        />
      )}

      {/* Auto-update banner (P1-14) — no-op in dev builds */}
      <UpdateNotification />

      {/* P0-01 Phase 3: sandbox approval modal + violation toast stack */}
      <SandboxApprovalModal />
      <SandboxViolationToast />

      <GlobalDropOverlay onUploadFile={uploadFile as (file: File) => Promise<UploadedFileResult>} />
    </>
  );
}

export default function App() {
  const screen = getScreen();
  const startupPayload = getStartupPayload();

  if (screen === 'diagnostic') {
    return (
      <ErrorBoundary>
        <DiagnosticPanel payload={startupPayload} />
      </ErrorBoundary>
    );
  }

  const port = getBackendPort();
  const token = getWsToken();
  return (
    <ErrorBoundary>
      <WsProvider port={port} token={token}>
        <AppInner />
      </WsProvider>
    </ErrorBoundary>
  );
}
