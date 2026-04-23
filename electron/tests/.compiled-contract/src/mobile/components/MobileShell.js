"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MobileShell = MobileShell;
const jsx_runtime_1 = require("react/jsx-runtime");
const BottomNav_1 = require("./BottomNav");
const OfflineBanner_1 = require("./OfflineBanner");
function MobileShell({ activeTab, onTabChange, children, }) {
    return ((0, jsx_runtime_1.jsxs)("div", { style: {
            display: 'flex',
            flexDirection: 'column',
            height: '100dvh',
            background: 'var(--ds-bg)',
            color: 'var(--ds-text)',
            overflow: 'hidden',
        }, children: [(0, jsx_runtime_1.jsx)(OfflineBanner_1.OfflineBanner, {}), (0, jsx_runtime_1.jsx)("main", { id: "mobile-main-content", style: {
                    flex: 1,
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    WebkitOverflowScrolling: 'touch',
                    paddingTop: 'env(safe-area-inset-top, 0px)',
                }, children: children }), (0, jsx_runtime_1.jsx)(BottomNav_1.BottomNav, { activeTab: activeTab, onTabChange: onTabChange })] }));
}
