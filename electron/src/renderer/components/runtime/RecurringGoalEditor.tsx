/**
 * Inline editor for creating or updating recurring autonomous goals.
 */

import { useEffect, useMemo, useState } from 'react';
import type { RecurringGoalEntry } from '../../stores/policyStore';

type EditorValues = {
  goalId?: string;
  sessionId: string;
  prompt: string;
  intervalSeconds: number;
  enabled: boolean;
};

interface Props {
  initialGoal?: RecurringGoalEntry | null;
  busy?: boolean;
  onSubmit: (values: EditorValues) => Promise<void>;
  onCancel?: () => void;
}

type IntervalUnit = 'minutes' | 'hours' | 'days';

function inferIntervalUnit(intervalSeconds: number): IntervalUnit {
  if (intervalSeconds % 86400 === 0) return 'days';
  if (intervalSeconds % 3600 === 0) return 'hours';
  return 'minutes';
}

function toUnitValue(intervalSeconds: number, unit: IntervalUnit): number {
  if (unit === 'days') return intervalSeconds / 86400;
  if (unit === 'hours') return intervalSeconds / 3600;
  return intervalSeconds / 60;
}

function fromUnitValue(value: number, unit: IntervalUnit): number {
  if (unit === 'days') return value * 86400;
  if (unit === 'hours') return value * 3600;
  return value * 60;
}

export function RecurringGoalEditor({ initialGoal, busy = false, onSubmit, onCancel }: Props) {
  const inferredUnit = useMemo(
    () => inferIntervalUnit(initialGoal?.intervalSeconds ?? 3600),
    [initialGoal?.intervalSeconds],
  );
  const [sessionId, setSessionId] = useState(initialGoal?.sessionId ?? '');
  const [prompt, setPrompt] = useState(initialGoal?.prompt ?? '');
  const [enabled, setEnabled] = useState(initialGoal?.enabled ?? true);
  const [intervalUnit, setIntervalUnit] = useState<IntervalUnit>(inferredUnit);
  const [intervalValue, setIntervalValue] = useState(
    Math.max(1, toUnitValue(initialGoal?.intervalSeconds ?? 3600, inferredUnit)),
  );
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    const nextUnit = inferIntervalUnit(initialGoal?.intervalSeconds ?? 3600);
    setSessionId(initialGoal?.sessionId ?? '');
    setPrompt(initialGoal?.prompt ?? '');
    setEnabled(initialGoal?.enabled ?? true);
    setIntervalUnit(nextUnit);
    setIntervalValue(Math.max(1, toUnitValue(initialGoal?.intervalSeconds ?? 3600, nextUnit)));
    setValidationError(null);
  }, [initialGoal]);

  const submit = async () => {
    const normalizedSession = sessionId.trim();
    const normalizedPrompt = prompt.trim();
    if (!normalizedSession) {
      setValidationError('Session to wake is required.');
      return;
    }
    if (!normalizedPrompt) {
      setValidationError('Recurring prompt is required.');
      return;
    }
    if (!Number.isFinite(intervalValue) || intervalValue <= 0) {
      setValidationError('Interval must be greater than zero.');
      return;
    }
    setValidationError(null);
    await onSubmit({
      goalId: initialGoal?.goalId,
      sessionId: normalizedSession,
      prompt: normalizedPrompt,
      intervalSeconds: fromUnitValue(intervalValue, intervalUnit),
      enabled,
    });
  };

  return (
    <div className="rounded border border-ds-border/70 bg-ds-surface/60 px-2 py-2 space-y-2">
      <div className="grid grid-cols-1 gap-2">
        <label className="space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-ds-muted">Session To Wake</div>
          <input
            value={sessionId}
            onChange={(event) => setSessionId(event.target.value)}
            placeholder="autonomous:inbox or project session id"
            className="w-full rounded border border-ds-border bg-ds-bg px-2 py-1.5 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
          />
        </label>

        <label className="space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-ds-muted">Recurring Prompt</div>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={3}
            placeholder="Describe the recurring autonomous check to perform."
            className="w-full resize-none rounded border border-ds-border bg-ds-bg px-2 py-1.5 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
          />
        </label>

        <div className="grid grid-cols-[1fr_auto] gap-2">
          <label className="space-y-1">
            <div className="text-[10px] uppercase tracking-wider text-ds-muted">Interval</div>
            <input
              type="number"
              min={1}
              step={1}
              value={intervalValue}
              onChange={(event) => setIntervalValue(Number(event.target.value))}
              className="w-full rounded border border-ds-border bg-ds-bg px-2 py-1.5 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
            />
          </label>

          <label className="space-y-1">
            <div className="text-[10px] uppercase tracking-wider text-ds-muted">Unit</div>
            <select
              value={intervalUnit}
              onChange={(event) => setIntervalUnit(event.target.value as IntervalUnit)}
              className="rounded border border-ds-border bg-ds-bg px-2 py-1.5 text-xs text-ds-text focus:border-ds-accent focus:outline-none"
            >
              <option value="minutes">Minutes</option>
              <option value="hours">Hours</option>
              <option value="days">Days</option>
            </select>
          </label>
        </div>

        <label className="flex items-center gap-2 text-xs text-ds-text">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
            className="accent-[var(--ds-accent)]"
          />
          Enabled
        </label>
      </div>

      {validationError && <div className="text-xs text-ds-error">{validationError}</div>}

      <div className="flex items-center gap-2">
        <button
          onClick={() => void submit()}
          disabled={busy}
          className="rounded bg-ds-accent px-2 py-1.5 text-xs text-white disabled:opacity-50"
        >
          {initialGoal ? 'Save goal' : 'Create goal'}
        </button>
        {onCancel && (
          <button
            onClick={onCancel}
            disabled={busy}
            className="rounded border border-ds-border px-2 py-1.5 text-xs text-ds-muted hover:text-ds-text disabled:opacity-50"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
