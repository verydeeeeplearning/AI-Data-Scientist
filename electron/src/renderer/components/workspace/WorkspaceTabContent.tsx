import type { ExportWizardCandidate } from './ExportWizardModal';
import { Badge, Button, Card } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import type {
  EvidenceWorkspaceTab,
  WorkspacePinnedProjectionItem,
  WorkspaceReadModel,
} from '../../stores/workspaceStore';
import { WorkspaceEmptyState } from './WorkspaceEmptyState';
import { WorkspacePinnedProjectionList } from './WorkspacePinnedProjectionList';
import type { EvidenceWorkspaceFocus } from '../../application/workspace/workspaceRoute';

export type WorkspaceExportDisplayCandidate = ExportWizardCandidate & {
  sourceKind?: 'file' | 'plot';
};

interface Props {
  activeTab: EvidenceWorkspaceTab;
  focus: EvidenceWorkspaceFocus | null;
  readModel: WorkspaceReadModel;
  exportCandidates: readonly WorkspaceExportDisplayCandidate[];
  exportCandidatesLoading?: boolean;
  exportCandidatesRunId?: string | null;
  onOpenPinnedItem: (item: WorkspacePinnedProjectionItem) => void;
  onOpenFiles: () => void;
  onLaunchExportWizard: () => void;
}

function ExportStatusMeta({
  exportCandidatesLoading,
  exportCandidatesRunId,
}: {
  exportCandidatesLoading?: boolean;
  exportCandidatesRunId?: string | null;
}) {
  const { t } = useI18n();
  if (!exportCandidatesLoading && !exportCandidatesRunId) {
    return null;
  }

  return (
    <div className="mt-3 space-y-2">
      {exportCandidatesLoading && (
        <p role="status" aria-live="polite" className="text-xs text-ds-muted">
          {t('workspace:export.status.refreshing')}
        </p>
      )}
      {exportCandidatesRunId && (
        <p className="text-[11px] text-ds-muted">
          {t('workspace:export.status.runContext', { runId: exportCandidatesRunId })}
        </p>
      )}
    </div>
  );
}

function OverviewTab({
  focus,
  readModel,
  exportCandidates,
  exportCandidatesLoading,
  exportCandidatesRunId,
  onOpenPinnedItem,
}: {
  focus: EvidenceWorkspaceFocus | null;
  readModel: WorkspaceReadModel;
  exportCandidates: readonly WorkspaceExportDisplayCandidate[];
  exportCandidatesLoading?: boolean;
  exportCandidatesRunId?: string | null;
  onOpenPinnedItem: (item: WorkspacePinnedProjectionItem) => void;
}) {
  const { t } = useI18n();
  const metrics = [
    { label: t('workspace:summary.metric.pinnedEvidence'), value: readModel.pinnedCardCount },
    { label: t('workspace:summary.metric.filesTracked'), value: readModel.nonPlotFileCount },
    { label: t('workspace:summary.metric.chartsTracked'), value: readModel.plotCount },
    { label: t('workspace:summary.metric.exportReady'), value: exportCandidates.length },
  ];

  return (
    <div className="space-y-4">
      <dl className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <Card key={metric.label} className="bg-ds-bg/40 shadow-none">
            <dt className="text-xs uppercase tracking-[0.18em] text-ds-muted">{metric.label}</dt>
            <dd className="mt-3 text-2xl font-semibold text-ds-text">{metric.value}</dd>
          </Card>
        ))}
      </dl>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
        <Card className="bg-ds-bg/40 shadow-none">
          <h3 className="text-sm font-semibold text-ds-text">
            {t('workspace:summary.pinnedProjection.title')}
          </h3>
          <p className="mt-2 text-sm leading-6 text-ds-muted">
            {t('workspace:summary.pinnedProjection.description')}
          </p>
          <div className="mt-4">
            <WorkspacePinnedProjectionList
              items={readModel.pinnedItems}
              pinnedCardCount={readModel.pinnedCardCount}
              status={readModel.pinnedProjectionStatus}
              focus={focus}
              onSelectItem={onOpenPinnedItem}
            />
          </div>
        </Card>

        <Card className="bg-ds-bg/40 shadow-none">
          <h3 className="text-sm font-semibold text-ds-text">
            {t('workspace:summary.exportReadiness.title')}
          </h3>
          {exportCandidates.length === 0 ? (
            <p className="mt-2 text-sm leading-6 text-ds-muted">
              {t('workspace:summary.exportReadiness.empty')}
            </p>
          ) : (
            <div className="mt-3 space-y-3">
              {exportCandidates.map((candidate) => (
                <ExportCandidateCard key={candidate.id} candidate={candidate} />
              ))}
            </div>
          )}
          <ExportStatusMeta
            exportCandidatesLoading={exportCandidatesLoading}
            exportCandidatesRunId={exportCandidatesRunId}
          />
        </Card>
      </div>
    </div>
  );
}

