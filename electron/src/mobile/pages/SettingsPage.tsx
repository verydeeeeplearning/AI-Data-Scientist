import type { ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import { useWs } from '../../renderer/hooks/WsProvider';
import { useConfigStore } from '../../renderer/stores/configStore';
import { useRuntimeStore } from '../../renderer/stores/runtimeStore';
import { PushOptInCard } from '../components/PushOptInCard';
import { describeMobileConnection } from '../runtime';

function formatEpoch(seconds?: number | null): string {
  if (!seconds) {
    return '-';
  }
  return new Date(seconds * 1000).toLocaleString();
}

export function SettingsPage(): ReactElement {
  const { t } = useTranslation('mobile');
  const { status, disconnectReason } = useWs();
  const locale = useConfigStore((state) => state.theme);
  const sessions = useRuntimeStore((state) => state.sessions.slice(0, 5));
  const connection = describeMobileConnection(status, disconnectReason);

  return (
    <div className="flex flex-col gap-3 p-4">
      <h1 className="text-lg font-semibold text-ds-text">
        {t('nav.settings')}
      </h1>
      <p className="text-sm text-ds-muted">{t('settings.description')}</p>

      <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ds-text">{t('settings.connection.title')}</h2>
            <p className="mt-1 text-xs leading-5 text-ds-muted">
              {t('settings.connection.description')}
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
        <h2 className="text-sm font-semibold text-ds-text">{t('settings.sessions.title')}</h2>
        <div className="mt-4 space-y-3">
          {sessions.length === 0 ? (
            <div className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3 text-sm text-ds-muted">
              {t('settings.sessions.empty')}
            </div>
          ) : (
            sessions.map((session) => (
              <article
                key={session.sessionId}
                className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3"
              >
                <div className="text-sm font-medium text-ds-text">
                  {session.sessionLabel || session.sessionId}
                </div>
                <div className="mt-1 text-xs text-ds-muted">{session.surface}</div>
                <div className="mt-2 text-xs text-ds-muted">
                  {t('settings.sessions.updated')}: {formatEpoch(session.lastActive)}
                </div>
              </article>
            ))
          )}
        </div>
      </section>

      <PushOptInCard />

      <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
        <h2 className="text-sm font-semibold text-ds-text">{t('settings.device.title')}</h2>
        <div className="mt-4 rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3">
          <div className="text-[11px] uppercase tracking-[0.16em] text-ds-muted">
            {t('settings.device.theme')}
          </div>
          <div className="mt-2 text-sm font-medium text-ds-text">{locale}</div>
        </div>
      </section>
    </div>
  );
}
