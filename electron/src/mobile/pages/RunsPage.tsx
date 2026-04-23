import type { ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import { useRuntimeStore } from '../../renderer/stores/runtimeStore';

function formatEpoch(seconds?: number | null): string {
  if (!seconds) {
    return '-';
  }
  return new Date(seconds * 1000).toLocaleString();
}

export function RunsPage(): ReactElement {
  const { t } = useTranslation('mobile');
  const runs = useRuntimeStore((state) => state.runs.slice(0, 5));
  const tasks = useRuntimeStore((state) => state.tasks.slice(0, 5));

  return (
    <div className="flex flex-col gap-3 p-4">
      <h1 className="text-lg font-semibold text-ds-text">
        {t('nav.runs')}
      </h1>
      <span className="text-xs text-ds-muted">{t('status.readOnly')}</span>
      <p className="text-sm text-ds-muted">{t('runs.description')}</p>

      <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
        <h2 className="text-sm font-semibold text-ds-text">{t('runs.list.title')}</h2>
        <div className="mt-4 space-y-3">
          {runs.length === 0 ? (
            <div className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3 text-sm text-ds-muted">
              {t('runs.list.empty')}
            </div>
          ) : (
            runs.map((run) => (
              <article
                key={run.runId}
                className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ds-text">{run.runId}</div>
                    <div className="mt-1 text-xs text-ds-muted">
                      {run.sessionLabel || run.sessionId}
                    </div>
                  </div>
                  <span className="rounded-full bg-ds-accent/10 px-2 py-1 text-[11px] text-ds-accent">
                    {run.status}
                  </span>
                </div>
                <div className="mt-3 text-sm text-ds-text">{run.message}</div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-ds-muted">
                  <span>{t('runs.field.started')}: {formatEpoch(run.startedAt)}</span>
                  <span>{t('runs.field.cost')}: ${run.costUsd.toFixed(2)}</span>
                </div>
              </article>
            ))
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
        <h2 className="text-sm font-semibold text-ds-text">{t('runs.tasks.title')}</h2>
        <div className="mt-4 space-y-3">
          {tasks.length === 0 ? (
            <div className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3 text-sm text-ds-muted">
              {t('runs.tasks.empty')}
            </div>
          ) : (
            tasks.map((task) => (
              <article
                key={task.taskId}
                className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-ds-text">{task.taskId}</div>
                    <div className="mt-1 text-xs text-ds-muted">
                      {t('runs.tasks.runId')}: {task.runId}
                    </div>
                  </div>
                  <span className="rounded-full bg-ds-surface px-2 py-1 text-[11px] text-ds-muted">
                    {task.status}
                  </span>
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
