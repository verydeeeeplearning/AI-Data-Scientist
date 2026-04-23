import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';
import {
  createFocusTrap,
  type FocusTrap,
} from '../../application/a11y/focusManagement';
import { announce } from '../../application/a11y/ariaLive';
import {
  applyMissionPatch,
  COLLAPSED_SLOT_KEYS,
  deriveMissionBudgetState,
  isSnoozeActive,
  MISSION_BUDGET_SNOOZE_KEY,
  nextBudgetWarningVisibility,
  parseSnoozeStorage,
  serializeSnoozeStorage,
  snoozeUntil,
  type MissionBudgetState,
  type MissionDetailKey,
  type MissionSnoozeOption,
} from '../../application/mission/missionHeaderState';
import { pauseAgent } from '../../application/mission/pauseAgent';
import type { PauseAgentPort } from '../../application/mission/pauseAgentPort';
import { resumeFromCheckpoint } from '../../application/run/resumeFromCheckpoint';
import { saveCheckpoint } from '../../application/run/saveCheckpoint';
import {
  formatMissionMode,
  getMissionBudgetRatio,
  getMissionBudgetState,
  type MissionContext,
} from '../../domain/mission';
import { useModels } from '../../hooks/useModels';
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut';
import { useMissionContext } from '../../hooks/useMissionContext';
import { useMissionPause } from '../../hooks/useMissionPause';
import { useResumeFromCheckpoint } from '../../hooks/useResumeFromCheckpoint';
import { useSaveCheckpoint } from '../../hooks/useSaveCheckpoint';
import { useSessionHistory } from '../../hooks/useSessionHistory';
import { useWs } from '../../hooks/WsProvider';
import {
  buildCheckpointResumePrompt,
  copyCheckpointResumePrompt,
} from '../../infrastructure/api/checkpointResume';
import { Badge, Button, Card } from '../../design-system/primitives';
import { useChatStore } from '../../stores/chatStore';
import { useAgentStore } from '../../stores/agentStore';
import { useCanMutate } from '../../hooks/useCanMutate';
import { getLocaleOption, useI18n } from '../../stores/i18nStore';
import { ConnectionTooltip } from './ConnectionTooltip';
import { MissionSlot } from './MissionSlot';
import { RerunFromStepDialog } from '../runtime/RerunFromStepDialog';
import { ResumePromptFallbackDialog } from '../runtime/ResumePromptFallbackDialog';
import { SaveCheckpointDialog } from '../runtime/SaveCheckpointDialog';
import { useReasoningTraceStore } from '../../stores/reasoningTraceStore';

const GoalDrawer = lazy(() =>
  import('./GoalDrawer').then((m) => ({ default: m.GoalDrawer })),
);
const DataSourcesDrawer = lazy(() =>
  import('./DataSourcesDrawer').then((m) => ({ default: m.DataSourcesDrawer })),
);
const DeliverablesDrawer = lazy(() =>
  import('./DeliverablesDrawer').then((m) => ({ default: m.DeliverablesDrawer })),
);
const ConstraintsDrawer = lazy(() =>
  import('./ConstraintsDrawer').then((m) => ({ default: m.ConstraintsDrawer })),
);
const StageDrawer = lazy(() =>
  import('./StageDrawer').then((m) => ({ default: m.StageDrawer })),
);
const BudgetDrawer = lazy(() =>
  import('./BudgetDrawer').then((m) => ({ default: m.BudgetDrawer })),
);
const ModeDropdown = lazy(() =>
  import('./ModeDropdown').then((m) => ({ default: m.ModeDropdown })),
);
const ModelDropdown = lazy(() =>
  import('./ModelDropdown').then((m) => ({ default: m.ModelDropdown })),
);

type TranslateFn = (
  key: string,
  vars?: Record<string, string | number | undefined | null>,
) => string;

const DETAIL_TITLE_KEYS: Record<MissionDetailKey, string> = {
  goal: 'mission.header.slot.goal',
  dataSources: 'mission.header.slot.dataSources',
  deliverables: 'mission.header.slot.deliverables',
  constraints: 'mission.header.slot.constraints',
  stage: 'mission.header.slot.stage',
  mode: 'mission.header.slot.mode',
  model: 'mission.header.slot.model',
  budget: 'mission.header.slot.budget',
  connection: 'mission.header.slot.connection',
};

const MISSION_HEADER_COLLAPSE_STORAGE_KEY = 'ds-agent-mission-header-collapsed';

const SNOOZE_OPTIONS: ReadonlyArray<MissionSnoozeOption> = ['5m', '30m', '1h'];

interface Props {
  readonly sessionId: string;
  readonly isStreaming?: boolean;
  readonly onAbort?: () => void;
}

