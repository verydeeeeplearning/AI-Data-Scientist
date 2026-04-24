/**
 * Timeline panel for runtime alerts, recovery, and policy decisions.
 */

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  ShieldAlert,
  Siren,
  ActivitySquare,
} from 'lucide-react';
import { useMemo } from 'react';
import { useSessionHistory } from '../../hooks/useSessionHistory';
import { useI18n } from '../../stores/i18nStore';
import { useRuntimeEventStore, type RuntimeEventEntry } from '../../stores/runtimeEventStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import {
  formatRuntimeRelativeAge,
  translateRuntimeEventCategory,
} from './runtimeI18n';

function eventIcon(event: RuntimeEventEntry) {
  if (event.category === 'recovery') return Clock3;
  if (event.category === 'approval') return ShieldAlert;
  if (event.category === 'pressure') return Siren;
  if (event.category === 'health') return AlertTriangle;
  return ActivitySquare;
}

function severityClasses(severity: RuntimeEventEntry['severity']): string {
  if (severity === 'error') return 'text-ds-error border-ds-error/30 bg-ds-error/10';
  if (severity === 'warning') return 'text-ds-warning border-ds-warning/30 bg-ds-warning/10';
  if (severity === 'success') return 'text-ds-success border-ds-success/30 bg-ds-success/10';
  return 'text-ds-muted border-ds-border bg-ds-bg/70';
}

export function RuntimeAlertsPanel() {
  const { t } = useI18n();
  const events = useRuntimeEventStore((s) => s.events);
  const lastUpdatedAt = useRuntimeEventStore((s) => s.lastUpdatedAt);
  const selectRun = useRuntimeStore((s) => s.selectRun);
  const { currentSessionId, openingSessionId, openSession } = useSessionHistory();

  const summary = useMemo(() => {
    const latest = events.slice(0, 12);
    return {
      warnings: latest.filter((event) => event.severity === 'warning' || event.severity === 'error').length,
      recoveries: latest.filter((event) => event.category === 'recovery').length,
      approvals: latest.filter((event) => event.category === 'approval').length,
    };
  }, [events]);

  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2 text-[10px] font-semibold text-ds-muted uppercase tracking-wider mb-2">
        <AlertTriangle size={12} />
        {t('run.runtime.alerts.title')}
        <span className="ml-auto text-ds-text normal-case text-xs">{events.length}</span>
      </div>

      <div className="mb-2 grid grid-cols-3 gap-2 text-[10px]">
        <div className="rounded border border-ds-border bg-ds-bg/70 px-2 py-1.5">
          <div className="text-ds-muted">{t('run.runtime.alerts.summary.warnings')}</div>
          <div className="mt-1 font-mono text-ds-text">{summary.warnings}</div>
        </div>
        <div className="rounded border border-ds-border bg-ds-bg/70 px-2 py-1.5">
          <div className="text-ds-muted">{t('run.runtime.alerts.summary.recoveries')}</div>
          <div className="mt-1 font-mono text-ds-text">{summary.recoveries}</div>
        </div>
        <div className="rounded border border-ds-border bg-ds-bg/70 px-2 py-1.5">
          <div className="text-ds-muted">{t('run.runtime.alerts.summary.approvals')}</div>
          <div className="mt-1 font-mono text-ds-text">{summary.approvals}</div>
        </div>
      </div>

      {events.length === 0 ? (
        <div className="text-xs text-ds-muted">{t('run.runtime.alerts.empty')}</div>
      ) : (
        <div className="space-y-2">
          {events.slice(0, 24).map((event) => {
            const Icon = eventIcon(event);
            const selectedSession = event.sessionId && currentSessionId === event.sessionId;

            return (
              <div
                key={event.eventId}
                className={`rounded-md border p-2 ${severityClasses(event.severity)}`}
              >
                <div className="flex items-start gap-2">
                  <Icon size={12} className="mt-0.5 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase tracking-wider">
                        {translateRuntimeEventCategory(event.category, t)}
                      </span>
                      <span className="text-[10px] opacity-80">
                        {formatRuntimeRelativeAge(t, event.createdAt)}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-ds-text">{event.message}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-ds-muted">
                      <span>{event.kind}</span>
                      {event.source && <span>{event.source}</span>}
                      {event.surface && <span>{event.surface}</span>}
                      {event.sessionId && (
                        <span className={selectedSession ? 'text-ds-accent font-medium' : ''}>
                          {event.sessionId}
                        </span>
                      )}
                      {event.runId && <span className="font-mono truncate max-w-28">{event.runId}</span>}
                    </div>

                    {(event.sessionId || event.runId) && (
                      <div className="mt-2 flex items-center gap-2">
                        {event.sessionId && (
                          <button
                            onClick={() => void openSession(event.sessionId!)}
                            disabled={openingSessionId === event.sessionId}
                            className="inline-flex items-center gap-1 rounded border border-ds-border px-2 py-1 text-[10px] text-ds-muted hover:text-ds-text disabled:opacity-50"
                          >
                            <ExternalLink size={10} />
                            {openingSessionId === event.sessionId
                              ? t('run.runtime.sessions.action.opening')
                              : selectedSession
                                ? t('run.runtime.sessions.action.opened')
                                : t('run.runtime.sessions.action.open')}
                          </button>
                        )}
                        {event.runId && (
                          <button
                            onClick={() => selectRun(event.runId!)}
                            className="inline-flex items-center gap-1 rounded border border-ds-border px-2 py-1 text-[10px] text-ds-muted hover:text-ds-text"
                          >
                            <CheckCircle2 size={10} />
                            {t('run.runtime.runs.action.inspect')}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {lastUpdatedAt && (
        <div className="mt-2 text-[10px] text-ds-muted">
          {t('run.runtime.alerts.synced', {
            time: new Date(lastUpdatedAt).toLocaleTimeString(),
          })}
        </div>
      )}
    </div>
  );
}
