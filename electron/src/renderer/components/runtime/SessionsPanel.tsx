/**
 * Runtime sessions panel.
 */

import { Clock3, ExternalLink } from 'lucide-react';
import { useI18n } from '../../stores/i18nStore';
import { useSessionHistory } from '../../hooks/useSessionHistory';
import { useRuntimeEventStore } from '../../stores/runtimeEventStore';
import { useRuntimeStore } from '../../stores/runtimeStore';
import { formatRuntimeRelativeAge } from './runtimeI18n';

export function SessionsPanel() {
  const { t } = useI18n();
  const sessions = useRuntimeStore((s) => s.sessions);
  const events = useRuntimeEventStore((s) => s.events);
  const { currentSessionId, openingSessionId, openSession } = useSessionHistory();

  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2 text-[10px] font-semibold text-ds-muted uppercase tracking-wider mb-2">
        <Clock3 size={12} />
        {t('run.runtime.sessions.title')}
        <span className="ml-auto text-ds-text normal-case text-xs">{sessions.length}</span>
      </div>

      {sessions.length === 0 ? (
        <div className="text-xs text-ds-muted">{t('run.runtime.sessions.empty')}</div>
      ) : (
        <div className="space-y-2">
          {sessions.map((session) => (
            <SessionCard
              key={session.sessionId}
              t={t}
              session={session}
              currentSessionId={currentSessionId}
              openingSessionId={openingSessionId}
              openSession={openSession}
              recentAlertCount={events.filter((event) => (
                event.sessionId === session.sessionId
                && ((Date.now() / 1000) - event.createdAt) <= 3600
              )).length}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SessionCard({
  t,
  session,
  currentSessionId,
  openingSessionId,
  openSession,
  recentAlertCount,
}: {
  t: (key: string, vars?: Record<string, string | number | undefined | null>) => string;
  session: {
    sessionId: string;
    sessionLabel?: string | null;
    threadLabel?: string | null;
    surface: string;
    lastActive: number;
    lastRunId?: string | null;
  };
  currentSessionId: string | null;
  openingSessionId: string | null;
  openSession: (sessionId: string) => Promise<boolean>;
  recentAlertCount: number;
}) {
  const sessionLabel = session.sessionLabel || session.sessionId;

  return (
    <div
      className={`rounded-md border p-2 ${
        currentSessionId === session.sessionId
          ? 'border-ds-accent bg-ds-bg/90'
          : 'border-ds-border bg-ds-bg/70'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs text-ds-text font-mono truncate">{sessionLabel}</div>
          {session.threadLabel && (
            <div className="mt-0.5 text-[10px] text-ds-muted uppercase">
              {session.threadLabel}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {recentAlertCount > 0 && (
            <span className="rounded-full bg-ds-warning/15 px-1.5 py-0.5 text-[10px] text-ds-warning">
              {recentAlertCount === 1
                ? t('run.runtime.sessions.alertCount.one', { count: recentAlertCount })
                : t('run.runtime.sessions.alertCount.other', { count: recentAlertCount })}
            </span>
          )}
          <div className="text-[10px] uppercase text-ds-muted">{session.surface}</div>
        </div>
      </div>
      <div className="mt-1 text-[10px] text-ds-muted">
        {t('run.runtime.sessions.lastActive', {
          value: formatRuntimeRelativeAge(t, session.lastActive),
        })}
      </div>
      {session.lastRunId && (
        <div className="mt-1 text-[10px] font-mono text-ds-muted truncate">
          {t('run.runtime.sessions.lastRun', { runId: session.lastRunId })}
        </div>
      )}
      <div className="mt-2 flex items-center gap-2">
        <button
          onClick={() => void openSession(session.sessionId)}
          data-testid={`open-session-${session.sessionId}`}
          disabled={openingSessionId === session.sessionId}
          className="inline-flex items-center gap-1 rounded border border-ds-border px-2 py-1 text-[10px] text-ds-muted hover:text-ds-text disabled:opacity-50"
        >
          <ExternalLink size={10} />
          {openingSessionId === session.sessionId
            ? t('run.runtime.sessions.action.opening')
            : currentSessionId === session.sessionId
              ? t('run.runtime.sessions.action.opened')
              : t('run.runtime.sessions.action.open')}
        </button>
      </div>
    </div>
  );
}
