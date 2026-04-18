/**
 * Sidebar — 3-tab layout (Files / Workflow / Experiments) + Model/Mode/Budget.
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
} from 'lucide-react';
import { useState } from 'react';
import { useAgentStore } from '../../stores/agentStore';
import { useWorkflowStore, type SidebarTab } from '../../stores/workflowStore';
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
import type { ModelGroup } from '../../hooks/useModels';
import type { SimpleQualityPreset } from '../../utils/qualityPreset';

interface Props {
  onRefreshFiles: () => void;
  onChangeModel: (model: string) => void;
  onChangeQualityPreset: (preset: SimpleQualityPreset) => void;
  onChangeMode: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
  onUploadFile: (file: File) => Promise<string | null>;
  onOpenSettings: () => void;
  modelGroups: ModelGroup[];
}

const TABS: { id: SidebarTab; icon: typeof FolderOpen; label: string }[] = [
  { id: 'files', icon: FolderOpen, label: 'Files' },
  { id: 'workflow', icon: BarChart3, label: 'Workflow' },
  { id: 'review', icon: ShieldCheck, label: 'Review' },
  { id: 'runtime', icon: Server, label: 'Runtime' },
  { id: 'experiments', icon: FlaskConical, label: 'Experiments' },
  { id: 'portfolio', icon: Layers, label: 'Portfolio' },
  { id: 'learning', icon: Bot, label: 'Learning' },
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
  const activeTab = useWorkflowStore((s) => s.activeTab);
  const setActiveTab = useWorkflowStore((s) => s.setActiveTab);
  const [inspectedMetricQuery, setInspectedMetricQuery] = useState<string>('');

  return (
    <div className="w-56 bg-ds-surface border-r border-ds-border flex flex-col h-full">
      {/* Logo */}
      <div className="px-4 py-3 border-b border-ds-border">
        <div className="flex items-center gap-2">
          <Bot size={20} className="text-ds-accent" />
          <span className="text-sm font-semibold text-ds-text">DS Agent</span>
          <span className="text-[10px] text-ds-muted bg-ds-bg px-1.5 py-0.5 rounded">v0.1</span>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-ds-border">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            data-testid={`sidebar-tab-${tab.id}`}
            className={`flex-1 py-1.5 flex items-center justify-center transition-colors ${
              activeTab === tab.id
                ? 'text-ds-accent border-b-2 border-ds-accent'
                : 'text-ds-muted hover:text-ds-text'
            }`}
            title={tab.label}
          >
            <tab.icon size={14} />
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto py-2 space-y-1">
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

      {/* Bottom: model, mode, budget */}
      <div className="border-t border-ds-border space-y-0">
        <ModelSelector
          onChangeModel={onChangeModel}
          onChangeQualityPreset={onChangeQualityPreset}
          groups={modelGroups}
        />

        <div className="mx-3 border-t border-ds-border/50" />

        <ModeSelector onChange={onChangeMode} />

        <UsageMeter />

        {/* Budget bar */}
        <BudgetBar />

        {/* Cost + Settings */}
        <div className="px-3 py-2 border-t border-ds-border/50 flex items-center justify-between">
          <div className="text-xs text-ds-muted">
            Cost: <span className="text-ds-text font-mono">${cost.toFixed(4)}</span>
          </div>
          <button
            onClick={onOpenSettings}
            data-testid="open-settings"
            className="p-1 rounded hover:bg-ds-bg text-ds-muted hover:text-ds-text transition-colors"
            title="Settings (Ctrl+,)"
          >
            <Settings size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
