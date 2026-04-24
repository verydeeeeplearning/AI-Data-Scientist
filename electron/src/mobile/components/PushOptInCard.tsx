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
import {
  getPushErrorKey,
  getPushMetricsErrorKey,
  resolvePushErrorCode,
} from '../errors/mobileError';
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
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const [endpoint, setEndpoint] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<WebPushMetricsSummary | null>(null);
  const [metricsErrorKey, setMetricsErrorKey] = useState<string | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);

  const refreshMetrics = useCallback(async () => {
    setMetricsLoading(true);
    setMetricsErrorKey(null);
    try {
      const url = new URL('/api/web-push/metrics', getBackendBase());
      url.searchParams.set('windowHours', '24');
      const response = await fetch(url.toString(), { cache: 'no-store' });
      if (!response.ok) {
        const errorCode =
          response.status === 400 ? 'push_metrics_invalid_request' : 'push_metrics_load_failed';
        setMetricsErrorKey(getPushMetricsErrorKey(errorCode));
        setMetrics(null);
        return;
      }
      const payload = (await response.json()) as Partial<WebPushMetricsSummary>;
      setMetrics({
        deliveredCount: typeof payload.deliveredCount === 'number' ? payload.deliveredCount : 0,
        failedCount: typeof payload.failedCount === 'number' ? payload.failedCount : 0,
        prunedCount: typeof payload.prunedCount === 'number' ? payload.prunedCount : 0,
        uniqueEndpoints: typeof payload.uniqueEndpoints === 'number' ? payload.uniqueEndpoints : 0,
      });
    } catch (error) {
      setMetricsErrorKey(getPushMetricsErrorKey(resolvePushErrorCode(error)));
      setMetrics(null);
    } finally {
      setMetricsLoading(false);
    }
  }, []);

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
      try {
        const current = await getCurrentSubscription(registration);
        if (cancelled) return;
        if (current) {
          setEndpoint(current.endpoint);
          setStatus('active');
        }
      } catch (error) {
        if (cancelled) return;
        setErrorKey(getPushErrorKey(resolvePushErrorCode(error)));
        setStatus('error');
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
      setErrorKey('mobile.push.error.bridgeMissing');
      setStatus('error');
      return;
    }
    setStatus('loading');
    setErrorKey(null);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        setStatus(permission === 'denied' ? 'denied' : 'inactive');
        return;
      }
      const keyResp = await bridge.getPublicKey();
      if (!keyResp.ok || !keyResp.publicKey) {
        setErrorKey(getPushErrorKey(resolvePushErrorCode(keyResp.reason ?? 'push_vapid_public_key_missing')));
        setStatus('error');
        return;
      }
      const registration = await getRegistration();
      if (!registration) {
        setErrorKey('mobile.push.error.swMissing');
        setStatus('error');
        return;
      }
      const payload = await subscribeToWebPush(registration, keyResp.publicKey);
      const reg = await bridge.registerSubscription(payload);
      if (!reg.ok) {
        setErrorKey(getPushErrorKey(resolvePushErrorCode(reg.error)));
        setStatus('error');
        return;
      }
      setEndpoint(payload.endpoint);
      setStatus('active');
      void refreshMetrics();
    } catch (err) {
      setErrorKey(getPushErrorKey(resolvePushErrorCode(err)));
      setStatus('error');
    }
  }, [bridge, refreshMetrics]);

  const handleDisable = useCallback(async () => {
    setStatus('loading');
    setErrorKey(null);
    try {
      const registration = await getRegistration();
      if (registration) {
        await unsubscribeFromWebPush(registration);
      }
      if (bridge && endpoint) {
        const response = await bridge.unregisterSubscription({ endpoint });
        if (!response.ok) {
          setErrorKey(getPushErrorKey(resolvePushErrorCode(response.error)));
          setStatus('error');
          return;
        }
      }
      setEndpoint(null);
      setStatus('inactive');
      void refreshMetrics();
    } catch (err) {
      setErrorKey(getPushErrorKey(resolvePushErrorCode(err)));
      setStatus('error');
    }
  }, [bridge, endpoint, refreshMetrics]);

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
      {errorKey ? (
        <p className="mt-2 text-xs text-rose-300" role="alert">
          {t(errorKey)}
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
        {metricsErrorKey ? (
          <p className="mt-3 text-xs text-rose-300" role="alert">
            {t(metricsErrorKey)}
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