export function MissionHeader({ sessionId, isStreaming = false, onAbort }: Props) {
  const { rpc, status: wsStatus } = useWs();
  const { mission, loading, error, refresh } = useMissionContext(sessionId);
  const { openSession, openingSessionId } = useSessionHistory();
  const { grouped: modelGroups } = useModels(rpc, wsStatus === 'connected');
  const currentModel = useAgentStore((s) => s.model);
  const currentMode = useAgentStore((s) => s.mode);
  const updateFromStatus = useAgentStore((s) => s.updateFromStatus);
  const setMode = useAgentStore((s) => s.setMode);
  const resetConversation = useChatStore((s) => s.resetConversation);
  const { locale, t } = useI18n();
  const { canMutate, reason: mutateBlockedReason } = useCanMutate();
  const mutateBlockedTitle = mutateBlockedReason ? t(mutateBlockedReason) : undefined;
  const [selectedDetail, setSelectedDetail] = useState<MissionDetailKey | null>(null);
  const [collapsed, setCollapsed] = useState<boolean>(() => loadMissionHeaderCollapsed());
  const [showBudgetWarning, setShowBudgetWarning] = useState(false);
  const [snoozedUntil, setSnoozedUntil] = useState<number | null>(() =>
    parseSnoozeStorage(loadSnoozeStorage()).until,
  );
  const [pauseStatus, setPauseStatus] = useState<{ kind: 'idle' | 'pending' | 'paused' | 'error'; message?: string }>({ kind: 'idle' });
  const [checkpointResumeStatus, setCheckpointResumeStatus] = useState<{
    tone: 'success' | 'info' | 'error';
    message: string;
  } | null>(null);
  const [showConnectionTooltip, setShowConnectionTooltip] = useState(false);
  const detailPanelId = useId();
  const budgetModalRef = useRef<HTMLDivElement | null>(null);
  const budgetModalTrapRef = useRef<FocusTrap | null>(null);
  const previousBudgetStateRef = useRef<MissionBudgetState>('default');
  const localeTag = useMemo(() => getLocaleOption(locale).bcp47, [locale]);

  const budgetState: MissionBudgetState = mission ? getMissionBudgetState(mission.budget) : 'default';
  const budgetRatio = mission ? getMissionBudgetRatio(mission.budget) : 0;
  const connectionState = mission?.connection.state ?? 'disconnected';
  const stageMeta = mission
    ? `${mission.stage.current}/${mission.stage.total}`
    : t('mission.header.empty');

  const closeDetailPanel = useCallback(() => {
    setSelectedDetail(null);
  }, []);

  const handleChangeMode = useCallback(
    async (mode: 'auto' | 'supervised' | 'step-by-step') => {
      if (mode === currentMode) {
        setSelectedDetail(null);
        return;
      }
      await rpc('config.set', { path: 'agent.mode', value: mode });
      setMode(mode);
      setSelectedDetail(null);
    },
    [currentMode, rpc, setMode],
  );

  const handleChangeModel = useCallback(
    async (model: string) => {
      if (model === currentModel) {
        setSelectedDetail(null);
        return;
      }
      try {
        await rpc('chat.abort');
      } catch (error) {
        console.warn('[MissionHeader] abort before model change failed:', error);
      }
      await rpc('config.set', { path: 'provider.default_model', value: model });
      resetConversation(true);
      updateFromStatus(await rpc('status.get'));
      setSelectedDetail(null);
    },
    [currentModel, resetConversation, rpc, updateFromStatus],
  );

  const toggleCollapsed = useCallback(() => {
    setCollapsed((current) => !current);
  }, []);

  const visibleSlotKeys = collapsed ? COLLAPSED_SLOT_KEYS : null;

  useKeyboardShortcut('escape', closeDetailPanel, selectedDetail !== null);
  useKeyboardShortcut('ctrl+shift+m', toggleCollapsed);
  useKeyboardShortcut('meta+shift+m', toggleCollapsed);

  useEffect(() => {
    if (!mission && selectedDetail !== null) {
      setSelectedDetail(null);
    }
  }, [mission, selectedDetail]);

  useEffect(() => {
    saveMissionHeaderCollapsed(collapsed);
  }, [collapsed]);

  useEffect(() => {
    if (!collapsed || selectedDetail === null) {
      return;
    }
    if (!COLLAPSED_SLOT_KEYS.includes(selectedDetail)) {
      setSelectedDetail(null);
    }
  }, [collapsed, selectedDetail]);

  useEffect(() => {
    previousBudgetStateRef.current = 'default';
    setShowBudgetWarning(false);
    setPauseStatus({ kind: 'idle' });
    setCheckpointResumeStatus(null);
    setSaveCheckpointDialogOpen(false);
    setSaveCheckpointDialogError(null);
  }, [sessionId]);

  useEffect(() => {
    if (!checkpointResumeStatus) {
      return;
    }
    const timer = window.setTimeout(() => {
      setCheckpointResumeStatus(null);
    }, 8_000);
    return () => window.clearTimeout(timer);
  }, [checkpointResumeStatus]);

  useEffect(() => {
    if (!mission || !isStreaming) {
      previousBudgetStateRef.current = budgetState;
      return;
    }

    const previousBudgetState = previousBudgetStateRef.current;
    const visible = nextBudgetWarningVisibility({
      previous: previousBudgetState,
      next: budgetState,
      streaming: true,
      snoozedUntil,
      now: Date.now(),
    });
    if (visible) {
      setShowBudgetWarning(true);
    }
    previousBudgetStateRef.current = budgetState;
  }, [budgetState, isStreaming, mission, snoozedUntil]);

  useEffect(() => {
    const modal = budgetModalRef.current;
    if (!showBudgetWarning || !modal) {
      budgetModalTrapRef.current?.deactivate();
      budgetModalTrapRef.current = null;
      return;
    }

    const trap = createFocusTrap(modal);
    budgetModalTrapRef.current = trap;
    trap.activate();

    return () => {
      trap.deactivate();
      if (budgetModalTrapRef.current === trap) {
        budgetModalTrapRef.current = null;
      }
    };
  }, [showBudgetWarning]);

  useEffect(() => {
    if (!showBudgetWarning) {
      return;
    }
    const timer = window.setInterval(() => {
      if (snoozedUntil !== null && !isSnoozeActive({ until: snoozedUntil }, Date.now())) {
        setSnoozedUntil(null);
        saveSnoozeStorage(null);
      }
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [showBudgetWarning, snoozedUntil]);

  const slotSummaries = useMemo(() => {
    if (!mission) {
      return null;
    }

    return {
      goal: {
        label: t('mission.header.slot.goal'),
        value: mission.goal.title,
        meta: mission.goal.successCriteria[0] ?? t('mission.header.noSuccessCriteria'),
      },
      dataSources: {
        label: t('mission.header.slot.dataSources'),
        value: formatDataSourceSummary(mission, t),
        meta: mission.dataSources[0]?.label ?? t('mission.header.noSourceAttached'),
      },
      deliverables: {
        label: t('mission.header.slot.deliverables'),
        value: mission.deliverables.length > 0
          ? mission.deliverables.join(', ')
          : t('mission.header.none'),
        meta: t('mission.header.deliverableCount', {
          count: mission.deliverables.length.toLocaleString(localeTag),
        }),
      },
      constraints: {
        label: t('mission.header.slot.constraints'),
        value: formatConstraintSummary(mission, t),
        meta: mission.constraints.requiresApproval
          ? t('mission.header.approvalAware')
          : t('mission.header.autonomousReady'),
      },
      stage: {
        label: t('mission.header.slot.stage'),
        value: `${mission.stage.current}/${mission.stage.total} / ${mission.stage.label}`,
        meta: t('mission.header.currentStageMeta'),
      },
      mode: {
        label: t('mission.header.slot.mode'),
        value: formatMissionModeLabel(mission.mode, t),
        meta: t('mission.header.currentModeMeta'),
      },
      model: {
        label: t('mission.header.slot.model'),
        value: mission.model.primary,
        meta: mission.model.capabilities.join(', ') || t('mission.header.noCapabilities'),
      },
      budget: {
        label: t('mission.header.slot.budget'),
        value: formatBudget(mission.budget.spentUsd, mission.budget.limitUsd, localeTag),
        meta: t('mission.header.elapsed', {
          value: formatElapsed(mission.budget.elapsedSec),
        }),
      },
      connection: {
        label: t('mission.header.slot.connection'),
        value: formatConnectionState(connectionState, t),
        meta: typeof mission.connection.latencyMs === 'number'
          ? `${Math.round(mission.connection.latencyMs)} ms`
          : t('mission.header.noLatency'),
      },
    };
  }, [connectionState, localeTag, mission, t]);

  const modelOptions = useMemo(() => {
    const flattened = modelGroups.flatMap((group) => group.models);
    const seen = new Set<string>();
    return flattened.filter((entry) => {
      if (seen.has(entry.id)) {
        return false;
      }
      seen.add(entry.id);
      return true;
    });
  }, [modelGroups]);

  const handleBudgetWarningKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setShowBudgetWarning(false);
        return;
      }
      if (event.key === 'Tab') {
        event.preventDefault();
        budgetModalTrapRef.current?.cycle(event.shiftKey ? 'backward' : 'forward');
      }
    },
    [],
  );

  const pausePort: PauseAgentPort = useMissionPause();
  const resumePort = useResumeFromCheckpoint();
  const saveCheckpointPort = useSaveCheckpoint();
  const [saveCheckpointBusy, setSaveCheckpointBusy] = useState(false);
  const [saveCheckpointDialogOpen, setSaveCheckpointDialogOpen] = useState(false);
  const [saveCheckpointDialogError, setSaveCheckpointDialogError] = useState<string | null>(null);
  const [rerunDialogOpen, setRerunDialogOpen] = useState(false);
  const [resumeFallback, setResumeFallback] = useState<{
    prompt: string;
    errorDetail: string | null;
    clipboardCopied: boolean;
  } | null>(null);
  const rerunParentRunId = useReasoningTraceStore((state) => state.runId);

  const handlePauseAgent = useCallback(async () => {
    setPauseStatus({ kind: 'pending' });
    try {
      const result = await pauseAgent(pausePort, {
        sessionId,
        reason: 'budget_warning',
      });
      if (result.paused) {
        setPauseStatus({ kind: 'paused' });
        announce(t('mission.header.budgetAlert.paused'));
      } else {
        setPauseStatus({ kind: 'paused' });
      }
      setShowBudgetWarning(false);
      onAbort?.();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setPauseStatus({ kind: 'error', message });
      announce(t('mission.header.budgetAlert.pauseFailed', { reason: message }));
    }
  }, [onAbort, pausePort, sessionId, t]);

  const handleSnooze = useCallback(
    (option: MissionSnoozeOption) => {
      const next = snoozeUntil(Date.now(), option);
      setSnoozedUntil(next);
      saveSnoozeStorage(serializeSnoozeStorage({ until: next }));
      setShowBudgetWarning(false);
      announce(t('mission.header.budgetAlert.snoozedFor', {
        duration: t(`mission.header.budgetAlert.snooze.${option}`),
      }));
    },
    [t],
  );

  const handleDismissForSession = useCallback(() => {
    setSnoozedUntil(Number.POSITIVE_INFINITY);
    setShowBudgetWarning(false);
  }, []);

  const submitSaveCheckpoint = useCallback(async (draft: { name: string; description: string }) => {
    setSaveCheckpointBusy(true);
    setSaveCheckpointDialogError(null);
    try {
      const result = await saveCheckpoint(saveCheckpointPort, {
        sessionId,
        name: draft.name.trim(),
        description: draft.description.trim() || null,
      });
      const message = t('run:checkpointDialog.status.saved', {
        name: result.name,
        step: result.transcriptStep,
      });
      setCheckpointResumeStatus({ tone: 'success', message });
      setSaveCheckpointDialogOpen(false);
      announce(message);
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      const message = t('run:checkpointDialog.status.failed', { reason: detail });
      setSaveCheckpointDialogError(message);
      setCheckpointResumeStatus({ tone: 'error', message });
      announce(message);
    } finally {
      setSaveCheckpointBusy(false);
    }
  }, [saveCheckpointPort, sessionId, t]);

  const handleCheckpointResume = useCallback(async () => {
    if (isStreaming) {
      const message = 'Finish the current run before resuming from a checkpoint.';
      setCheckpointResumeStatus({ tone: 'info', message });
      announce(message);
      return;
    }

    const opened = await openSession(sessionId);
    if (!opened) {
      const message = 'Failed to refresh the current session before resume.';
      setCheckpointResumeStatus({ tone: 'error', message });
      announce(message);
      return;
    }

    const resumePrompt = buildCheckpointResumePrompt({
      sessionId,
      sessionLabel: mission?.goal.title ?? null,
    });

    try {
      const result = await resumeFromCheckpoint(resumePort, {
        sessionId,
        message: resumePrompt,
        model: currentModel ?? null,
      });

      if (result.resumed) {
        const message = 'Resumed agent from the latest persisted checkpoint.';
        setCheckpointResumeStatus({ tone: 'success', message });
        announce(message);
        return;
      }

      const message =
        'No checkpoint was available, so a fresh resume turn was started using the prepared prompt.';
      setCheckpointResumeStatus({ tone: 'info', message });
      announce(message);
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      const copied = await copyCheckpointResumePrompt(resumePrompt);
      setResumeFallback({ prompt: resumePrompt, errorDetail: detail, clipboardCopied: copied });
      const message = copied
        ? `Resume RPC failed (${detail}). Resume prompt copied to clipboard so it can be pasted manually.`
        : `Resume RPC failed (${detail}). Use the dialog to copy the resume prompt manually.`;
      setCheckpointResumeStatus({ tone: 'error', message });
      announce(message);
    }
  }, [
    currentModel,
    isStreaming,
    mission?.goal.title,
    openSession,
    resumePort,
    sessionId,
  ]);

  const drawerOpen = (key: MissionDetailKey): boolean => selectedDetail === key;

  return (
    <section
      className="border-b border-ds-border/50 bg-ds-surface/30 px-4 py-3"
      aria-label={t('mission.header.title')}
    >
      <Card tone={error ? 'danger' : 'elevated'} className="p-ds-4">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="text-[10px] uppercase tracking-[0.22em] text-ds-muted">
                {t('mission.header.title')}
              </div>
              <div
                className="mt-1 truncate font-mono text-xs text-ds-text"
                aria-label={`${t('mission.header.session')}: ${sessionId}`}
                title={sessionId}
              >
                {sessionId}
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={toggleCollapsed}
                title={t('mission.header.collapse.shortcut')}
              >
                {collapsed
                  ? t('mission.header.collapse.expand')
                  : t('mission.header.collapse.collapse')}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => void refresh()}
              >
                {t('mission.header.refresh')}
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={() => void handleCheckpointResume()}
                disabled={!canMutate || isStreaming || openingSessionId === sessionId}
                aria-disabled={!canMutate || undefined}
                loading={openingSessionId === sessionId}
                title={
                  canMutate
                    ? 'Refresh this session from persisted history and copy a checkpoint resume prompt.'
                    : mutateBlockedTitle
                }
              >
                {openingSessionId === sessionId ? 'Preparing Resume...' : 'Resume via Chat'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  setSaveCheckpointDialogError(null);
                  setSaveCheckpointDialogOpen(true);
                }}
                disabled={!canMutate || saveCheckpointBusy}
                aria-disabled={!canMutate || undefined}
                loading={saveCheckpointBusy}
                title={
                  canMutate
                    ? 'Save a named checkpoint anchored at the current transcript step.'
                    : mutateBlockedTitle
                }
              >
                {saveCheckpointBusy
                  ? t('run:checkpointDialog.confirmBusy')
                  : t('run:checkpointDialog.confirm')}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setRerunDialogOpen(true)}
                disabled={!canMutate || !rerunParentRunId}
                aria-disabled={!canMutate || undefined}
                title={
                  !canMutate
                    ? mutateBlockedTitle
                    : rerunParentRunId
                      ? 'Pick a plan-tree node and rerun the agent anchored at that step.'
                      : 'No active run is available to rerun.'
                }
              >
                Rerun from Step
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {mission && slotSummaries ? (
              <>
                <Badge
                  compact
                  tone="neutral"
                  title={slotSummaries.stage.value}
                  aria-label={`${slotSummaries.stage.label}: ${slotSummaries.stage.value}`}
                >
                  {`${slotSummaries.stage.label}: ${mission.stage.current}/${mission.stage.total}`}
                </Badge>
                <Badge
                  compact
                  tone={getBudgetBadgeTone(budgetState)}
                  title={`${slotSummaries.budget.label}: ${slotSummaries.budget.value}`}
                  aria-label={`${slotSummaries.budget.label}: ${slotSummaries.budget.value}`}
                >
                  {slotSummaries.budget.value}
                </Badge>
                <Badge
                  compact
                  tone={getConnectionBadgeTone(connectionState)}
                  title={`${slotSummaries.connection.label}: ${slotSummaries.connection.value} ${slotSummaries.connection.meta}`}
                  aria-label={`${slotSummaries.connection.label}: ${slotSummaries.connection.value} ${slotSummaries.connection.meta}`}
                >
                  {slotSummaries.connection.meta === t('mission.header.noLatency')
                    ? slotSummaries.connection.value
                    : `${slotSummaries.connection.value} ${slotSummaries.connection.meta}`}
                </Badge>
              </>
            ) : (
              <Badge compact tone={loading ? 'info' : 'neutral'}>
                {loading ? t('mission.header.loadingContext') : stageMeta}
              </Badge>
            )}
            {loading && mission && (
              <Badge compact tone="info">{t('mission.header.loading')}</Badge>
            )}
            {error && (
              <Badge
                compact
                tone="danger"
                className="max-w-full sm:max-w-[28rem]"
                title={error}
              >
                {error}
              </Badge>
            )}
          </div>
        </div>
      </Card>

      {rerunParentRunId && (
        <RerunFromStepDialog
          parentRunId={rerunParentRunId}
          open={rerunDialogOpen}
          onClose={() => setRerunDialogOpen(false)}
        />
      )}

      <SaveCheckpointDialog
        open={saveCheckpointDialogOpen}
        busy={saveCheckpointBusy}
        error={saveCheckpointDialogError}
        onClose={() => {
          if (!saveCheckpointBusy) {
            setSaveCheckpointDialogOpen(false);
            setSaveCheckpointDialogError(null);
          }
        }}
        onSubmit={(draft) => void submitSaveCheckpoint(draft)}
      />

      <ResumePromptFallbackDialog
        open={resumeFallback !== null}
        prompt={resumeFallback?.prompt ?? ''}
        errorDetail={resumeFallback?.errorDetail ?? null}
        clipboardCopied={resumeFallback?.clipboardCopied ?? false}
        onCopy={async () => {
          if (!resumeFallback) {
            return;
          }
          const copied = await copyCheckpointResumePrompt(resumeFallback.prompt);
          setResumeFallback({ ...resumeFallback, clipboardCopied: copied });
        }}
        onClose={() => setResumeFallback(null)}
      />

      {checkpointResumeStatus && (
        <div
          className={`mt-3 text-[11px] ${
            checkpointResumeStatus.tone === 'error'
              ? 'text-rose-300'
              : checkpointResumeStatus.tone === 'success'
                ? 'text-emerald-300'
                : 'text-ds-muted'
          }`}
          role="status"
          aria-live="polite"
        >
          {checkpointResumeStatus.message}
        </div>
      )}

      {mission && slotSummaries ? (
        <>
          <div className="mt-3 grid gap-2 lg:grid-cols-3">
            <MissionSlot
              label={slotSummaries.goal.label}
              value={slotSummaries.goal.value}
              meta={slotSummaries.goal.meta}
              selected={selectedDetail === 'goal'}
              ariaLabel={getSlotAriaLabel(slotSummaries.goal.label, selectedDetail === 'goal', t)}
              controlsId={detailPanelId}
              onClick={() => toggleSelectedDetail('goal', selectedDetail, setSelectedDetail)}
            />
            {visibleSlotKeys === null && (
              <>
                <MissionSlot
                  label={slotSummaries.dataSources.label}
                  value={slotSummaries.dataSources.value}
                  meta={slotSummaries.dataSources.meta}
                  selected={selectedDetail === 'dataSources'}
                  ariaLabel={getSlotAriaLabel(slotSummaries.dataSources.label, selectedDetail === 'dataSources', t)}
                  controlsId={detailPanelId}
                  onClick={() => toggleSelectedDetail('dataSources', selectedDetail, setSelectedDetail)}
                />
                <MissionSlot
                  label={slotSummaries.deliverables.label}
                  value={slotSummaries.deliverables.value}
                  meta={slotSummaries.deliverables.meta}
                  selected={selectedDetail === 'deliverables'}
                  ariaLabel={getSlotAriaLabel(slotSummaries.deliverables.label, selectedDetail === 'deliverables', t)}
                  controlsId={detailPanelId}
                  onClick={() => toggleSelectedDetail('deliverables', selectedDetail, setSelectedDetail)}
                />
                <MissionSlot
                  label={slotSummaries.constraints.label}
                  value={slotSummaries.constraints.value}
                  meta={slotSummaries.constraints.meta}
                  selected={selectedDetail === 'constraints'}
                  ariaLabel={getSlotAriaLabel(slotSummaries.constraints.label, selectedDetail === 'constraints', t)}
                  controlsId={detailPanelId}
                  onClick={() => toggleSelectedDetail('constraints', selectedDetail, setSelectedDetail)}
                />
              </>
            )}
            <MissionSlot
              label={slotSummaries.stage.label}
              value={slotSummaries.stage.value}
              meta={slotSummaries.stage.meta}
              selected={selectedDetail === 'stage'}
              ariaLabel={getSlotAriaLabel(slotSummaries.stage.label, selectedDetail === 'stage', t)}
              controlsId={detailPanelId}
              onClick={() => toggleSelectedDetail('stage', selectedDetail, setSelectedDetail)}
            >
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ds-border/60">
                <div
                  className="h-full rounded-full bg-ds-accent transition-[width]"
                  style={{
                    width: `${Math.max(
                      0,
                      Math.min(
                        100,
                        (mission.stage.current / Math.max(1, mission.stage.total)) * 100,
                      ),
                    )}%`,
                  }}
                />
              </div>
            </MissionSlot>
            {visibleSlotKeys === null && (
              <>
                <MissionSlot
                  label={slotSummaries.mode.label}
                  value={slotSummaries.mode.value}
                  meta={slotSummaries.mode.meta}
                  selected={selectedDetail === 'mode'}
                  ariaLabel={getSlotAriaLabel(slotSummaries.mode.label, selectedDetail === 'mode', t)}
                  controlsId={detailPanelId}
                  onClick={() => toggleSelectedDetail('mode', selectedDetail, setSelectedDetail)}
                />
                <MissionSlot
                  label={slotSummaries.model.label}
                  value={slotSummaries.model.value}
                  meta={slotSummaries.model.meta}
                  selected={selectedDetail === 'model'}
                  ariaLabel={getSlotAriaLabel(slotSummaries.model.label, selectedDetail === 'model', t)}
                  controlsId={detailPanelId}
                  onClick={() => toggleSelectedDetail('model', selectedDetail, setSelectedDetail)}
                />
              </>
            )}
            <MissionSlot
              label={slotSummaries.budget.label}
              value={slotSummaries.budget.value}
              meta={slotSummaries.budget.meta}
              state={budgetState}
              selected={selectedDetail === 'budget'}
              ariaLabel={getSlotAriaLabel(slotSummaries.budget.label, selectedDetail === 'budget', t)}
              controlsId={detailPanelId}
              onClick={() => toggleSelectedDetail('budget', selectedDetail, setSelectedDetail)}
            >
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ds-border/60">
                <div
                  className={`h-full rounded-full transition-[width] ${
                    budgetState === 'error'
                      ? 'bg-rose-400'
                      : budgetState === 'warning'
                        ? 'bg-amber-400'
                        : 'bg-ds-accent'
                  }`}
                  style={{ width: `${Math.max(0, Math.min(100, budgetRatio * 100))}%` }}
                />
              </div>
            </MissionSlot>
            {visibleSlotKeys === null && (
              <div
                className="relative"
                onMouseEnter={() => setShowConnectionTooltip(true)}
                onMouseLeave={() => setShowConnectionTooltip(false)}
                onFocus={() => setShowConnectionTooltip(true)}
                onBlur={() => setShowConnectionTooltip(false)}
              >
                <MissionSlot
                  label={slotSummaries.connection.label}
                  value={slotSummaries.connection.value}
                  meta={slotSummaries.connection.meta}
                  state={
                    connectionState === 'connected'
                      ? 'default'
                      : connectionState === 'reconnecting'
                        ? 'warning'
                        : 'error'
                  }
                  selected={selectedDetail === 'connection'}
                  ariaLabel={getSlotAriaLabel(slotSummaries.connection.label, selectedDetail === 'connection', t)}
                  controlsId={detailPanelId}
                  onClick={() => toggleSelectedDetail('connection', selectedDetail, setSelectedDetail)}
                />
                {showConnectionTooltip && (
                  <div className="absolute right-0 top-full z-30 mt-2 w-64">
                    <ConnectionTooltip
                      state={connectionState}
                      latencyMs={mission.connection.latencyMs}
                    />
                  </div>
                )}
              </div>
            )}
          </div>

          <Suspense fallback={null}>
            {drawerOpen('goal') && (
              <GoalDrawer open mission={mission} onClose={closeDetailPanel} />
            )}
            {drawerOpen('dataSources') && (
              <DataSourcesDrawer open mission={mission} onClose={closeDetailPanel} />
            )}
            {drawerOpen('deliverables') && (
              <DeliverablesDrawer open mission={mission} onClose={closeDetailPanel} />
            )}
            {drawerOpen('constraints') && (
              <ConstraintsDrawer open mission={mission} onClose={closeDetailPanel} />
            )}
            {drawerOpen('stage') && (
              <StageDrawer open mission={mission} onClose={closeDetailPanel} />
            )}
            {drawerOpen('budget') && (
              <BudgetDrawer open mission={mission} onClose={closeDetailPanel} />
            )}
            {drawerOpen('mode') && (
              <div className="mt-3" id={detailPanelId} role="region" aria-label={getMissionDetailTitle('mode', t)}>
                <ModeDropdown
                  open
                  current={
                    (currentMode === 'auto' || currentMode === 'supervised' || currentMode === 'step-by-step')
                      ? currentMode
                      : 'auto'
                  }
                  onSelect={(mode) => void handleChangeMode(mode)}
                  onClose={closeDetailPanel}
                />
              </div>
            )}
            {drawerOpen('model') && (
              <div className="mt-3" id={detailPanelId} role="region" aria-label={getMissionDetailTitle('model', t)}>
                <ModelDropdown
                  open
                  current={currentModel ?? mission.model.primary}
                  options={modelOptions}
                  onSelect={(modelId) => void handleChangeModel(modelId)}
                  onClose={closeDetailPanel}
                />
              </div>
            )}
            {drawerOpen('connection') && (
              <div className="mt-3" id={detailPanelId} role="region" aria-label={getMissionDetailTitle('connection', t)}>
                <ConnectionTooltip
                  state={connectionState}
                  latencyMs={mission.connection.latencyMs}
                />
              </div>
            )}
          </Suspense>

          {showBudgetWarning && mission && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-ds-bg/70 px-4">
              <div
                ref={budgetModalRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={`${detailPanelId}-budget-warning-title`}
                aria-describedby={`${detailPanelId}-budget-warning-body`}
                className="w-full max-w-lg rounded-3xl border border-ds-border bg-ds-surface px-6 py-5 shadow-2xl"
                onKeyDown={handleBudgetWarningKeyDown}
              >
                <div
                  id={`${detailPanelId}-budget-warning-title`}
                  className="text-sm font-semibold text-ds-text"
                >
                  {budgetState === 'error'
                    ? t('mission.header.budgetAlert.errorTitle')
                    : t('mission.header.budgetAlert.warningTitle')}
                </div>
                <p
                  id={`${detailPanelId}-budget-warning-body`}
                  className="mt-2 text-sm leading-6 text-ds-muted"
                >
                  {budgetState === 'error'
                    ? t('mission.header.budgetAlert.errorBody', {
                        spend: formatBudget(
                          mission.budget.spentUsd,
                          mission.budget.limitUsd,
                          localeTag,
                        ),
                      })
                    : t('mission.header.budgetAlert.warningBody', {
                        spend: formatBudget(
                          mission.budget.spentUsd,
                          mission.budget.limitUsd,
                          localeTag,
                        ),
                      })}
                </p>
                {pauseStatus.kind === 'paused' && (
                  <p className="mt-2 text-xs text-emerald-300">
                    {t('mission.header.budgetAlert.paused')}
                  </p>
                )}
                {pauseStatus.kind === 'error' && (
                  <p className="mt-2 text-xs text-rose-300">
                    {t('mission.header.budgetAlert.pauseFailed', { reason: pauseStatus.message ?? '' })}
                  </p>
                )}
                <div className="mt-4 grid gap-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-ds-muted">
                      {t('mission.header.budgetAlert.snoozeLabel')}
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {SNOOZE_OPTIONS.map((option) => (
                        <button
                          key={option}
                          type="button"
                          onClick={() => handleSnooze(option)}
                          className="rounded-lg border border-ds-border px-2 py-1 text-[11px] text-ds-muted hover:border-ds-accent hover:text-ds-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg"
                        >
                          {t(`mission.header.budgetAlert.snooze.${option}`)}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={handleDismissForSession}
                      className="rounded-xl border border-ds-border px-3 py-2 text-sm text-ds-muted hover:border-ds-accent hover:text-ds-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg"
                    >
                      {t('mission.header.budgetAlert.dismiss')}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowBudgetWarning(false)}
                      className="rounded-xl border border-ds-border px-3 py-2 text-sm text-ds-muted hover:border-ds-accent hover:text-ds-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg"
                    >
                      {t('mission.header.budgetAlert.continue')}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedDetail('budget');
                        setShowBudgetWarning(false);
                      }}
                      className="rounded-xl border border-ds-border px-3 py-2 text-sm text-ds-text hover:border-ds-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg"
                    >
                      {t('mission.header.budgetAlert.review')}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handlePauseAgent()}
                      disabled={pauseStatus.kind === 'pending'}
                      className="rounded-xl border border-ds-accent bg-ds-accent/10 px-3 py-2 text-sm font-medium text-ds-accent hover:bg-ds-accent/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg disabled:opacity-50"
                    >
                      {t('mission.header.budgetAlert.pause')}
                    </button>
                    {onAbort && (
                      <button
                        type="button"
                        onClick={() => {
                          onAbort?.();
                          setShowBudgetWarning(false);
                        }}
                        className="rounded-xl bg-rose-500 px-3 py-2 text-sm font-medium text-white hover:bg-rose-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg"
                      >
                        {t('mission.header.budgetAlert.abort')}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      ) : (
        <Card className="mt-3 p-ds-4 text-sm text-ds-muted">
          {loading ? t('mission.header.loadingContext') : stageMeta}
        </Card>
      )}
    </section>
  );
}

function getSlotAriaLabel(label: string, selected: boolean, t: TranslateFn): string {
  return `${label}. ${
    selected ? t('mission.header.slot.collapse') : t('mission.header.slot.expand')
  }`;
}

function getMissionDetailTitle(detail: MissionDetailKey, t: TranslateFn): string {
  return t(DETAIL_TITLE_KEYS[detail]);
}

function toggleSelectedDetail(
  next: MissionDetailKey,
  current: MissionDetailKey | null,
  setSelectedDetail: (value: MissionDetailKey | null) => void,
): void {
  setSelectedDetail(current === next ? null : next);
}

function formatDataSourceSummary(
  mission: MissionContext,
  t: TranslateFn,
): string {
  if (mission.dataSources.length === 0) {
    return t('mission.header.noSources');
  }
  if (mission.dataSources.length === 1) {
    return mission.dataSources[0].label;
  }
  return t('mission.header.sourceCount', {
    count: mission.dataSources.length,
  });
}

function formatConstraintSummary(
  mission: MissionContext,
  t: TranslateFn,
): string {
  const parts = [mission.constraints.language.toUpperCase()];
  parts.push(
    mission.constraints.requiresApproval
      ? t('mission.header.constraint.approvalOn')
      : t('mission.header.constraint.approvalOff'),
  );
  if (mission.constraints.localOnlyModel) {
    parts.push(t('mission.header.constraint.localModel'));
  }
  return parts.join(' / ');
}

function formatBudget(spentUsd: number, limitUsd: number, localeTag: string): string {
  return `${formatUsd(spentUsd, localeTag)} / ${formatUsd(limitUsd, localeTag)}`;
}

function formatUsd(value: number, localeTag: string): string {
  return new Intl.NumberFormat(localeTag, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)}m`;
  }
  return `${(seconds / 3600).toFixed(1)}h`;
}

function formatConnectionState(
  state: MissionContext['connection']['state'],
  t: TranslateFn,
): string {
  switch (state) {
    case 'connected':
      return t('mission.header.connection.connected');
    case 'reconnecting':
      return t('mission.header.connection.reconnecting');
    case 'disconnected':
      return t('mission.header.connection.disconnected');
    default:
      return state;
  }
}

function formatMissionModeLabel(mode: string, t: TranslateFn): string {
  switch (mode) {
    case 'auto':
      return t('mode.auto');
    case 'supervised':
      return t('mode.supervised');
    case 'step-by-step':
      return t('mode.step');
    default:
      return formatMissionMode(mode);
  }
}

function getBudgetBadgeTone(
  state: MissionBudgetState,
): 'accent' | 'warning' | 'danger' {
  switch (state) {
    case 'warning':
      return 'warning';
    case 'error':
      return 'danger';
    default:
      return 'accent';
  }
}

function getConnectionBadgeTone(
  state: MissionContext['connection']['state'],
): 'success' | 'warning' | 'danger' {
  switch (state) {
    case 'connected':
      return 'success';
    case 'reconnecting':
      return 'warning';
    case 'disconnected':
    default:
      return 'danger';
  }
}

function loadMissionHeaderCollapsed(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  try {
    return window.localStorage.getItem(MISSION_HEADER_COLLAPSE_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function saveMissionHeaderCollapsed(collapsed: boolean): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(MISSION_HEADER_COLLAPSE_STORAGE_KEY, collapsed ? '1' : '0');
  } catch {
    // Ignore storage failures and keep the in-memory state.
  }
}

function loadSnoozeStorage(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    return window.localStorage.getItem(MISSION_BUDGET_SNOOZE_KEY);
  } catch {
    return null;
  }
}

function saveSnoozeStorage(value: string | null): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    if (value === null) {
      window.localStorage.removeItem(MISSION_BUDGET_SNOOZE_KEY);
    } else {
      window.localStorage.setItem(MISSION_BUDGET_SNOOZE_KEY, value);
    }
  } catch {
    // Ignore storage failures.
  }
}

// Helper retained to satisfy unused-import detection in agentStore wrap typings.
void applyMissionPatch;
void deriveMissionBudgetState;
