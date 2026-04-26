import { Suspense, lazy, useEffect, useMemo, useState } from 'react';
import {
  buildPaletteCommands,
  type PaletteFileSource,
  type PaletteModelSource,
  type PaletteRunSource,
} from '../../application/command/buildPaletteCommands';
import { AreaSidebar } from './AreaSidebar';
import { MissionContextBar } from './MissionContextBar';
import { SessionDrawer } from './SessionDrawer';
import { StatusBar } from './StatusBar';
import { FloatingChat } from '../chat/FloatingChat';
import { useHashNavigation } from '../../hooks/useHashNavigation';
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut';
import { MigrationBanner } from '../navigation/MigrationBanner';
import { RunsPage } from '../../pages/runs/RunsPage';
import { ArtifactsPage } from '../../pages/artifacts/ArtifactsPage';
import { GovernancePage } from '../../pages/governance/GovernancePage';
import { AdminPage } from '../../pages/admin/AdminPage';
import { CommandPalette } from '../palette/CommandPalette';
import type { UploadedFileResult } from '../../domain/workspace/uploadedFile';
import type { ModelGroup } from '../../hooks/useModels';
import { useChatStore } from '../../stores/chatStore';
import { useI18n } from '../../stores/i18nStore';
import { useFilesStore } from '../../stores/filesStore';
import { useMissionContext } from '../../hooks/useMissionContext';
import { useRuntimeStore } from '../../stores/runtimeStore';
import type { SimpleQualityPreset } from '../../utils/qualityPreset';
import type { RpcFn } from '../settings/types';

const GoalDrawer = lazy(() =>
  import('../mission/GoalDrawer').then((m) => ({ default: m.GoalDrawer })),
);

interface Props {
  onSend: (message: string) => void;
  onAbort: () => void;
  onRefreshFiles: () => void;
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  onChangeMode: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
  onChangeMaxBudget: (value: number, previousValue?: number) => void | Promise<void>;
  onUploadFile: (file: File) => Promise<UploadedFileResult>;
  onRestartOnboarding: () => void;
  disabled?: boolean;
  modelGroups: ModelGroup[];
  rpc: RpcFn;
}

