import { useCallback, useEffect, useMemo, useState, type ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import {
  detectPushPermissionState,
  getCurrentSubscription,
  subscribeToWebPush,
  unsubscribeFromWebPush,
  type PushCapableRegistration,
  type PushPermissionState,
  type PushSubscriptionPayload,
} from '../push/pushAdapter';
import { getBackendBase } from '../../renderer/utils/backendUrl';
import { VapidSubjectField } from './VapidSubjectField';

type CardStatus =
  | 'unsupported'
  | 'denied'
  | 'inactive'
  | 'active'
  | 'loading'
  | 'error';

interface WebPushMetricsSummary {
  deliveredCount: number;
  failedCount: number;
  prunedCount: number;
  uniqueEndpoints: number;
}

function getRegistration(): Promise<PushCapableRegistration | null> {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) {
    return Promise.resolve(null);
  }
  return navigator.serviceWorker.ready.then(
    (reg) => reg as unknown as PushCapableRegistration,
    () => null,
  );
}

function metricValue(value: number | null | undefined): string {
  return String(typeof value === 'number' && Number.isFinite(value) ? value : 0);
}

export function PushOptInCard(): ReactElement {
  const { t } = useTranslation('mobile');
  const bridge = window.electronAPI?.webPush;
  const initialPermission: PushPermissionState = useMemo(() => {
    if (typeof window === 'undefined') {
      return 'unsupported';
    }
    return detectPushPermissionState({
      Notification: 'Notification' in window
        ? (window as typeof window & {
            Notification: { permission: NotificationPermission };
          }).Notification
        : undefined,
      PushManager: 'PushManager' in window ? window.PushManager : undefined,
    });
  }, []);
  const [status, setStatus] = useState<CardStatus>(
    initialPermission === 'unsupported' ? 'unsupported'
      : initialPermission === 'denied' ? 'denied'
      : 'inactive',
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [endpoint, setEndpoint] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<WebPushMetricsSummary | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);

  const refreshMetrics = useCallback(async () => {
    setMetricsLoading(true);
    setMetricsError(null);
    try {
      const url = new URL('/api/web-push/metrics', getBackendBase());
      url.searchParams.set('windowHours', '24');
      const response = await fetch(url.toString(), { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`metrics request failed (${response.status})`);
      }
      const payload = (await response.json()) as Partial<WebPushMetricsSummary>;
      setMetrics({
        deliveredCount: typeof payload.deliveredCount === 'number' ? payload.deliveredCount : 0,
        failedCount: typeof payload.failedCount === 'number' ? payload.failedCount : 0,
        prunedCount: typeof payload.prunedCount === 'number' ? payload.prunedCount : 0,
        uniqueEndpoints: typeof payload.uniqueEndpoints === 'number' ? payload.uniqueEndpoints : 0,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : t('mobile.push.metrics.error');
      setMetricsError(message);
      setMetrics(null);
    } finally {
      setMetricsLoading(false);
    }
  }, [t]);

  // On mount, detect whether a subscription already exists so the card
  // renders the correct CTA (enable vs disable).
  useEffect(() => {
    let cancelled = false;
    if (status === 'unsupported' || status === 'denied') {
      return;
    }
    (async () => {
      const registration = await getRegistration();
      if (!registration || cancelled) return;
      const current = await getCurrentSubscription(registration);
      if (cancelled) return;
      if (current) {
        setEndpoint(current.endpoint);
        setStatus('active');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status]);

  useEffect(() => {
    void refreshMetrics();
  }, [refreshMetrics]);

  const handleEnable = useCallback(async () => {
    if (!bridge) {
      setErrorMessage(t('mobile.push.error.bridgeMissing'));
      setStatus('error');
      return;
    }
    setStatus('loading');
    setErrorMessage(null);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setStatus(permission === 'denied' ? 'denied' : 'inactive');
        return;
      }
      const keyResp = await bridge.getPublicKey();
      if (!keyResp.ok || !keyResp.publicKey) {
        setErrorMessage(t('mobile.push.error.keyMissing'));
        setStatus('error');
        return;
      }
      const registration = await getRegistration();
      if (!registration) {
        setErrorMessage(t('mobile.push.error.swMissing'));
        setStatus('error');
        return;
      }
      const payload = await subscribeToWebPush(registration, keyResp.publicKey);
      const reg = await bridge.registerSubscription(payload);
      if (!reg.ok) {
        setErrorMessage(reg.error ?? t('mobile.push.error.register'));
        setStatus('error');
        return;
      }
      setEndpoint(payload.endpoint);
      setStatus('active');
      void refreshMetrics();
    } catch (err) {
      setErrorMessage((err as Error).message ?? t('mobile.push.error.generic'));
      setStatus('error');
    }
  }, [bridge, refreshMetrics, t]);

  const handleDisable = useCallback(async () => {
    setStatus('loading');
    setErrorMessage(null);
    try {
      const registration = await getRegistration();
      if (registration) {
        await unsubscribeFromWebPush(registration);
      }
      if (bridge && endpoint) {
        await bridge.unregisterSubscription({ endpoint });
      }
      setEndpoint(null);
      setStatus('inactive');
      void refreshMetrics();
    } catch (err) {
      setErrorMessage((err as Error).message ?? t('mobile.push.error.generic'));
      setStatus('error');
    }
  }, [bridge, endpoint, refreshMetrics, t]);

  const statusLabelKey =
    status === 'unsupported' ? 'mobile.push.status.unsupported'
      : status === 'denied' ? 'mobile.push.status.denied'
      : status === 'active' ? 'mobile.push.status.active'
      : status === 'loading' ? 'mobile.push.status.loading'
      : status === 'error' ? 'mobile.push.status.error'
      : 'mobile.push.status.inactive';

  const metricsAllZero =
    metrics?.deliveredCount === 0
    && metrics?.failedCount === 0
    && metrics?.prunedCount === 0
    && metrics?.uniqueEndpoints === 0;

  return (
    <section
      className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4"
      aria-labelledby="mobile-push-card-title"
    >
      <h2
        id="mobile-push-card-title"
        className="text-sm font-semibold text-ds-text"
      >
        {t('mobile.push.title')}
      </h2>
      <p className="mt-1 text-xs leading-5 text-ds-muted">
        {t('mobile.push.description')}
      </p>
      <p className="mt-3 text-xs uppercase tracking-[0.16em] text-ds-muted">
        {t(statusLabelKey)}
      </p>
      {errorMessage ? (
        <p className="mt-2 text-xs text-rose-300" role="alert">
          {errorMessage}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {status === 'active' ? (
          <button
            type="button"
            onClick={handleDisable}
            className="rounded-full border border-ds-border px-3 py-1 text-xs text-ds-text"
          >
            {t('mobile.push.button.disable')}
          </button>
        ) : null}
        {(status === 'inactive' || status === 'error') ? (
          <button
            type="button"
            onClick={handleEnable}
            className="rounded-full border border-ds-border px-3 py-1 text-xs text-ds-text"
          >
            {t('mobile.push.button.enable')}
          </button>
        ) : null}
      </div>

      <div className="mt-4">
        <VapidSubjectField />
      </div>

      <section className="mt-4 rounded-2xl border border-ds-border bg-ds-bg/50 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-ds-text">
              {t('mobile.push.metrics.title')}
            </h3>
            <p className="mt-1 text-xs leading-5 text-ds-muted">
              {t('mobile.push.metrics.window', { hours: 24 })}
            </p>
          </div>
          <span className="rounded-full border border-ds-border/70 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-ds-muted">
            {metricsLoading ? t('mobile.push.status.loading') : '24h'}
          </span>
        </div>
        {metricsError ? (
          <p className="mt-3 text-xs text-rose-300" role="alert">
            {metricsError}
          </p>
        ) : null}
        {metrics ? (
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="rounded-xl border border-ds-border/70 bg-ds-surface/80 p-3">
              <div className="text-[11px] uppercase tracking-[0.16em] text-ds-muted">
                {t('mobile.push.metrics.delivered')}
              </div>
              <div className="mt-2 text-lg font-semibold text-ds-text">
                {metricValue(metrics.deliveredCount)}
              </div>
            </div>
            <div className="rounded-xl border border-ds-border/70 bg-ds-surface/80 p-3">
              <div className="text-[11px] uppercase tracking-[0.16em] text-ds-muted">
                {t('mobile.push.metrics.failed')}
              </div>
              <div className="mt-2 text-lg font-semibold text-ds-text">
                {metricValue(metrics.failedCount)}
              </div>
            </div>
            <div className="rounded-xl border border-ds-border/70 bg-ds-surface/80 p-3">
              <div className="text-[11px] uppercase tracking-[0.16em] text-ds-muted">
                {t('mobile.push.metrics.pruned')}
              </div>
              <div className="mt-2 text-lg font-semibold text-ds-text">
                {metricValue(metrics.prunedCount)}
              </div>
            </div>
            <div className="rounded-xl border border-ds-border/70 bg-ds-surface/80 p-3">
              <div className="text-[11px] uppercase tracking-[0.16em] text-ds-muted">
                {t('mobile.push.metrics.unique')}
              </div>
              <div className="mt-2 text-lg font-semibold text-ds-text">
                {metricValue(metrics.uniqueEndpoints)}
              </div>
            </div>
          </div>
        ) : null}
        {metrics && metricsAllZero ? (
          <p className="mt-3 text-xs leading-5 text-ds-muted">
            {t('mobile.push.metrics.empty')}
          </p>
        ) : null}
      </section>
    </section>
  );
}
