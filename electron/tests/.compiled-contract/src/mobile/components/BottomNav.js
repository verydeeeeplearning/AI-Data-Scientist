"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.BottomNav = BottomNav;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const react_i18next_1 = require("react-i18next");
const router_1 = require("../router");
const TAB_ICONS = {
    mission: lucide_react_1.Target,
    runs: lucide_react_1.Play,
    artifacts: lucide_react_1.Archive,
    approvals: lucide_react_1.ShieldCheck,
    settings: lucide_react_1.Settings,
};
function BottomNav({ activeTab, onTabChange }) {
    const { t } = (0, react_i18next_1.useTranslation)('mobile');
    return ((0, jsx_runtime_1.jsx)("nav", { role: "tablist", "aria-label": t('nav.primary'), style: {
            display: 'flex',
            borderTop: '1px solid var(--ds-border)',
            background: 'var(--ds-surface)',
            paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        }, children: router_1.MOBILE_TABS.map((tab) => {
            const Icon = TAB_ICONS[tab];
            const isActive = activeTab === tab;
            return ((0, jsx_runtime_1.jsxs)("button", { role: "tab", "aria-selected": isActive, "aria-current": isActive ? 'page' : undefined, onClick: () => onTabChange(tab), "data-tab": tab, style: {
                    flex: 1,
                    minHeight: '44px',
                    minWidth: '44px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '2px',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    color: isActive ? 'var(--ds-accent)' : 'var(--ds-muted)',
                    fontSize: '10px',
                    fontWeight: isActive ? 600 : 400,
                    padding: '8px 4px',
                }, children: [(0, jsx_runtime_1.jsx)(Icon, { size: 22, "aria-hidden": "true" }), (0, jsx_runtime_1.jsx)("span", { children: t(`nav.${tab}`) })] }, tab));
        }) }));
}
