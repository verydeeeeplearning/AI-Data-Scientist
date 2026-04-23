"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PushOptInCard = PushOptInCard;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_i18next_1 = require("react-i18next");
const pushAdapter_1 = require("../push/pushAdapter");
const backendUrl_1 = require("../../renderer/utils/backendUrl");
const VapidSubjectField_1 = require("./VapidSubjectField");
function getRegistration() {
    if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) {
        return Promise.resolve(null);
    }
    return navigator.serviceWorker.ready.then((reg) => reg, () => null);
}
function metricValue(value) {
    return String(typeof value === 'number' && Number.isFinite(value) ? value : 0);
}
function PushOptInCard() {
    const { t } = (0, react_i18next_1.useTranslation)('mobile');
    const bridge = window.electronAPI?.webPush;
    const initialPermission = (0, react_1.useMemo)(() => {
        if (typeof window === 'undefined') {
            return 'unsupported';
        }
        return (0, pushAdapter_1.detectPushPermissionState)({
            Notification: 'Notification' in window
                ? window.Notification
                : undefined,
            PushManager: 'PushManager' in window ? window.PushManager : undefined,
        });
    }, []);
    const [status, setStatus] = (0, react_1.useState)(initialPermission === 'unsupported' ? 'unsupported'
        : initialPermission === 'denied' ? 'denied'
            : 'inactive');
    const [errorMessage, setErrorMessage] = (0, react_1.useState)(null);
    const [endpoint, setEndpoint] = (0, react_1.useState)(null);
    const [metrics, setMetrics] = (0, react_1.useState)(null);
    const [metricsError, setMetricsError] = (0, react_1.useState)(null);
    const [metricsLoading, setMetricsLoading] = (0, react_1.useState)(true);
    const refreshMetrics = (0, react_1.useCallback)(async () => {
        setMetricsLoading(true);
        setMetricsError(null);
        try {
            const url = new URL('/api/web-push/metrics', (0, backendUrl_1.getBackendBase)());
            url.searchParams.set('windowHours', '24');
            const response = await fetch(url.toString(), { cache: 'no-store' });
            if (!response.ok) {
                throw new Error(`metrics request failed (${response.status})`);
            }
            const payload = (await response.json());
            setMetrics({
                deliveredCount: typeof payload.deliveredCount === 'number' ? payload.deliveredCount : 0,
                failedCount: typeof payload.failedCount === 'number' ? payload.failedCount : 0,
                prunedCount: typeof payload.prunedCount === 'number' ? payload.prunedCount : 0,
                uniqueEndpoints: typeof payload.uniqueEndpoints === 'number' ? payload.uniqueEndpoints : 0,
            });
        }
        catch (error) {
            const message = error instanceof Error ? error.message : t('mobile.push.metrics.error');
            setMetricsError(message);
            setMetrics(null);
        }
        finally {
            setMetricsLoading(false);
        }
    }, [t]);
    // On mount, detect whether a subscription already exists so the card
    // renders the correct CTA (enable vs disable).
    (0, react_1.useEffect)(() => {
        let cancelled = false;
        if (status === 'unsupported' || status === 'denied') {
            return;
        }
        (async () => {
            const registration = await getRegistration();
            if (!registration || cancelled)
                return;
            const current = await (0, pushAdapter_1.getCurrentSubscription)(registration);
            if (cancelled)
                return;
            if (current) {
                setEndpoint(current.endpoint);
                setStatus('active');
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [status]);
    (0, react_1.useEffect)(() => {
        void refreshMetrics();
    }, [refreshMetrics]);
    const handleEnable = (0, react_1.useCallback)(async () => {
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
            const payload = await (0, pushAdapter_1.subscribeToWebPush)(registration, keyResp.publicKey);
            const reg = await bridge.registerSubscription(payload);
            if (!reg.ok) {
                setErrorMessage(reg.error ?? t('mobile.push.error.register'));
                setStatus('error');
                return;
            }
            setEndpoint(payload.endpoint);
            setStatus('active');
            void refreshMetrics();
        }
        catch (err) {
            setErrorMessage(err.message ?? t('mobile.push.error.generic'));
            setStatus('error');
        }
    }, [bridge, refreshMetrics, t]);
    const handleDisable = (0, react_1.useCallback)(async () => {
        setStatus('loading');
        setErrorMessage(null);
        try {
            const registration = await getRegistration();
            if (registration) {
                await (0, pushAdapter_1.unsubscribeFromWebPush)(registration);
            }
            if (bridge && endpoint) {
                await bridge.unregisterSubscription({ endpoint });
            }
            setEndpoint(null);
            setStatus('inactive');
            void refreshMetrics();
        }
        catch (err) {
            setErrorMessage(err.message ?? t('mobile.push.error.generic'));
            setStatus('error');
        }
    }, [bridge, endpoint, refreshMetrics, t]);
    const statusLabelKey = status === 'unsupported' ? 'mobile.push.status.unsupported'
        : status === 'denied' ? 'mobile.push.status.denied'
            : status === 'active' ? 'mobile.push.status.active'
                : status === 'loading' ? 'mobile.push.status.loading'
                    : status === 'error' ? 'mobile.push.status.error'
                        : 'mobile.push.status.inactive';
    const metricsAllZero = metrics?.deliveredCount === 0
        && metrics?.failedCount === 0
        && metrics?.prunedCount === 0
        && metrics?.uniqueEndpoints === 0;
    return ((0, jsx_runtime_1.jsxs)("section", { className: "rounded-2xl border border-ds-border bg-ds-surface/70 p-4", "aria-labelledby": "mobile-push-card-title", children: [(0, jsx_runtime_1.jsx)("h2", { id: "mobile-push-card-title", className: "text-sm font-semibold text-ds-text", children: t('mobile.push.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-xs leading-5 text-ds-muted", children: t('mobile.push.description') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-xs uppercase tracking-[0.16em] text-ds-muted", children: t(statusLabelKey) }), errorMessage ? ((0, jsx_runtime_1.jsx)("p", { className: "mt-2 text-xs text-rose-300", role: "alert", children: errorMessage })) : null, (0, jsx_runtime_1.jsxs)("div", { className: "mt-3 flex flex-wrap gap-2", children: [status === 'active' ? ((0, jsx_runtime_1.jsx)("button", { type: "button", onClick: handleDisable, className: "rounded-full border border-ds-border px-3 py-1 text-xs text-ds-text", children: t('mobile.push.button.disable') })) : null, (status === 'inactive' || status === 'error') ? ((0, jsx_runtime_1.jsx)("button", { type: "button", onClick: handleEnable, className: "rounded-full border border-ds-border px-3 py-1 text-xs text-ds-text", children: t('mobile.push.button.enable') })) : null] }), (0, jsx_runtime_1.jsx)("div", { className: "mt-4", children: (0, jsx_runtime_1.jsx)(VapidSubjectField_1.VapidSubjectField, {}) }), (0, jsx_runtime_1.jsxs)("section", { className: "mt-4 rounded-2xl border border-ds-border bg-ds-bg/50 p-4", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-start justify-between gap-3", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("h3", { className: "text-sm font-semibold text-ds-text", children: t('mobile.push.metrics.title') }), (0, jsx_runtime_1.jsx)("p", { className: "mt-1 text-xs leading-5 text-ds-muted", children: t('mobile.push.metrics.window', { hours: 24 }) })] }), (0, jsx_runtime_1.jsx)("span", { className: "rounded-full border border-ds-border/70 px-2 py-1 text-[11px] uppercase tracking-[0.16em] text-ds-muted", children: metricsLoading ? t('mobile.push.status.loading') : '24h' })] }), metricsError ? ((0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-xs text-rose-300", role: "alert", children: metricsError })) : null, metrics ? ((0, jsx_runtime_1.jsxs)("div", { className: "mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4", children: [(0, jsx_runtime_1.jsxs)("div", { className: "rounded-xl border border-ds-border/70 bg-ds-surface/80 p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] uppercase tracking-[0.16em] text-ds-muted", children: t('mobile.push.metrics.delivered') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-2 text-lg font-semibold text-ds-text", children: metricValue(metrics.deliveredCount) })] }), (0, jsx_runtime_1.jsxs)("div", { className: "rounded-xl border border-ds-border/70 bg-ds-surface/80 p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] uppercase tracking-[0.16em] text-ds-muted", children: t('mobile.push.metrics.failed') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-2 text-lg font-semibold text-ds-text", children: metricValue(metrics.failedCount) })] }), (0, jsx_runtime_1.jsxs)("div", { className: "rounded-xl border border-ds-border/70 bg-ds-surface/80 p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] uppercase tracking-[0.16em] text-ds-muted", children: t('mobile.push.metrics.pruned') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-2 text-lg font-semibold text-ds-text", children: metricValue(metrics.prunedCount) })] }), (0, jsx_runtime_1.jsxs)("div", { className: "rounded-xl border border-ds-border/70 bg-ds-surface/80 p-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] uppercase tracking-[0.16em] text-ds-muted", children: t('mobile.push.metrics.unique') }), (0, jsx_runtime_1.jsx)("div", { className: "mt-2 text-lg font-semibold text-ds-text", children: metricValue(metrics.uniqueEndpoints) })] })] })) : null, metrics && metricsAllZero ? ((0, jsx_runtime_1.jsx)("p", { className: "mt-3 text-xs leading-5 text-ds-muted", children: t('mobile.push.metrics.empty') })) : null] })] }));
}
