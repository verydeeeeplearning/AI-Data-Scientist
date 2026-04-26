import { useId } from 'react';
import { FileOutput, Pin } from 'lucide-react';
import { Badge, Card } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import type { EvidenceWorkspaceTab, WorkspaceReadModel } from '../../stores/workspaceStore';

interface Props {
  activeTab: EvidenceWorkspaceTab;
  readModel: WorkspaceReadModel;
  exportCandidateCount?: number;
  onSelectTab: (tab: EvidenceWorkspaceTab) => void;
}

const SECTION_ICONS = {
  overview: Pin,
  export: FileOutput,
} as const;

function formatLastUpdated(
  timestamp: number | null,
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string,
): string {
  if (timestamp == null) {
    return t('workspace:overviewRail.metric.lastUpdated.empty');
  }
  return new Date(timestamp).toLocaleString();
}

export function WorkspaceOverviewRail({
  activeTab,
  readModel,
  exportCandidateCount,
  onSelectTab,
}: Props) {
  const { t } = useI18n();
  const overviewTitleId = useId();
  const sectionsTitleId = useId();
  const resolvedExportCandidateCount = exportCandidateCount ?? readModel.exportCandidateCount;
  const sections = readModel.sections.map((section) => (
    section.id === 'export'
      ? {
          ...section,
          itemCount: resolvedExportCandidateCount,
          hasContent: resolvedExportCandidateCount > 0,
        }
      : section
  ));
  return (
    <aside className="space-y-4">
      <Card role="region" aria-labelledby={overviewTitleId}>
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-ds-muted">
          {t('workspace:evidence.heading')}
        </p>
        <h2 id={overviewTitleId} className="mt-3 text-lg font-semibold text-ds-text">
          {t('workspace:overviewRail.title')}
        </h2>
        <p className="mt-2 text-sm leading-6 text-ds-muted">
          {t('workspace:overviewRail.description')}
        </p>
        <dl className="mt-4 space-y-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-ds-muted">{t('workspace:overviewRail.metric.pinnedEvidence')}</dt>
            <dd className="font-medium text-ds-text">{readModel.pinnedCardCount}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-ds-muted">{t('workspace:overviewRail.metric.artifactsTracked')}</dt>
            <dd className="font-medium text-ds-text">
              {readModel.nonPlotFileCount + readModel.plotCount}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-ds-muted">{t('workspace:overviewRail.metric.lastUpdated')}</dt>
            <dd className="max-w-[10rem] text-right text-ds-text">
              {formatLastUpdated(readModel.lastUpdatedAt, t)}
            </dd>
          </div>
        </dl>
      </Card>

      <Card role="region" aria-labelledby={sectionsTitleId}>
        <h3 id={sectionsTitleId} className="text-sm font-semibold text-ds-text">
          {t('workspace:overviewRail.sections.title')}
        </h3>
        <nav className="mt-3 space-y-2" aria-labelledby={sectionsTitleId}>
          {sections.map((section) => {
            const Icon = SECTION_ICONS[section.id];
            const isActive = section.id === activeTab;
            return (
              <button
                key={section.id}
                type="button"
                onClick={() => onSelectTab(section.id)}
                aria-current={isActive ? 'true' : undefined}
                className={`w-full rounded-ds-xl border px-3 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg ${
                  isActive
                    ? 'border-ds-accent bg-ds-accent/10'
                    : 'border-ds-border bg-ds-bg/40 hover:border-ds-accent/40'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Icon
                      size={15}
                      className={isActive ? 'text-ds-accent' : 'text-ds-muted'}
                      aria-hidden="true"
                    />
                    <span className="text-sm font-medium text-ds-text">
                      {t(`workspace:section.${section.id}.label`)}
                    </span>
                  </div>
                  <Badge tone={section.hasContent ? 'accent' : 'neutral'} compact>
                    {section.itemCount}
                  </Badge>
                </div>
                <p className="mt-2 text-xs leading-5 text-ds-muted">
                  {t(`workspace:section.${section.id}.description`)}
                </p>
              </button>
            );
          })}
        </nav>
      </Card>
    </aside>
  );
}
