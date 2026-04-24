/**
 * Editable recurring-goal list for autonomous policy control.
 */

import { Clock3, Pencil, Plus, RefreshCw } from 'lucide-react';
import { useId, useState } from 'react';
import { Badge, Button, Card } from '../../design-system/primitives';
import { useWs } from '../../hooks/WsProvider';
import { fetchPolicySnapshot } from '../../hooks/usePolicy';
import { useI18n } from '../../stores/i18nStore';
import { usePolicyStore, type RecurringGoalEntry } from '../../stores/policyStore';
import { RecurringGoalEditor } from './RecurringGoalEditor';
import { formatRuntimeIntervalShort } from './runtimeI18n';

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

function formatLastTriggered(
  timestamp: number | null | undefined,
  t: (key: string) => string,
): string {
  if (!timestamp) return t('run.runtime.policy.recurringGoals.never');
  return new Date(timestamp * 1000).toLocaleString();
}

export function RecurringGoalsPanel() {
  const { t } = useI18n();
  const headingId = useId();
  const editorRegionId = `${headingId}-editor`;
  const { rpc } = useWs();
  const snapshot = usePolicyStore((s) => s.snapshot);
  const setSnapshot = usePolicyStore((s) => s.setSnapshot);
  const markUpdated = usePolicyStore((s) => s.markUpdated);
  const recurringGoals = snapshot?.recurringGoals ?? [];
  const [showCreate, setShowCreate] = useState(false);
  const [editingGoalId, setEditingGoalId] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const refresh = async () => {
    setSnapshot(await fetchPolicySnapshot(rpc));
    markUpdated();
  };

  const persistGoal = async (values: {
    goalId?: string;
    sessionId: string;
    prompt: string;
    intervalSeconds: number;
    enabled: boolean;
  }) => {
    setSaveState('saving');
    setErrorMessage(null);
    try {
      await rpc('policy.upsertRecurringGoal', {
        goalId: values.goalId,
        sessionId: values.sessionId,
        prompt: values.prompt,
        intervalSeconds: values.intervalSeconds,
        enabled: values.enabled,
      });
      await refresh();
      setSaveState('saved');
      setShowCreate(false);
      setEditingGoalId(null);
    } catch (err) {
      setSaveState('error');
      setErrorMessage((err as Error)?.message ?? t('run.runtime.policy.recurringGoals.errorSave'));
    }
  };

  const toggleGoal = async (goal: RecurringGoalEntry) => {
    await persistGoal({
      goalId: goal.goalId,
      sessionId: goal.sessionId,
      prompt: goal.prompt,
      intervalSeconds: goal.intervalSeconds,
      enabled: !goal.enabled,
    });
  };

  return (
    <section aria-labelledby={headingId}>
      <Card className="space-y-4 bg-ds-bg/60" aria-busy={saveState === 'saving'}>
        <header className="flex flex-wrap items-center gap-2">
          <div
            id={headingId}
            className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-ds-muted"
          >
            <Clock3 size={12} aria-hidden="true" />
            {t('run.runtime.policy.recurringGoals.title')}
          </div>
          <Badge compact>{recurringGoals.length}</Badge>
          <Button
            onClick={() => {
              setEditingGoalId(null);
              setShowCreate((value) => !value);
              setSaveState('idle');
              setErrorMessage(null);
            }}
            variant={showCreate ? 'ghost' : 'secondary'}
            size="sm"
            leadingIcon={<Plus size={14} aria-hidden="true" />}
            className="ml-auto"
            aria-expanded={showCreate}
            aria-controls={editorRegionId}
          >
            {showCreate
              ? t('run.runtime.policy.recurringGoals.action.close')
              : t('run.runtime.policy.recurringGoals.action.add')}
          </Button>
        </header>

        {showCreate ? (
          <div id={editorRegionId}>
            <RecurringGoalEditor
              busy={saveState === 'saving'}
              onSubmit={persistGoal}
              onCancel={() => {
                setShowCreate(false);
                setSaveState('idle');
                setErrorMessage(null);
              }}
            />
          </div>
        ) : null}

        {errorMessage ? (
          <p role="alert" className="text-xs text-ds-error">
            {errorMessage}
          </p>
        ) : null}
        {saveState === 'saved' ? (
          <p role="status" className="text-xs text-ds-success">
            {t('run.runtime.policy.recurringGoals.saved')}
          </p>
        ) : null}

        {recurringGoals.length === 0 ? (
          <Card className="bg-ds-surface/60 text-sm text-ds-muted">
            {t('run.runtime.policy.recurringGoals.empty')}
          </Card>
        ) : (
          <ul
            className="space-y-3 list-none p-0"
            aria-label={t('run.runtime.policy.recurringGoals.listAria')}
          >
            {recurringGoals.map((goal) => (
              <li key={goal.goalId}>
                {editingGoalId === goal.goalId ? (
                  <div id={editorRegionId}>
                    <RecurringGoalEditor
                      initialGoal={goal}
                      busy={saveState === 'saving'}
                      onSubmit={persistGoal}
                      onCancel={() => {
                        setEditingGoalId(null);
                        setSaveState('idle');
                        setErrorMessage(null);
                      }}
                    />
                  </div>
                ) : (
                  <Card className="space-y-3 bg-ds-surface/60">
                    <div className="flex flex-wrap items-start gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="line-clamp-2 text-sm text-ds-text">{goal.prompt}</p>
                      </div>
                      <Badge
                        tone={goal.enabled ? 'success' : 'neutral'}
                        compact
                        className="uppercase tracking-[0.16em]"
                      >
                        {goal.enabled
                          ? t('run.runtime.policy.recurringGoals.state.enabled')
                          : t('run.runtime.policy.recurringGoals.state.disabled')}
                      </Badge>
                    </div>

                    <dl className="grid gap-3 sm:grid-cols-3">
                      <GoalMetaItem label={t('run.runtime.policy.recurringGoals.meta.session')}>
                        {goal.sessionId}
                      </GoalMetaItem>
                      <GoalMetaItem label={t('run.runtime.policy.recurringGoals.meta.interval')}>
                        {formatRuntimeIntervalShort(t, goal.intervalSeconds)}
                      </GoalMetaItem>
                      <GoalMetaItem label={t('run.runtime.policy.recurringGoals.meta.lastTrigger')}>
                        {formatLastTriggered(goal.lastTriggeredAt, t)}
                      </GoalMetaItem>
                    </dl>

                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        onClick={() => {
                          setEditingGoalId(goal.goalId);
                          setShowCreate(false);
                          setSaveState('idle');
                          setErrorMessage(null);
                        }}
                        variant="secondary"
                        size="sm"
                        leadingIcon={<Pencil size={14} aria-hidden="true" />}
                      >
                        {t('run.runtime.policy.recurringGoals.action.edit')}
                      </Button>
                      <Button
                        onClick={() => void toggleGoal(goal)}
                        disabled={saveState === 'saving'}
                        variant="ghost"
                        size="sm"
                        leadingIcon={<RefreshCw size={14} aria-hidden="true" />}
                      >
                        {goal.enabled
                          ? t('run.runtime.policy.recurringGoals.action.disable')
                          : t('run.runtime.policy.recurringGoals.action.enable')}
                      </Button>
                    </div>
                  </Card>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}

function GoalMetaItem({ label, children }: { label: string; children: string }) {
  return (
    <div className="rounded-xl border border-ds-border/70 bg-ds-bg/70 px-3 py-2">
      <dt className="text-[10px] uppercase tracking-[0.16em] text-ds-muted">{label}</dt>
      <dd className="mt-1 text-xs text-ds-text break-all">{children}</dd>
    </div>
  );
}
