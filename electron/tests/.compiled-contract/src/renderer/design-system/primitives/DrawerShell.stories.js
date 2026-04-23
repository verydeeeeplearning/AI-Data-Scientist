"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LargeLeft = exports.Default = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const Button_1 = require("./Button");
const DrawerShell_1 = require("./DrawerShell");
const meta = {
    title: 'Design System/Primitives/DrawerShell',
    component: DrawerShell_1.DrawerShell,
    parameters: {
        layout: 'fullscreen',
    },
    args: {
        open: true,
        title: 'Inspector drawer',
        description: 'A token-driven drawer for focused workflows and side-panel tasks.',
    },
};
exports.default = meta;
exports.Default = {
    render: (args) => {
        const [open, setOpen] = (0, react_1.useState)(true);
        return ((0, jsx_runtime_1.jsxs)("div", { className: "min-h-screen bg-ds-bg p-ds-6", children: [(0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "primary", onClick: () => setOpen(true), children: "Open drawer" }), (0, jsx_runtime_1.jsx)(DrawerShell_1.DrawerShell, { ...args, open: open, onDismiss: () => setOpen(false), footer: (0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", onClick: () => setOpen(false), children: "Cancel" }), (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "primary", onClick: () => setOpen(false), children: "Confirm" })] }), children: (0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-4", children: [(0, jsx_runtime_1.jsx)("div", { className: "rounded-ds-lg border border-ds-border/70 bg-ds-bg/70 p-ds-4 text-ds-sm text-ds-text", children: "Drawer body content lives here." }), (0, jsx_runtime_1.jsx)("div", { className: "rounded-ds-lg border border-ds-border/70 bg-ds-bg/70 p-ds-4 text-ds-sm text-ds-muted", children: "Use this for mission details, inspectors, approval flows, or guided edits." })] }) })] }));
    },
};
exports.LargeLeft = {
    args: {
        placement: 'left',
        size: 'lg',
        title: 'Large editor drawer',
        description: 'Supports wider side tasks without introducing a separate screen.',
    },
};
