/**
 * Root component — orchestrates splash, onboarding, settings, chat, sidebar,
 * error handling, and keyboard shortcuts.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { DiagnosticPanel } from './components/diagnostic/DiagnosticPanel';
import { ErrorBoundary } from './components/layout/ErrorBoundary';
import { SplashScreen } from './components/layout/SplashScreen';
import { DisconnectOverlay } from './components/layout/DisconnectOverlay';
import { AreaMainPanel } from './components/layout/AreaMainPanel';
import { AppToastStack } from './components/layout/AppToastStack';
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
import { useTelegramRuntime } from './hooks/useTelegramRuntime';
import { useRuntime } from './hooks/useRuntime';
import { useUsageSummary } from './hooks/useUsageSummary';
import { useWorkflow } from './hooks/useWorkflow';
import {
  syncConfigStoreFromStorageEvent,
  useConfigStore,
} from './stores/configStore';
import { useAgentStore } from './stores/agentStore';
import { useChatStore } from './stores/chatStore';
import type { UploadedFileResult } from './domain/workspace/uploadedFile';
import { getBackendPort, getBackendQueryParam } from './utils/backendUrl';

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
  return getBackendQueryParam('token') ?? '';
}

function AppInner() {
  // WIRE-07: useChat and useAgent now share a single WebSocket via WsProvider
  const { sendMessage, abort, status, disconnectReason, on } = useChat();
  const { rpc, refreshFiles, changeModel, changeQualityPreset, changeMode, changeMaxBudget, uploadFile } = useAgent();
  useDeepLinkListener();

  useEffect(() => {
    window.addEventListener('storage', syncConfigStoreFromStorageEvent);
    return () => window.removeEventListener('storage', syncConfigStoreFromStorageEvent);
  }, []);

  // Subscribe to DS workflow events (harness warnings, quality, experiments, budget)
  useWorkflow(on, rpc, status === 'connected');
  useRuntime(on, rpc, status === 'connected');
  useRuntimeEvents(on, rpc, status === 'connected');
  useTelegramRuntime(on, rpc, status === 'connected');
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

  // Onboarding complete — wizard issues config.set, but those calls have been
  // observed to silently fail (provider.default_model = None in backend even
  // after a successful wizard run). We re-issue the model/preset sync via
  // useAgent.changeModel/changeQualityPreset, which (a) writes config.set,
  // (b) round-trips through status.get to refresh the renderer store, and
  // (c) aborts any in-flight chat — guaranteeing header + backend agree.
  const handleOnboardingComplete = useCallback(
    async (result: OnboardingResult) => {
      try {
        await changeModel(result.model);
        if (result.qualityPreset !== 'custom') {
          await changeQualityPreset(result.qualityPreset);
        } else {
          setQualityPreset(result.qualityPreset);
        }
      } catch (err) {
        console.error('[app] failed to sync model/preset after onboarding:', err);
        setModel(result.model);
        setQualityPreset(result.qualityPreset);
      }
      setFirstRun(false);
      setShowOnboarding(false);
    },
    [
      changeModel,
      changeQualityPreset,
      setFirstRun,
      setModel,
      setQualityPreset,
      setShowOnboarding,
    ],
  );

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
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
  }, [showSettings, setShowSettings, mode, changeMode, setMode]);

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
      <AreaMainPanel
        onSend={sendMessage}
        onAbort={abort}
        onRefreshFiles={refreshFiles}
        onChangeModel={changeModel}
        onChangeQualityPreset={changeQualityPreset}
        onChangeMode={changeMode}
        onChangeMaxBudget={changeMaxBudget}
        onUploadFile={uploadFile as (file: File) => Promise<UploadedFileResult>}
        onRestartOnboarding={resetOnboarding}
        disabled={status !== 'connected'}
        modelGroups={modelGroups}
        rpc={rpc}
      />

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
      <AppToastStack />

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