export function AreaMainPanel({
  onSend,
  onAbort,
  onRefreshFiles,
  onChangeModel,
  onChangeQualityPreset,
  onChangeMode,
  onChangeMaxBudget,
  onUploadFile,
  onRestartOnboarding,
  disabled,
  modelGroups,
  rpc,
}: Props) {
  const t = useI18n((state) => state.t);
  const files = useFilesStore((state) => state.files);
  const runs = useRuntimeStore((state) => state.runs);
  const selectRun = useRuntimeStore((state) => state.selectRun);
  const { currentPath, selection, migrationNotice, navigate, dismissMigrationNotice } =
    useHashNavigation();
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [sessionDrawerOpen, setSessionDrawerOpen] = useState(false);
  const [goalDrawerOpen, setGoalDrawerOpen] = useState(false);
  const sessionId = useChatStore((state) => state.sessionId);
  const { mission } = useMissionContext(sessionId);

  useKeyboardShortcut('ctrl+k', () => setCommandPaletteOpen(true));
  useKeyboardShortcut('meta+k', () => setCommandPaletteOpen(true));
  useKeyboardShortcut('ctrl+;', () => {
    setSessionDrawerOpen((value) => !value);
  });
  useKeyboardShortcut('meta+;', () => {
    setSessionDrawerOpen((value) => !value);
  });

  useEffect(() => {
    const handleOpenCommandPalette = () => {
      setCommandPaletteOpen(true);
    };

    window.addEventListener(
      'ds-agent:open-command-palette',
      handleOpenCommandPalette as EventListener,
    );
    return () => {
      window.removeEventListener(
        'ds-agent:open-command-palette',
        handleOpenCommandPalette as EventListener,
      );
    };
  }, []);

  // v3 redirect: 'mission' and 'memory' areas are folded into the
  // MissionContextBar (top strip) and Admin > Memory respectively.
  // Anyone landing on those areas — fresh nav, deep link, persisted state —
  // gets bounced to their v3 home on the next tick.
  useEffect(() => {
    if (selection.areaId === 'mission') {
      navigate('/artifacts/files');
    } else if (selection.areaId === 'memory') {
      navigate('/admin/memory');
    }
  }, [navigate, selection.areaId]);

  const paletteRuns = useMemo<PaletteRunSource[]>(
    () =>
      runs.map((run) => ({
        runId: run.runId,
        status: run.status,
        surface: run.surface,
        sessionLabel: run.sessionLabel,
        resultPreview: run.resultPreview,
        createdAt: run.createdAt,
      })),
    [runs],
  );

  const paletteFiles = useMemo<PaletteFileSource[]>(
    () =>
      files.map((file) => ({
        name: file.name,
        path: file.path,
        size: file.size,
        type: file.type,
        modifiedAt: file.modifiedAt,
      })),
    [files],
  );

  const paletteModels = useMemo<PaletteModelSource[]>(
    () =>
      modelGroups.flatMap((group) =>
        group.models.map((model) => ({
          id: model.id,
          displayName: model.displayName,
          provider: model.provider,
          groupLabel: t(group.titleKey),
          badges: model.badges,
          recommendedFor: model.recommendedFor,
        })),
      ),
    [modelGroups, t],
  );

  const paletteCommands = useMemo(
    () =>
      buildPaletteCommands({
        t,
        navigate,
        files: paletteFiles,
        runs: paletteRuns,
        selectRun,
        models: paletteModels,
        onChangeModel,
        onSend,
        rpc,
      }),
    [navigate, onChangeModel, onSend, paletteFiles, paletteModels, paletteRuns, rpc, selectRun, t],
  );

  return (
    <div className="flex h-screen flex-col bg-ds-bg text-ds-text">
      <MissionContextBar
        connected={!disabled}
        onOpenGoal={() => setGoalDrawerOpen(true)}
        onOpenStage={() => navigate('/runs')}
        onOpenSession={() => setSessionDrawerOpen(true)}
      />

      <div className="flex flex-1 overflow-hidden">
        <AreaSidebar selection={selection} onNavigate={navigate} />
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {migrationNotice && (
            <div className="border-b border-ds-border px-4 py-3">
              <MigrationBanner
                fromPath={migrationNotice.fromPath}
                toPath={migrationNotice.toPath}
                onDismiss={dismissMigrationNotice}
              />
            </div>
          )}

          {selection.areaId === 'runs' && <RunsPage onNavigate={navigate} />}

          {selection.areaId === 'artifacts' && (
            <ArtifactsPage
              selection={selection}
              onNavigate={navigate}
              onRefreshFiles={onRefreshFiles}
              onUploadFile={onUploadFile}
            />
          )}

          {selection.areaId === 'governance' && (
            <GovernancePage selection={selection} onNavigate={navigate} />
          )}

          {selection.areaId === 'admin' && (
            <AdminPage
              selection={selection}
              onNavigate={navigate}
              onChangeModel={onChangeModel}
              onChangeQualityPreset={onChangeQualityPreset}
              onChangeMode={onChangeMode}
              onRestartOnboarding={onRestartOnboarding}
              rpc={rpc}
              modelGroups={modelGroups}
            />
          )}
        </div>
      </div>
      <StatusBar onNavigate={navigate} />
      <CommandPalette
        open={commandPaletteOpen}
        commands={paletteCommands}
        onSend={onSend}
        onClose={() => setCommandPaletteOpen(false)}
      />

      <FloatingChat
        onSend={onSend}
        onAbort={onAbort}
        disabled={disabled}
      />
      <SessionDrawer
        open={sessionDrawerOpen}
        onClose={() => setSessionDrawerOpen(false)}
        onChangeMode={onChangeMode}
        onChangeModel={onChangeModel}
        onChangeQualityPreset={onChangeQualityPreset}
        onChangeMaxBudget={onChangeMaxBudget}
        onOpenAdmin={() => {
          setSessionDrawerOpen(false);
          navigate('/admin/settings');
        }}
        modelGroups={modelGroups}
      />
      {mission && (
        <Suspense fallback={null}>
          <GoalDrawer
            open={goalDrawerOpen}
            mission={mission}
            onClose={() => setGoalDrawerOpen(false)}
          />
        </Suspense>
      )}

      <div className="sr-only" aria-live="polite">
        {currentPath}
      </div>
    </div>
  );
}
