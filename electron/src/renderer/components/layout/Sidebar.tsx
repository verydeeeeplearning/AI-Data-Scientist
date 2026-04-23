/**
 * Sidebar — collapsible navigation rail + active panel content.
 */

import {
  Bot,
  FolderOpen,
  BarChart3,
  FlaskConical,
  Layers,
  Settings,
  Server,
  ShieldCheck,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { announce } from '../../application/a11y/ariaLive';
import {
  prefersReducedMotion,
  subscribeReducedMotion,
} from '../../application/a11y/reducedMotion';
import { useAgentStore } from '../../stores/agentStore';
import { useI18n } from '../../stores/i18nStore';
import { useWorkflowStore, type SidebarTab } from '../../stores/workflowStore';
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut';
import { useSidebarCollapse } from '../../hooks/useSidebarCollapse';
import { SidebarItem } from '../sidebar/SidebarItem';
import { FileExplorer } from '../sidebar/FileExplorer';
import { PlotGallery } from '../sidebar/PlotGallery';
import { ModelSelector } from '../sidebar/ModelSelector';
import { ModeSelector } from '../sidebar/ModeSelector';
import { UsageMeter } from '../sidebar/UsageMeter';
import { FileUpload } from '../sidebar/FileUpload';
import { ProjectPanel } from '../sidebar/ProjectPanel';
import { ApprovalPanel } from '../workflow/ApprovalPanel';
import { WorkflowProgress } from '../workflow/WorkflowProgress';
import { QualityPanel } from '../workflow/QualityPanel';
import { ExperimentTable } from '../workflow/ExperimentTable';
import { BudgetBar } from '../workflow/BudgetBar';
import { ReviewTab } from '../workflow/ReviewTab';
import { WorkObjectPanel } from '../workflow/WorkObjectPanel';
import { MetricSourcePanel } from '../semantic/MetricSourcePanel';
import { MissionBriefPanel } from '../mission/MissionBriefPanel';
import { GatewayStatusPanel } from '../runtime/GatewayStatusPanel';
import { PolicyPanel } from '../runtime/PolicyPanel';
import { RuntimeAlertsPanel } from '../runtime/RuntimeAlertsPanel';
import { CertificationBoard } from '../runtime/CertificationBoard';
import { RegressionBoard } from '../runtime/RegressionBoard';
import { ProjectControlTower } from '../portfolio/ProjectControlTower';
import { LearningInbox } from '../learning/LearningInbox';
import { SessionsPanel } from '../runtime/SessionsPanel';
import { RunsPanel } from '../runtime/RunsPanel';
import { TasksPanel } from '../runtime/TasksPanel';
import type { UploadedFileResult } from '../../domain/workspace/uploadedFile';
import type { ModelGroup } from '../../hooks/useModels';
import type { SimpleQualityPreset } from '../../utils/qualityPreset';
import {
  SIDEBAR_COLLAPSED_WIDTH,
  SIDEBAR_EXPANDED_WIDTH,
} from '../../utils/sidebarLayout';

interface Props {
  onRefreshFiles: () => void;
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  onChangeMode: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
  onUploadFile: (file: File) => Promise<UploadedFileResult>;
  onOpenSettings: () => void;
  modelGroups: ModelGroup[];
}

const TABS: { id: SidebarTab; icon: typeof FolderOpen; labelKey: string }[] = [
  { id: 'files', icon: FolderOpen, labelKey: 'sidebar.tab.files' },
  { id: 'workflow', icon: BarChart3, labelKey: 'sidebar.tab.workflow' },
  { id: 'review', icon: ShieldCheck, labelKey: 'sidebar.tab.review' },
  { id: 'runtime', icon: Server, labelKey: 'sidebar.tab.runtime' },
  { id: 'experiments', icon: FlaskConical, labelKey: 'sidebar.tab.experiments' },
  { id: 'portfolio', icon: Layers, labelKey: 'sidebar.tab.portfolio' },
  { id: 'learning', icon: Bot, labelKey: 'sidebar.tab.learning' },
];

export function Sidebar({
  onRefreshFiles,
  onChangeModel,
  onChangeQualityPreset,
  onChangeMode,
  onUploadFile,
  onOpenSettings,
  modelGroups,
}: Props) {
  const { cost } = useAgentStore();
  const { t } = useI18n();
  const activeTab = useWorkflowStore((s) => s.activeTab);
  const setActiveTab = useWorkflowStore((s) => s.setActiveTab);
  const [inspectedMetricQuery, setInspectedMetricQuery] = useState<string>('');
  const [reducedMotion, setReducedMotion] = useState<boolean>(() => prefersReducedMotion());
  const { collapsed, toggleSidebar } = useSidebarCollapse();
  const navRef = useRef<HTMLElement | null>(null);
  const shouldFocusActiveTabRef = useRef(false);
  const announceReadyRef = useRef(false);
  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_EXPANDED_WIDTH;
  const toggleLabel = collapsed ? t('sidebar.toggle.expand') : t('sidebar.toggle.collapse');

  useEffect(() => subscribeReducedMotion(setReducedMotion, { emitInitial: true }), []);

  useEffect(() => {
    if (!announceReadyRef.current) {
      announceReadyRef.current = true;
      return;
    }

    announce(
      collapsed ? t('sidebar.announce.collapsed') : t('sidebar.announce.expanded'),
    );
  }, [collapsed, t]);

  useEffect(() => {
    if (!collapsed || !shouldFocusActiveTabRef.current) {
      return;
    }

    const target = navRef.current?.querySelector<HTMLElement>(
      `[data-testid="sidebar-tab-${activeTab}"]`,
    );
    target?.focus();
    shouldFocusActiveTabRef.current = false;
  }, [activeTab, collapsed]);

  const handleToggleSidebar = () => {
    const activeElement = typeof document !== 'undefined' ? document.activeElement : null;
    if (!collapsed && activeElement instanceof HTMLElement && navRef.current?.contains(activeElement)) {
      shouldFocusActiveTabRef.current = true;
    }
    toggleSidebar();
  };

  useKeyboardShortcut('ctrl+\\', handleToggleSidebar);
  useKeyboardShortcut('meta+\\', handleToggleSidebar);

  return (
    <nav
      ref={navRef}
      role="navigation"
      aria-label="Primary navigation"
      className="flex h-full shrink-0 flex-col border-r border-ds-border bg-ds-surface transition-[width] ease-out"
      style={{
        width: `${sidebarWidth}px`,
        transitionDuration: reducedMotion ? '0ms' : '200ms',
      }}
    >
      <div className={`border-b border-ds-border px-2 py-3 ${collapsed ? '' : 'space-y-3'}`}>
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'justify-between gap-2'}`}>
          <div className={`flex items-center ${collapsed ? 'justify-center' : 'min-w-0 gap-2'}`}>
            <Bot size={20} className="shrink-0 text-ds-accent" />
            {!collapsed && (
              <>
                <span className="truncate text-sm font-semibold text-ds-text">DS Agent</span>
                <span className="rounded bg-ds-bg px-1.5 py-0.5 text-[10px] text-ds-muted">
                  v0.1
                </span>
              </>
            )}
          </div>
          <button
            onClick={handleToggleSidebar}
            aria-label={toggleLabel}
            aria-expanded={!collapsed}
            title={`${toggleLabel} (${t('sidebar.toggle.shortcut')})`}
            className="rounded p-1 text-ds-muted transition-colors hover:bg-ds-bg hover:text-ds-text focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50"
          >
            {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        <div className="space-y-1">
          {TABS.map((tab) => (
            <SidebarItem
              key={tab.id}
              icon={tab.icon}
              label={t(tab.labelKey)}
              active={activeTab === tab.id}
              collapsed={collapsed}
              onClick={() => setActiveTab(tab.id)}
              dataTestId={`sidebar-tab-${tab.id}`}
            />
          ))}
        </div>

        {!collapsed && (
          <div className="mt-3 space-y-1">
            {activeTab === 'files' && (
              <>
                <ProjectPanel />
                <div className="mx-3 border-t border-ds-border/50" />
                <FileExplorer onRefresh={onRefreshFiles} />
                <div className="mx-3 border-t border-ds-border/50" />
                <PlotGallery />
                <div className="mx-3 border-t border-ds-border/50" />
                <FileUpload onUpload={onUploadFile} />
              </>
            )}

            {activeTab === 'workflow' && (
              <>
                <MissionBriefPanel />
                <div className="mx-3 border-t border-ds-border/50" />
                <WorkObjectPanel />
                <div className="mx-3 border-t border-ds-border/50" />
                <ApprovalPanel />
                <div className="mx-3 border-t border-ds-border/50" />
                <WorkflowProgress />
                <div className="mx-3 border-t border-ds-border/50" />
                <QualityPanel />
              </>
            )}

            {activeTab === 'review' && <ReviewTab />}

            {activeTab === 'runtime' && (
              <>
                <GatewayStatusPanel />
                <div className="mx-3 border-t border-ds-border/50" />
                <RuntimeAlertsPanel />
                <div className="mx-3 border-t border-ds-border/50" />
                <PolicyPanel />
                <div className="mx-3 border-t border-ds-border/50" />
                <CertificationBoard />
                <div className="mx-3 border-t border-ds-border/50" />
                <RegressionBoard />
                <div className="mx-3 border-t border-ds-border/50" />
                <SessionsPanel />
                <div className="mx-3 border-t border-ds-border/50" />
                <RunsPanel />
                <div className="mx-3 border-t border-ds-border/50" />
                <TasksPanel />
                <div className="mx-3 border-t border-ds-border/50" />
                <ApprovalPanel />
              </>
            )}

            {activeTab === 'experiments' && (
              <>
                <MetricSourcePanel metricQuery={inspectedMetricQuery} />
                <div className="mx-3 border-t border-ds-border/50" />
                <ExperimentTable
                  activeMetricKey={inspectedMetricQuery}
                  onInspectMetric={setInspectedMetricQuery}
                />
              </>
            )}

            {activeTab === 'portfolio' && <ProjectControlTower />}

            {activeTab === 'learning' && <LearningInbox />}
          </div>
        )}
      </div>

      <div className="border-t border-ds-border px-2 py-2">
        {!collapsed && (
          <>
            <ModelSelector
              onChangeModel={onChangeModel}
              onChangeQualityPreset={onChangeQualityPreset}
              groups={modelGroups}
            />

            <div className="mx-1 border-t border-ds-border/50" />

            <ModeSelector onChange={onChangeMode} />

            <UsageMeter />

            <BudgetBar />

            <div className="flex items-center justify-between border-t border-ds-border/50 px-1 py-2">
              <div className="text-xs text-ds-muted">
                Cost: <span className="font-mono text-ds-text">${cost.toFixed(4)}</span>
              </div>
              <button
                onClick={onOpenSettings}
                data-testid="open-settings"
                className="rounded p-1 text-ds-muted transition-colors hover:bg-ds-bg hover:text-ds-text focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50"
                title="Settings (Ctrl+,)"
              >
                <Settings size={14} />
              </button>
            </div>
          </>
        )}

        {collapsed && (
          <SidebarItem
            icon={Settings}
            label={t('settings.title')}
            collapsed
            onClick={onOpenSettings}
            dataTestId="open-settings"
          />
        )}
      </div>
    </nav>
  );
}
