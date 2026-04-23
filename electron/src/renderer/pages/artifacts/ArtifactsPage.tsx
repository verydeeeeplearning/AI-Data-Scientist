import { useMemo, useState } from 'react';
import { ExperimentTable } from '../../components/workflow/ExperimentTable';
import { MetricSourcePanel } from '../../components/semantic/MetricSourcePanel';
import { FileExplorer } from '../../components/sidebar/FileExplorer';
import { FileUpload } from '../../components/sidebar/FileUpload';
import { PlotGallery } from '../../components/sidebar/PlotGallery';
import { ProjectPanel } from '../../components/sidebar/ProjectPanel';
import { ProjectControlTower } from '../../components/portfolio/ProjectControlTower';
import { EvidenceWorkspace } from '../../components/workspace/EvidenceWorkspace';
import {
  buildEvidenceWorkspacePath,
  normalizeArtifactsView,
  parseEvidenceWorkspaceRoute,
  type ArtifactView,
} from '../../application/workspace/workspaceRoute';
import type { AreaSelection } from '../../domain/navigation/area';
import type { UploadedFileResult } from '../../domain/workspace/uploadedFile';
import { exportWorkspaceFile } from '../../infrastructure/api/exportApi';
import { useWorkspaceExportArtifacts } from '../../hooks/useWorkspaceExportArtifacts';
import { useChatStore } from '../../stores/chatStore';
import { useI18n } from '../../stores/i18nStore';
import { useReasoningTraceStore } from '../../stores/reasoningTraceStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import {
  useWorkspaceStore,
  type WorkspacePinnedProjectionItem,
} from '../../stores/workspaceStore';
import { resolveWorkspaceExportRunId } from '../../application/workspace/resolveWorkspaceExportRunId';
import type { ExportWizardCandidate } from '../../components/workspace/ExportWizardModal';

interface Props {
  selection: AreaSelection;
  onNavigate: (path: string) => void;
  onRefreshFiles: () => void;
  onUploadFile: (file: File) => Promise<UploadedFileResult>;
}

export function ArtifactsPage({
  selection,
  onNavigate,
  onRefreshFiles,
  onUploadFile,
}: Props) {
  const { t } = useI18n();
  const [metricQuery, setMetricQuery] = useState('');
  const currentSessionId = useChatStore((state) => state.sessionId);
  const cardsById = useChatStore((state) => state.cardsById);
  const selectedRunId = useRuntimeStore((state) => state.selectedRunId);
  const runtimeRuns = useRuntimeStore((state) => state.runs);
  const reasoningRunId = useReasoningTraceStore((state) => state.runId);
  const pinnedItems = useWorkspaceStore((state) => state.readModel.pinnedItems);
  const view = normalizeArtifactsView(selection);
  const workspaceRoute = parseEvidenceWorkspaceRoute(selection);
  const workspaceExportRunId = useMemo(
    () =>
      resolveWorkspaceExportRunId({
        focus: workspaceRoute.focus,
        sessionId: currentSessionId,
        selectedRunId,
        reasoningRunId,
        runtimeRuns,
        cards: Object.values(cardsById),
        pinnedItems,
      }),
    [
      cardsById,
      currentSessionId,
      pinnedItems,
      reasoningRunId,
      runtimeRuns,
      selectedRunId,
      workspaceRoute.focus,
    ],
  );
  const authoritativeExportArtifacts = useWorkspaceExportArtifacts(workspaceExportRunId);
  const authoritativeExportCandidates = useMemo<readonly ExportWizardCandidate[]>(
    () =>
      authoritativeExportArtifacts.exportCandidates.map((candidate) => ({
        id: candidate.path,
        name: candidate.name,
        path: candidate.path,
        type: candidate.type,
        formats: candidate.formats,
      })),
    [authoritativeExportArtifacts.exportCandidates],
  );
  const labels: Record<ArtifactView, string> = {
    files: t('area.artifacts.views.files'),
    experiments: t('area.artifacts.views.experiments'),
    portfolio: t('area.artifacts.views.portfolio'),
    workspace: 'Workspace',
  };

  function handleOpenPinnedItem(item: WorkspacePinnedProjectionItem): void {
    onNavigate(buildEvidenceWorkspacePath('summary', {
      mode: 'detail',
      target: 'card',
      value: item.cardId,
    }));
  }

  return (
    <div className="flex h-full min-w-0 flex-col overflow-hidden">
      <div className="border-b border-ds-border px-6 py-4">
        <h1 className="text-lg font-semibold text-ds-text">{t('area.artifacts.label')}</h1>
        <p className="mt-1 text-sm text-ds-muted">{t('area.artifacts.description')}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {(['files', 'experiments', 'portfolio', 'workspace'] as const).map((candidate) => (
            <button
              key={candidate}
              type="button"
              onClick={() => onNavigate(`/artifacts/${candidate}`)}
              className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                view === candidate
                  ? 'border-ds-accent bg-ds-accent/10 text-ds-accent'
                  : 'border-ds-border bg-ds-surface text-ds-muted hover:text-ds-text'
              }`}
            >
              {labels[candidate]}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {view === 'files' && (
          <div className="grid gap-4 xl:grid-cols-[minmax(280px,0.7fr)_minmax(0,1.3fr)]">
            <div className="space-y-4">
              <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
                <ProjectPanel />
              </section>
              <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
                <FileUpload onUpload={onUploadFile} />
              </section>
            </div>
            <div className="space-y-4">
              <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
                <FileExplorer onRefresh={onRefreshFiles} />
              </section>
              <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
                <PlotGallery />
              </section>
            </div>
          </div>
        )}

        {view === 'experiments' && (
          <div className="grid gap-4 xl:grid-cols-[minmax(320px,0.7fr)_minmax(0,1.3fr)]">
            <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
              <MetricSourcePanel metricQuery={metricQuery} />
            </section>
            <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
              <ExperimentTable activeMetricKey={metricQuery} onInspectMetric={setMetricQuery} />
            </section>
          </div>
        )}

        {view === 'portfolio' && (
          <section className="rounded-2xl border border-ds-border bg-ds-surface/70">
            <ProjectControlTower />
          </section>
        )}

        {view === 'workspace' && (
          <EvidenceWorkspace
            activeTab={workspaceRoute.tab}
            focus={workspaceRoute.focus}
            onChangeTab={(tab) => onNavigate(buildEvidenceWorkspacePath(tab))}
            onOpenPinnedItem={handleOpenPinnedItem}
            onRefreshFiles={onRefreshFiles}
            authoritativeExportCandidates={authoritativeExportCandidates}
            authoritativeExportLoading={authoritativeExportArtifacts.loading}
            authoritativeExportRunId={authoritativeExportArtifacts.runId}
            exportPort={exportWorkspaceFile}
          />
        )}
      </div>
    </div>
  );
}
