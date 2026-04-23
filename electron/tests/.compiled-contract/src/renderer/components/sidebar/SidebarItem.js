"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SidebarItem = SidebarItem;
const jsx_runtime_1 = require("react/jsx-runtime");
const primitives_1 = require("../../design-system/primitives");
function SidebarItem({ icon: Icon, label, active = false, collapsed, onClick, dataTestId, }) {
    const button = ((0, jsx_runtime_1.jsxs)("button", { onClick: onClick, "data-testid": dataTestId, "aria-label": label, title: collapsed ? undefined : label, className: `group relative flex w-full items-center rounded-lg px-2 py-2 text-left transition-colors ${collapsed ? 'justify-center' : 'justify-start gap-2'} ${active
            ? 'bg-ds-accent/10 text-ds-accent'
            : 'text-ds-muted hover:bg-ds-bg hover:text-ds-text'} focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50`, children: [(0, jsx_runtime_1.jsx)(Icon, { size: 16, className: "shrink-0" }), !collapsed && (0, jsx_runtime_1.jsx)("span", { className: "truncate text-xs font-medium", children: label })] }));
    if (!collapsed) {
        return button;
    }
    return ((0, jsx_runtime_1.jsx)(primitives_1.Tooltip, { content: label, placement: "right", children: button }));
}
