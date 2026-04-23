import { useEffect, useState, type ReactElement } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Inline offline banner for the mobile shell. Render-only — no actions, no
 * 44x44 touch target (this is a status banner, not a button). The actual
 * offline read experience comes from the service worker's cached app shell
 * and last-known store snapshots in localStorage.
 */
export function OfflineBanner(): ReactElement | null {
  const { t } = useTranslation('mobile');
  const [online, setOnline] = useState<boolean>(() => {
    if (typeof navigator === 'undefined') return true;
    return navigator.onLine !== false;
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handleOnline = (): void => setOnline(true);
    const handleOffline = (): void => setOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  if (online) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="mobile-offline-banner"
      style={{
        padding: '8px 12px',
        background: 'var(--ds-surface)',
        color: 'var(--ds-text)',
        borderBottom: '1px solid var(--ds-border)',
        fontSize: '13px',
        lineHeight: '1.4',
        display: 'flex',
        flexDirection: 'column',
        gap: '2px',
      }}
    >
      <span style={{ fontWeight: 600 }}>{t('offline.banner')}</span>
      <span style={{ color: 'var(--ds-muted)', fontSize: '12px' }}>
        {t('offline.lastUpdatedAt')}
      </span>
    </div>
  );
}
