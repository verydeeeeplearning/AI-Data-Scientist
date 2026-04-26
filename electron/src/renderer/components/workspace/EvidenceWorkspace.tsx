import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { Pin } from 'lucide-react';
import { Badge, Button, Card } from '../../design-system/primitives';
import { useChatStore } from '../../stores/chatStore';
import { useFilesStore } from '../../stores/filesStore';
import { useI18n } from '../../stores/i18nStore';
import {
  EVIDENCE_WORKSPACE_TABS,
  useWorkspaceStore,
  type EvidenceWorkspaceTab,
  type WorkspacePinnedProjectionItem,
} from '../../stores/workspaceStore';
import {
  getAudienceViewProfile,
  type EvidenceTabId,
} from '../../domain/workspace/audienceView';
import {
  applyAudienceViewToTabs,
  resolveActiveTabForAudience,
} from '../../application/workspace/applyAudienceView';
import { useAudienceViewTelemetry } from '../../hooks/useAudienceView';
import { AudienceViewSwitcher } from './AudienceViewSwitcher';
import { WorkspaceContextRail } from './WorkspaceContextRail';
import { WorkspaceOverviewRail } from './WorkspaceOverviewRail';
import { WorkspaceTabContent } from './WorkspaceTabContent';
import type { EvidenceWorkspaceFocus } from '../../application/workspace/workspaceRoute';
import {
  ExportWizardModal,
  type ExportPort,
  type ExportWizardCandidate,
} from './ExportWizardModal';
import {
  prioritizeExportWizardCandidates,
  resolveExportWizardSelection,
} from '../../application/workspace/resolveExportWizardSelection';

interface Props {
  activeTab: EvidenceWorkspaceTab;
  focus: EvidenceWorkspaceFocus | null;
  onChangeTab: (tab: EvidenceWorkspaceTab) => void;
  onOpenFiles: () => void;
  onOpenPinnedItem: (item: WorkspacePinnedProjectionItem) => void;
  onRefreshFiles: () => void;
  authoritativeExportCandidates?: readonly ExportWizardCandidate[];
  authoritativeExportLoading?: boolean;
  authoritativeExportRunId?: string | null;
  exportPort: ExportPort;
}