function ExportTab({
  exportCandidates,
  exportCandidatesLoading,
  exportCandidatesRunId,
  onOpenFiles,
  onLaunchExportWizard,
}: {
  exportCandidates: readonly WorkspaceExportDisplayCandidate[];
  exportCandidatesLoading?: boolean;
  exportCandidatesRunId?: string | null;
  onOpenFiles: () => void;
  onLaunchExportWizard: () => void;
}) {
  const { t } = useI18n();
  if (exportCandidates.length === 0) {
    return (
      <WorkspaceEmptyState
        title={t('workspace:export.empty.title')}
        description={t('workspace:export.empty.description')}
        action={(
          <Button
            onClick={onOpenFiles}
            variant="secondary"
            size="sm"
          >
            {t('workspace:export.openFiles')}
          </Button>
        )}
      />
    );
  }

  return (
    <div className="space-y-4">
      <Card className="bg-ds-bg/40 shadow-none">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-ds-text">
            {t('workspace:export.available.title')}
          </h3>
          <Button
            onClick={onLaunchExportWizard}
            variant="primary"
            size="sm"
          >
            {t('workspace:exportWizard.button.start')}
          </Button>
        </div>
        <ExportStatusMeta
          exportCandidatesLoading={exportCandidatesLoading}
          exportCandidatesRunId={exportCandidatesRunId}
        />
        <div className="mt-3 space-y-3">
          {exportCandidates.map((candidate) => (
            <ExportCandidateCard key={candidate.id} candidate={candidate} />
          ))}
        </div>
      </Card>

      <Card className="bg-ds-bg/40 shadow-none">
        <h3 className="text-sm font-semibold text-ds-text">{t('workspace:export.handoff.title')}</h3>
        <p className="mt-2 text-sm leading-6 text-ds-muted">
          {t('workspace:export.handoff.description')}
        </p>
        <Button
          onClick={onOpenFiles}
          variant="secondary"
          size="sm"
          className="mt-4"
        >
          {t('workspace:export.handoff.review')}
        </Button>
      </Card>
    </div>
  );
}

function ExportCandidateCard({ candidate }: { candidate: WorkspaceExportDisplayCandidate }) {
  const formatList = candidate.formats.map((format) => format.toUpperCase()).join(', ');

  return (
    <Card className="bg-ds-surface/60 shadow-none">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-ds-text" title={candidate.name}>
            {candidate.name}
          </div>
          <div className="mt-1 truncate text-xs text-ds-muted" title={candidate.path}>
            {candidate.path}
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Badge compact tone="accent" className="uppercase tracking-wide">
            {candidate.type}
          </Badge>
          {candidate.sourceKind && (
            <Badge compact tone="neutral" className="normal-case">
              {candidate.sourceKind}
            </Badge>
          )}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {candidate.formats.map((format) => (
          <Badge
            key={format}
            compact
            tone="neutral"
            className="uppercase tracking-wide"
          >
            {format}
          </Badge>
        ))}
      </div>
      <p className="mt-3 text-xs leading-5 text-ds-muted">
        Available formats: {formatList}
      </p>
    </Card>
  );
}

export function WorkspaceTabContent({
  activeTab,
  focus,
  readModel,
  exportCandidates,
  exportCandidatesLoading,
  exportCandidatesRunId,
  onOpenPinnedItem,
  onOpenFiles,
  onLaunchExportWizard,
}: Props) {
  if (activeTab === 'overview') {
    return (
      <OverviewTab
        focus={focus}
        readModel={readModel}
        exportCandidates={exportCandidates}
        exportCandidatesLoading={exportCandidatesLoading}
        exportCandidatesRunId={exportCandidatesRunId}
        onOpenPinnedItem={onOpenPinnedItem}
      />
    );
  }
  return (
    <ExportTab
      exportCandidates={exportCandidates}
      exportCandidatesLoading={exportCandidatesLoading}
      exportCandidatesRunId={exportCandidatesRunId}
      onOpenFiles={onOpenFiles}
      onLaunchExportWizard={onLaunchExportWizard}
    />
  );
}
