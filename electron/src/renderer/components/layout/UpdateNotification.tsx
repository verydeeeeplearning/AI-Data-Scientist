/**
 * Update notification banner (P1-14).
 *
 * Subscribes to the main-process auto-updater IPC bridge and shows a single
 * persistent banner with the appropriate CTA for each state. Hidden in dev
 * builds (the main-process updater is a no-op there).
 */

import { useEffect, useState } from 'react';
import { Download, Loader2, RefreshCw, X } from 'lucide-react';
import { useI18n } from '../../stores/i18nStore';

type Status = 'idle' | 'available' | 'downloading' | 'ready' | 'error';

interface UpdateState {
  status: Status;
  version: string | null;
  percent: number;
  errorMessage: string | null;
}

const INITIAL: UpdateState = {
  status: 'idle',
  version: null,
  percent: 0,
  errorMessage: null,
};

export function UpdateNotification() {
  const { t } = useI18n();
  const [state, setState] = useState<UpdateState>(INITIAL);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const updater = window.electronAPI?.updater;
    if (!updater) return;

    let cancelled = false;
    void updater.getState()
      .then((info) => {
        if (cancelled || !info.isPackaged) return;
        // Dev build → updater is a no-op; stay hidden.
      })
      .catch((error) => {
        console.warn('[UpdateNotification] updater:getState failed:', error);
      });

    const offAvailable = updater.on('update-available', (payload) => {
      setDismissed(false);
      setState((prev) => ({
        ...prev,
        status: 'available',
        version: typeof payload.version === 'string' ? payload.version : prev.version,
        errorMessage: null,
      }));
    });

    const offProgress = updater.on('download-progress', (payload) => {
      setState((prev) => ({
        ...prev,
        status: 'downloading',
        percent:
          typeof payload.percent === 'number' ? Math.round(payload.percent) : prev.percent,
      }));
    });

    const offReady = updater.on('update-ready', (payload) => {
      setDismissed(false);
      setState((prev) => ({
        ...prev,
        status: 'ready',
        version: typeof payload.version === 'string' ? payload.version : prev.version,
      }));
    });

    const offError = updater.on('error', (payload) => {
      setState((prev) => ({
        ...prev,
        status: 'error',
        errorMessage:
          typeof payload.message === 'string' ? payload.message : t('common.error'),
      }));
    });

    return () => {
      cancelled = true;
      offAvailable();
      offProgress();
      offReady();
      offError();
    };
  }, [t]);

  if (dismissed || state.status === 'idle') {
    return null;
  }

  const handleDownload = async () => {
    setState((prev) => ({ ...prev, status: 'downloading', percent: 0 }));
    const updater = window.electronAPI?.updater;
    if (!updater) return;
    const result = await updater.download();
    if (!result.ok) {
      setState((prev) => ({ ...prev, status: 'error', errorMessage: result.error }));
    }
  };

  const handleInstall = async () => {
    await window.electronAPI?.updater?.install();
  };

  const version = state.version ?? '?';

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 z-40 flex max-w-sm items-start gap-3 rounded-lg border border-ds-accent/40 bg-ds-surface px-3 py-3 shadow-2xl"
    >
      <div className="mt-0.5 text-ds-accent">
        {state.status === 'downloading' ? (
          <Loader2 size={18} className="animate-spin" />
        ) : state.status === 'ready' ? (
          <RefreshCw size={18} />
        ) : (
          <Download size={18} />
        )}
      </div>
      <div className="min-w-0 flex-1">
        {state.status === 'available' && (
          <>
            <div className="text-xs font-medium text-ds-text">
              {t('update.available', { version })}
            </div>
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => void handleDownload()}
                className="rounded bg-ds-accent px-2.5 py-1 text-[11px] font-medium text-white hover:bg-ds-accent/90"
              >
                {t('update.download_btn')}
              </button>
              <button
                onClick={() => setDismissed(true)}
                className="rounded border border-ds-border px-2.5 py-1 text-[11px] text-ds-muted hover:text-ds-text"
              >
                {t('update.later_btn')}
              </button>
            </div>
          </>
        )}
        {state.status === 'downloading' && (
          <>
            <div className="text-xs font-medium text-ds-text">
              {t('update.downloading', { percent: state.percent })}
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded bg-ds-bg">
              <div
                className="h-full bg-ds-accent transition-[width]"
                style={{ width: `${state.percent}%` }}
              />
            </div>
          </>
        )}
        {state.status === 'ready' && (
          <>
            <div className="text-xs font-medium text-ds-text">{t('update.ready')}</div>
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => void handleInstall()}
                className="rounded bg-ds-accent px-2.5 py-1 text-[11px] font-medium text-white hover:bg-ds-accent/90"
              >
                {t('update.install_btn')}
              </button>
              <button
                onClick={() => setDismissed(true)}
                className="rounded border border-ds-border px-2.5 py-1 text-[11px] text-ds-muted hover:text-ds-text"
              >
                {t('update.defer_btn')}
              </button>
            </div>
          </>
        )}
        {state.status === 'error' && (
          <>
            <div className="text-xs font-medium text-ds-text">
              {state.errorMessage ?? t('common.error')}
            </div>
            <div className="mt-2 text-[10px] text-ds-muted">
              Current version continues to run normally.
            </div>
          </>
        )}
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="rounded p-0.5 text-ds-muted hover:bg-ds-bg hover:text-ds-text"
        aria-label={t('common.close')}
      >
        <X size={14} />
      </button>
    </div>
  );
}
