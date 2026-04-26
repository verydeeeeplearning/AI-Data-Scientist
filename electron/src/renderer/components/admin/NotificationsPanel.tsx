import type { ReactElement } from 'react';
import { Hash, Mail, MessageCircle } from 'lucide-react';

import { TelegramConnectFlow } from '../settings/telegram/TelegramConnectFlow';
import { TelegramNotificationSettings } from '../settings/TelegramNotificationSettings';
import { useI18n } from '../../stores/i18nStore';
import { useTelegramStore } from '../../stores/telegramStore';
import type { RpcFn } from '../settings/types';

export function NotificationsPanel({ rpc }: { readonly rpc: RpcFn }): ReactElement {
  const { t } = useI18n();
  const telegramStatus = useTelegramStore((state) => state.status);
  const pairedChat = useTelegramStore((state) => state.pairedChat);
  const lastError = useTelegramStore((state) => state.lastError);

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-ds-border bg-ds-surface p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-semibold text-ds-text">
              <MessageCircle size={16} aria-hidden="true" />
              <span>{t('settings.notifications.title')}</span>
            </div>
            <p className="mt-1 text-xs leading-5 text-ds-muted">
              {t('settings.notifications.description')}
            </p>
          </div>
          <span className={`rounded-full px-2 py-1 text-[10px] font-medium ${statusBadgeClass(telegramStatus, Boolean(pairedChat))}`}>
            {pairedChat
              ? t('settings.telegramConnect.status.connected')
              : t(`settings.telegramConnect.status.${telegramStatus}`)}
          </span>
        </div>
        {lastError ? (
          <div className="mt-3 rounded-lg border border-ds-error/30 bg-ds-error/10 px-3 py-2 text-[11px] text-ds-error">
            {lastError}
          </div>
        ) : null}
      </section>

      <TelegramConnectFlow rpc={rpc} embedded />

      <TelegramNotificationSettings rpc={rpc} />

      <div className="grid gap-3 md:grid-cols-2">
        <ComingSoonChannel
          icon={<Hash size={15} aria-hidden="true" />}
          title={t('settings.notifications.slack.title')}
          badge={t('settings.notifications.comingSoon')}
        />
        <ComingSoonChannel
          icon={<Mail size={15} aria-hidden="true" />}
          title={t('settings.notifications.email.title')}
          badge={t('settings.notifications.comingSoon')}
        />
      </div>
    </div>
  );
}

function ComingSoonChannel({
  badge,
  icon,
  title,
}: {
  readonly badge: string;
  readonly icon: ReactElement;
  readonly title: string;
}): ReactElement {
  return (
    <section
      aria-disabled="true"
      className="rounded-lg border border-ds-border bg-ds-surface/60 p-4 opacity-70"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-ds-text">
          <span className="text-ds-muted">{icon}</span>
          <span>{title}</span>
        </div>
        <span className="rounded-full bg-ds-bg px-2 py-1 text-[10px] font-medium text-ds-muted">
          {badge}
        </span>
      </div>
    </section>
  );
}

export function statusBadgeClass(status: string, paired: boolean): string {
  if (status === 'running' && paired) {
    return 'bg-ds-success/15 text-ds-success';
  }
  if (status === 'error') {
    return 'bg-ds-error/15 text-ds-error';
  }
  if (status === 'starting' || status === 'stopping' || status === 'running') {
    return 'bg-ds-warning/15 text-ds-warning';
  }
  return 'bg-ds-bg text-ds-muted';
}
