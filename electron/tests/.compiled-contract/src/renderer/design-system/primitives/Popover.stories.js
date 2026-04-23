"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DangerTone = exports.AccentTone = exports.Default = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const Badge_1 = require("./Badge");
const Button_1 = require("./Button");
const Popover_1 = require("./Popover");
const meta = {
    title: 'Design System/Primitives/Popover',
    component: Popover_1.Popover,
    tags: ['autodocs'],
    parameters: {
        layout: 'centered',
    },
    args: {
        trigger: ((0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.SlidersHorizontal, { size: 14 }), children: "Delivery policy" })),
        title: 'Operator delivery',
        description: 'Tune notifications for blocked runs without leaving the current workflow.',
        children: ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "rounded-ds-lg border border-ds-border bg-ds-bg/60 p-ds-3 text-ds-xs text-ds-text", children: "Escalate repeated blocked states after two digest cycles and keep quiet hours pinned to the active timezone." }), (0, jsx_runtime_1.jsxs)("div", { className: "flex items-center justify-between gap-ds-3 rounded-ds-lg border border-ds-border bg-ds-bg/40 p-ds-3", children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsx)("div", { className: "text-ds-xs font-medium text-ds-text", children: "Digest cadence" }), (0, jsx_runtime_1.jsx)("div", { className: "mt-1 text-[11px] text-ds-muted", children: "Every 30 minutes" })] }), (0, jsx_runtime_1.jsx)(Badge_1.Badge, { tone: "accent", children: "Recommended" })] }), (0, jsx_runtime_1.jsxs)("div", { className: "flex gap-ds-2", children: [(0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", size: "sm", children: "Dismiss" }), (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "primary", size: "sm", children: "Apply policy" })] })] })),
    },
};
exports.default = meta;
exports.Default = {};
exports.AccentTone = {
    args: {
        tone: 'accent',
        trigger: ((0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "primary", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.Bell, { size: 14 }), children: "Notification digest" })),
        title: 'Digest window',
        description: 'Aggregate low-urgency events and send them as a single operator update.',
    },
};
exports.DangerTone = {
    args: {
        tone: 'danger',
        placement: 'right',
        align: 'start',
        trigger: ((0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "danger", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.AlertTriangle, { size: 14 }), children: "Destructive action" })),
        title: 'Delete cached artifacts',
        description: 'This clears local exports, generated notebooks, and runtime snapshots for the selected run.',
        children: ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "rounded-ds-lg border border-ds-error/30 bg-ds-error/10 p-ds-3 text-ds-xs text-ds-text", children: "The backend will not restore deleted artifacts during startup recovery." }), (0, jsx_runtime_1.jsxs)("div", { className: "flex gap-ds-2", children: [(0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", size: "sm", children: "Keep artifacts" }), (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "danger", size: "sm", children: "Delete cache" })] })] })),
    },
};
