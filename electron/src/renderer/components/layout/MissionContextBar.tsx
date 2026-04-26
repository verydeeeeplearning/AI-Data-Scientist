/**
 * MissionContextBar — top strip, 44px tall, always visible across every area.
 *
 * Replaces the role of MissionHeader+MissionPage.
 * Compact by design: a few clickable slots that either open a drawer or
 * navigate deeper. Goal is the only growable slot; everything else is
 * icon + value pair.
 *
 * Slot click semantics:
 *   - Goal → opens GoalDrawer (TODO: reuse existing components/mission/GoalDrawer)
 *   - Stage → navigates to /runs and scrolls to current stage
 *   - Mode / Model / Budget → opens SessionDrawer (⌘;)
 *   - Warnings (only if any) → /runs (warnings panel)
 */

import {
  AlertTriangle,
  CircleDot,
  Cpu,
  DollarSign,
  Gauge,
  Target,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { useAgentStore } from '../../stores/agentStore';
import { useChatStore } from '../../stores/chatStore';
import { useConfigStore } from '../../stores/configStore';
import { useWorkflowStore } from '../../stores/workflowStore';
import { useUsageStore } from '../../stores/usageStore';
import { useI18n } from '../../stores/i18nStore';
import {
  formatBudget,
  formatBudgetRatio,
  formatElapsed,
  formatStage,
} from '../../application/mission/formatSessionSummary';

interface Props {
  connected: boolean;
  onOpenGoal: () => void;
  onOpenStage: () => void;
  onOpenSession: () => void;
}

interface SlotProps {
  icon: typeof Target;
  label: string;
  value: React.ReactNode;
  warning?: boolean;
  onClick?: () => void;
  testId?: string;
}

function Slot({ icon: Icon, label, value, warning, onClick, testId }: SlotProps) {
  const tone = warning
    ? 'text-ds-warning hover:bg-ds-warning/10'
    : 'text-ds-muted hover:bg-ds-bg hover:text-ds-text';
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      data-testid={testId}
      className={`flex h-full items-center gap-1.5 rounded px-2 transition-colors ${tone} focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50`}
    >
      <Icon size={13} className="shrink-0" />
      <span className="truncate font-mono text-[11px]">{value}</span>
    </button>
  );
}

export function MissionContextBar({ connected, onOpenGoal, onOpenStage, onOpenSession }: Props) {
  const { t } = useI18n();

  const goal = useChatStore((s) => s.goal);
  const startedAt = useChatStore((s) => s.startedAt);
  const isStreaming = useChatStore((s) => s.isStreaming);

  const model = useAgentStore((s) => s.model);
  const mode = useAgentStore((s) => s.mode);

  // Derive stage progress from workflowStore.stages (the canonical source).
  // currentStage = count of stages already completed or in flight.
  const stages = useWorkflowStore((s) => s.stages);
  const warnings = useWorkflowStore((s) => s.warnings);
  const totalStages = stages.length;
  const currentStage = stages.reduce(
    (acc, st) => (st.status === 'pending' ? acc : acc + 1),
    0,
  );
  const activeWarnings = warnings.filter((w) => !w.dismissed);

  // sessionCostUsd reflects the current chat session's spend (matches what
  // the budget chip is meant to convey — "how much have I spent right now?").
  const cost = useUsageStore((s) => s.summary?.sessionCostUsd ?? 0);
  const budgetLimit = useConfigStore((s) => s.maxBudgetUsd);
  const budgetWarn = formatBudgetRatio(cost, budgetLimit) >= 0.8;

  // Re-render every 5s while streaming so elapsed counter ticks.
  const [, force] = useState(0);
  useEffect(() => {
    if (!isStreaming || !startedAt) return;
    const id = window.setInterval(() => force((n) => n + 1), 5000);
    return () => window.clearInterval(id);
  }, [isStreaming, startedAt]);

  return (
    <header
      role="banner"
      aria-label={t('mission.context.label')}
      className="flex h-11 shrink-0 items-center gap-2 border-b border-ds-border bg-ds-surface px-3"
    >
      {/* Goal — primary entry point, allowed to grow */}
      <button
        type="button"
        onClick={onOpenGoal}
        data-testid="mission-context-goal"
        className="group flex min-w-0 flex-1 items-center gap-2 rounded px-2 py-1 text-left transition-colors hover:bg-ds-bg focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50"
      >
        <Target size={14} className="shrink-0 text-ds-accent" />
        <span className="truncate text-sm font-medium text-ds-text">
          {goal && goal.trim().length > 0 ? goal : t('mission.context.goalEmpty')}
        </span>
        {startedAt && (
          <span className="ml-2 shrink-0 font-mono text-[10px] text-ds-muted">
            {formatElapsed(startedAt)}
          </span>
        )}
      </button>

      <div className="h-5 w-px bg-ds-border" aria-hidden />

      <Slot
        icon={Gauge}
        label={t('mission.context.stage')}
        value={formatStage(currentStage, totalStages, t('mission.context.stageIdle'))}
        onClick={onOpenStage}
        testId="mission-context-stage"
      />
      <Slot
        icon={CircleDot}
        label={t('mission.context.mode')}
        value={t(`mode.${mode}.short` as never) || mode}
        onClick={onOpenSession}
        testId="mission-context-mode"
      />
      <Slot
        icon={Cpu}
        label={t('mission.context.model')}
        value={model || t('mission.context.modelMissing')}
        onClick={onOpenSession}
        testId="mission-context-model"
      />
      <Slot
        icon={DollarSign}
        label={t('mission.context.budget')}
        value={formatBudget(cost, budgetLimit)}
        warning={budgetWarn}
        onClick={onOpenSession}
        testId="mission-context-budget"
      />

      {activeWarnings.length > 0 && (
        <Slot
          icon={AlertTriangle}
          label={t('mission.context.warnings')}
          value={String(activeWarnings.length)}
          warning
          onClick={onOpenStage}
          testId="mission-context-warnings"
        />
      )}

      <div
        className="flex h-full items-center px-1.5"
        title={connected ? t('mission.context.connected') : t('mission.context.disconnected')}
        data-testid="mission-context-connection"
      >
        {connected ? (
          <Wifi size={14} className="text-ds-success" />
        ) : (
          <WifiOff size={14} className="text-ds-error" />
        )}
      </div>
    </header>
  );
}