export function EvidenceWorkspace({
  activeTab,
  focus,
  onChangeTab,
  onOpenFiles,
  onOpenPinnedItem,
  onRefreshFiles,
  authoritativeExportCandidates,
  authoritativeExportLoading = false,
  authoritativeExportRunId = null,
  exportPort,
}: Props) {
  const { t } = useI18n();
  const workspaceShellId = useId().replace(/:/g, '');
  const { files, plots, loading } = useFilesStore();
  const cardsById = useChatStore((state) => state.cardsById);
  const {
    readModel,
    setActiveTab,
    syncFromArtifacts,
    syncPinnedItems,
    audienceView,
    setAudienceView,
  } = useWorkspaceStore();
  const sessionId = useChatStore((state) => state.sessionId);
  const [exportWizardOpen, setExportWizardOpen] = useState(false);
  const exportWizardAutoOpenKey = useRef<string | null>(null);

  const audienceProfile = useMemo(
    () => getAudienceViewProfile(audienceView),
    [audienceView],
  );
  const visibleTabs = useMemo(
    () =>
      applyAudienceViewToTabs(
        EVIDENCE_WORKSPACE_TABS as ReadonlyArray<EvidenceTabId>,
        audienceProfile,
      ),
    [audienceProfile],
  );
  const resolvedActiveTab = useMemo(
    () =>
      resolveActiveTabForAudience(
        activeTab as EvidenceTabId,
        EVIDENCE_WORKSPACE_TABS as ReadonlyArray<EvidenceTabId>,
        audienceProfile,
      ) ?? activeTab,
    [activeTab, audienceProfile],
  );

  useEffect(() => {
    if (resolvedActiveTab !== activeTab) {
      onChangeTab(resolvedActiveTab as EvidenceWorkspaceTab);
    }
  }, [activeTab, onChangeTab, resolvedActiveTab]);

  useAudienceViewTelemetry(audienceView, { sessionId });

  useEffect(() => {
    setActiveTab(activeTab);
  }, [activeTab, setActiveTab]);

  useEffect(() => {
    syncFromArtifacts({ files, plots, loading });
  }, [files, plots, loading, syncFromArtifacts]);

  useEffect(() => {
    syncPinnedItems(Object.values(cardsById));
  }, [cardsById, syncPinnedItems]);

  function handleTabKeyDown(
    event: KeyboardEvent<HTMLButtonElement>,
    currentIndex: number,
  ) {
    if (
      event.key !== 'ArrowRight'
      && event.key !== 'ArrowLeft'
      && event.key !== 'Home'
      && event.key !== 'End'
    ) {
      return;
    }
    event.preventDefault();
    if (visibleTabs.length === 0) {
      return;
    }

    let nextIndex = currentIndex;
    if (event.key === 'ArrowRight') {
      nextIndex = (currentIndex + 1) % visibleTabs.length;
    } else if (event.key === 'ArrowLeft') {
      nextIndex = (currentIndex - 1 + visibleTabs.length) % visibleTabs.length;
    } else if (event.key === 'Home') {
      nextIndex = 0;
    } else if (event.key === 'End') {
      nextIndex = visibleTabs.length - 1;
    }

    const nextTab = visibleTabs[nextIndex] as EvidenceWorkspaceTab;
    onChangeTab(nextTab);
    const target = document.getElementById(`${workspaceShellId}-tab-${nextTab}`);
    if (target instanceof HTMLButtonElement) {
      target.focus();
    }
  }

  const tabLabel = (tab: EvidenceWorkspaceTab) => t(`workspace:evidence.tab.${tab}`);
  const tabDescription = (tab: EvidenceWorkspaceTab) => t(`workspace:evidence.tab.${tab}.description`);
  const pinnedBadgeLabel = formatPinnedBadge(t, readModel.pinnedCardCount, focus);

  const wizardCandidates = useMemo(
    () => (
      authoritativeExportCandidates && authoritativeExportCandidates.length > 0
        ? [...authoritativeExportCandidates]
        : readModel.exportCandidates
    ),
    [authoritativeExportCandidates, readModel.exportCandidates],
  );
  const exportWizardEvidenceCards = useMemo(
    () => Object.values(cardsById),
    [cardsById],
  );
  const exportWizardSelection = useMemo(
    () =>
      resolveExportWizardSelection({
        focus,
        candidates: wizardCandidates,
        cards: exportWizardEvidenceCards,
        pinnedItems: readModel.pinnedItems,
      }),
    [exportWizardEvidenceCards, focus, readModel.pinnedItems, wizardCandidates],
  );
  const orderedWizardCandidates = useMemo(
    () =>
      prioritizeExportWizardCandidates(
        wizardCandidates,
        exportWizardSelection.preferredCandidateId,
      ),
    [exportWizardSelection.preferredCandidateId, wizardCandidates],
  );
  const displayExportCandidates = wizardCandidates;

  useEffect(() => {
    if (
      activeTab !== 'export'
      || !exportWizardSelection.shouldAutoOpen
      || orderedWizardCandidates.length === 0
    ) {
      exportWizardAutoOpenKey.current = null;
      return;
    }

    const focusKey = `${focus?.mode ?? 'none'}:${focus?.target ?? 'none'}:${focus?.value ?? 'none'}`;
    if (exportWizardAutoOpenKey.current === focusKey) {
      return;
    }

    exportWizardAutoOpenKey.current = focusKey;
    setExportWizardOpen(true);
  }, [activeTab, focus, orderedWizardCandidates.length, exportWizardSelection.shouldAutoOpen]);

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(220px,0.75fr)_minmax(0,1.55fr)_minmax(240px,0.85fr)]">
      <WorkspaceOverviewRail
        activeTab={activeTab}
        readModel={readModel}
        exportCandidateCount={displayExportCandidates.length}
        onSelectTab={onChangeTab}
      />

      <Card
        role="region"
        aria-labelledby={`${workspaceShellId}-heading`}
        className="overflow-hidden rounded-3xl bg-ds-surface/70 p-0"
      >
        <div className="border-b border-ds-border px-5 py-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-ds-muted">
                {t('workspace:evidence.heading')}
              </p>
              <h2
                id={`${workspaceShellId}-heading`}
                className="mt-2 text-xl font-semibold text-ds-text"
              >
                {tabLabel(activeTab)}
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-ds-muted">
                {tabDescription(activeTab)}
              </p>
            </div>
            <Badge
              tone={readModel.pinnedCardCount > 0 ? 'accent' : 'neutral'}
              leadingIcon={<Pin size={14} aria-hidden="true" />}
              className="max-w-full px-ds-3 py-ds-2 text-ds-sm"
            >
              {pinnedBadgeLabel}
            </Badge>
          </div>

          <div className="mt-5">
            <AudienceViewSwitcher value={audienceView} onChange={setAudienceView} />
          </div>

          <div
            className="mt-4 flex flex-wrap gap-2"
            role="tablist"
            aria-label={t('workspace:evidence.tabsLabel')}
            aria-orientation="horizontal"
          >
            {visibleTabs.map((tab, index) => (
              <Button
                key={tab}
                id={`${workspaceShellId}-tab-${tab}`}
                type="button"
                role="tab"
                aria-selected={activeTab === tab}
                aria-controls={`${workspaceShellId}-panel-${tab}`}
                tabIndex={activeTab === tab ? 0 : -1}
                onClick={() => onChangeTab(tab as EvidenceWorkspaceTab)}
                onKeyDown={(event) => handleTabKeyDown(event, index)}
                variant="ghost"
                size="sm"
                className={`min-h-10 px-ds-3 py-ds-2 text-sm shadow-none ${
                  activeTab === tab
                    ? 'border-ds-accent bg-ds-accent/10 text-ds-accent hover:bg-ds-accent/10 hover:text-ds-accent'
                    : 'border-ds-border bg-ds-bg/50 text-ds-muted hover:border-ds-accent/40 hover:bg-ds-bg hover:text-ds-text'
                }`}
              >
                {tabLabel(tab as EvidenceWorkspaceTab)}
              </Button>
            ))}
          </div>
        </div>

        <div
          id={`${workspaceShellId}-panel-${activeTab}`}
          role="tabpanel"
          aria-labelledby={`${workspaceShellId}-tab-${activeTab}`}
          aria-busy={readModel.status === 'loading'}
          className="p-4 md:p-5"
        >
          <WorkspaceTabContent
            activeTab={activeTab}
            focus={focus}
            readModel={readModel}
            exportCandidates={displayExportCandidates}
            exportCandidatesLoading={authoritativeExportLoading}
            exportCandidatesRunId={authoritativeExportRunId}
            onOpenPinnedItem={onOpenPinnedItem}
            onOpenFiles={onOpenFiles}
            onLaunchExportWizard={() => setExportWizardOpen(true)}
          />
        </div>
      </Card>

      <WorkspaceContextRail
        focus={focus}
        readModel={readModel}
        onOpenPinnedItem={onOpenPinnedItem}
        onRefreshFiles={onRefreshFiles}
        onOpenFiles={onOpenFiles}
      />

      <ExportWizardModal
        open={exportWizardOpen}
        candidates={orderedWizardCandidates}
        defaultAudience={audienceView}
        exportPort={exportPort}
        onClose={() => setExportWizardOpen(false)}
      />
    </div>
  );
}

function formatPinnedBadge(
  t: (key: string, vars?: Record<string, string | number | null | undefined>) => string,
  count: number,
  focus: EvidenceWorkspaceFocus | null,
): string {
  const base = count === 0
    ? t('workspace:evidence.pinnedBadge.zero')
    : count === 1
      ? t('workspace:evidence.pinnedBadge.one')
      : t('workspace:evidence.pinnedBadge.other', { count });
  if (focus?.mode === 'detail') {
    return `${base}${t('workspace:evidence.pinnedBadge.detailSuffix')}`;
  }
  if (focus?.mode === 'highlight') {
    return `${base}${t('workspace:evidence.pinnedBadge.highlightSuffix')}`;
  }
  return base;
}
