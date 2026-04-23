import { useEffect, useMemo, useState } from 'react';
import {
  buildPaletteCommands,
  type PaletteFileSource,
  type PaletteModelSource,
  type PaletteRunSource,
} from '../../application/command/buildPaletteCommands';
import { AreaSidebar } from './AreaSidebar';
import { StatusBar } from './StatusBar';
import { useHashNavigation } from '../../hooks/useHashNavigation';
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut';
import { MigrationBanner } from '../navigation/MigrationBanner';
import { MissionPage } from '../../pages/mission/MissionPage';
import { RunsPage } from '../../pages/runs/RunsPage';
import { ArtifactsPage } from '../../pages/artifacts/ArtifactsPage';
import { GovernancePage } from '../../pages/governance/GovernancePage';
import { MemoryPage } from '../../pages/memory/MemoryPage';
import { AdminPage } from '../../pages/admin/AdminPage';
import { CommandPalette } from '../palette/CommandPalette';
import type { UploadedFileResult } from '../../domain/workspace/uploadedFile';
import type { ModelGroup } from '../../hooks/useModels';
import { useI18n } from '../../stores/i18nStore';
import { useFilesStore } from '../../stores/filesStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import type { SimpleQualityPreset } from '../../utils/qualityPreset';
import type { RpcFn } from '../settings/types';

interface Props {
  onSend: (message: string) => void;
  onAbort: () => void;
  onRefreshFiles: () => void;
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  onChangeMode: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
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

  useKeyboardShortcut('ctrl+k', () => setCommandPaletteOpen(true));
  useKeyboardShortcut('meta+k', () => setCommandPaletteOpen(true));

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

          {selection.areaId === 'mission' && (
            <MissionPage onSend={onSend} onAbort={onAbort} disabled={disabled} />
          )}

          {selection.areaId === 'runs' && <RunsPage />}

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

          {selection.areaId === 'memory' && <MemoryPage />}

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
      <StatusBar />
      <CommandPalette
        open={commandPaletteOpen}
        commands={paletteCommands}
        onSend={onSend}
        onClose={() => setCommandPaletteOpen(false)}
      />
      <div className="sr-only" aria-live="polite">
        {currentPath}
      </div>
    </div>
  );
}
