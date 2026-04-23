import type { ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import { useWs } from '../../renderer/hooks/WsProvider';
import { useAgentStore } from '../../renderer/stores/agentStore';
import { useRuntimeStore } from '../../renderer/stores/runtimeStore';
import { useWorkflowStore } from '../../renderer/stores/workflowStore';
import { describeMobileConnection } from '../runtime';

export function MissionPage(): ReactElement {
  const { t } = useTranslation('mobile');
  const { status, disconnectReason } = useWs();
  const { model, mode } = useAgentStore((state) => ({
    model: state.model,
    mode: state.mode,
  }));
  const runtimeStatus = useRuntimeStore((state) => state.status);
  const pendingApprovals = useWorkflowStore(
    (state) => state.approvals.filter((approval) => approval.status === 'pending').length,
  );
  const connection = describeMobileConnection(status, disconnectReason);
  const stats = [
    {
      label: t('mission.stat.sessions'),
      value: String(runtimeStatus?.activeSessions ?? 0),
    },
    {
      label: t('mission.stat.runs'),
      value: String(runtimeStatus?.activeRuns ?? 0),
    },
    {
      label: t('mission.stat.tasks'),
      value: String(runtimeStatus?.activeTasks ?? 0),
    },
    {
      label: t('mission.stat.approvals'),
      value: String(pendingApprovals),
    },
  ];

  return (
    <div className="flex flex-col gap-3 p-4">
      <h1 className="text-lg font-semibold text-ds-text">
        {t('nav.mission')}
      </h1>
      <span className="text-xs text-ds-muted">{t('status.readOnly')}</span>
      <p className="text-sm text-ds-muted">{t('mission.description')}</p>

      <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ds-text">
              {t('mission.connection.title')}
            </h2>
            <p className="mt-1 text-xs leading-5 text-ds-muted">
              {t('mission.connection.description')}
            </p>
          </div>
          <span
            className={`rounded-full px-2 py-1 text-[11px] font-medium ${
              connection.tone === 'success'
                ? 'bg-emerald-500/10 text-emerald-300'
                : connection.tone === 'warning'
                  ? 'bg-amber-500/10 text-amber-200'
                  : 'bg-rose-500/10 text-rose-200'
            }`}
          >
            {t(connection.labelKey)}
          </span>
        </div>
        <p className="mt-3 text-sm text-ds-text">{t(connection.detailKey)}</p>
      </section>

      <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
        <h2 className="text-sm font-semibold text-ds-text">
          {t('mission.runtimeSummary.title')}
        </h2>
        <p className="mt-1 text-xs leading-5 text-ds-muted">
          {t('mission.runtimeSummary.description')}
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3">
          {stats.map((item) => (
            <div key={item.label} className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3">
              <div className="text-[11px] uppercase tracking-[0.16em] text-ds-muted">
                {item.label}
              </div>
              <div className="mt-2 text-lg font-semibold text-ds-text">{item.value}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
        <h2 className="text-sm font-semibold text-ds-text">{t('mission.session.title')}</h2>
        <div className="mt-4 space-y-3">
          <div className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3">
            <div className="text-[11px] uppercase tracking-[0.16em] text-ds-muted">
              {t('mission.stat.model')}
            </div>
            <div className="mt-2 text-sm font-medium text-ds-text">{model || t('common.none')}</div>
          </div>
          <div className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3">
            <div className="text-[11px] uppercase tracking-[0.16em] text-ds-muted">
              {t('mission.stat.mode')}
            </div>
            <div className="mt-2 text-sm font-medium text-ds-text">{mode || t('common.none')}</div>
          </div>
        </div>
      </section>
    </div>
  );
}
