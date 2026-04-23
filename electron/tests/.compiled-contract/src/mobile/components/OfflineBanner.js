"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.OfflineBanner = OfflineBanner;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_i18next_1 = require("react-i18next");
/**
 * Inline offline banner for the mobile shell. Render-only — no actions, no
 * 44x44 touch target (this is a status banner, not a button). The actual
 * offline read experience comes from the service worker's cached app shell
 * and last-known store snapshots in localStorage.
 */
function OfflineBanner() {
    const { t } = (0, react_i18next_1.useTranslation)('mobile');
    const [online, setOnline] = (0, react_1.useState)(() => {
        if (typeof navigator === 'undefined')
            return true;
        return navigator.onLine !== false;
    });
    (0, react_1.useEffect)(() => {
        if (typeof window === 'undefined')
            return;
        const handleOnline = () => setOnline(true);
        const handleOffline = () => setOnline(false);
        window.addEventListener('online', handleOnline);
        window.addEventListener('offline', handleOffline);
        return () => {
            window.removeEventListener('online', handleOnline);
            window.removeEventListener('offline', handleOffline);
        };
    }, []);
    if (online)
        return null;
    return ((0, jsx_runtime_1.jsxs)("div", { role: "status", "aria-live": "polite", "data-testid": "mobile-offline-banner", style: {
            padding: '8px 12px',
            background: 'var(--ds-surface)',
            color: 'var(--ds-text)',
            borderBottom: '1px solid var(--ds-border)',
            fontSize: '13px',
            lineHeight: '1.4',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
        }, children: [(0, jsx_runtime_1.jsx)("span", { style: { fontWeight: 600 }, children: t('offline.banner') }), (0, jsx_runtime_1.jsx)("span", { style: { color: 'var(--ds-muted)', fontSize: '12px' }, children: t('offline.lastUpdatedAt') })] }));
}
