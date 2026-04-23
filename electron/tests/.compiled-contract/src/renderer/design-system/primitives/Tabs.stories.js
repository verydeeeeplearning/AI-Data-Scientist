"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SpaciousDensity = exports.ComfortableDensity = exports.CompactDensity = exports.WithDisabledTab = exports.Default = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const applyDensityScale_1 = require("../../application/layout/applyDensityScale");
const Tabs_1 = require("./Tabs");
const noop = () => undefined;
const meta = {
    title: 'Design System/Primitives/Tabs',
    component: Tabs_1.Tabs,
    tags: ['autodocs'],
    args: {
        value: 'overview',
        onValueChange: noop,
        items: [
            {
                value: 'overview',
                label: 'Overview',
                content: ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-2", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-ds-sm font-medium text-ds-text", children: "Pipeline summary" }), (0, jsx_runtime_1.jsx)("p", { className: "text-ds-sm leading-6 text-ds-muted", children: "The agent has a clean execution path, no blocked approvals, and stable delivery policy settings." })] })),
            },
            {
                value: 'quality',
                label: 'Quality',
                content: ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-2", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-ds-sm font-medium text-ds-text", children: "Validation signals" }), (0, jsx_runtime_1.jsx)("p", { className: "text-ds-sm leading-6 text-ds-muted", children: "Contract checks, lint gates, and workflow guards all point to a ready-to-ship state." })] })),
            },
            {
                value: 'delivery',
                label: 'Delivery',
                content: ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-2", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-ds-sm font-medium text-ds-text", children: "Operator outcome" }), (0, jsx_runtime_1.jsx)("p", { className: "text-ds-sm leading-6 text-ds-muted", children: "Notifications are aligned with the current cadence, quiet hours, and escalation policy." })] })),
            },
        ],
    },
};
exports.default = meta;
function TabsStory(args) {
    const [value, setValue] = (0, react_1.useState)(args.value);
    return (0, jsx_runtime_1.jsx)(Tabs_1.Tabs, { ...args, value: value, onValueChange: setValue });
}
exports.Default = {
    args: {
        onValueChange: noop,
    },
    render: (args) => (0, jsx_runtime_1.jsx)(TabsStory, { ...args }),
};
exports.WithDisabledTab = {
    args: {
        value: 'overview',
        onValueChange: noop,
        items: [
            {
                value: 'overview',
                label: 'Overview',
                content: (0, jsx_runtime_1.jsx)("p", { className: "text-ds-sm leading-6 text-ds-muted", children: "Active tab content." }),
            },
            {
                value: 'locked',
                label: 'Locked',
                disabled: true,
                content: (0, jsx_runtime_1.jsx)("p", { className: "text-ds-sm leading-6 text-ds-muted", children: "This tab cannot be selected." }),
            },
        ],
    },
    render: (args) => (0, jsx_runtime_1.jsx)(TabsStory, { ...args }),
};
function DensityShowcase({ mode, args }) {
    const [value, setValue] = (0, react_1.useState)(args.value);
    return ((0, jsx_runtime_1.jsx)("div", { "data-density": mode, style: (0, applyDensityScale_1.applyDensityScale)(mode), className: "bg-ds-bg p-ds-4", children: (0, jsx_runtime_1.jsx)(Tabs_1.Tabs, { ...args, value: value, onValueChange: setValue }) }));
}
exports.CompactDensity = {
    render: (args) => (0, jsx_runtime_1.jsx)(DensityShowcase, { mode: "compact", args: args }),
};
exports.ComfortableDensity = {
    render: (args) => (0, jsx_runtime_1.jsx)(DensityShowcase, { mode: "comfortable", args: args }),
};
exports.SpaciousDensity = {
    render: (args) => (0, jsx_runtime_1.jsx)(DensityShowcase, { mode: "spacious", args: args }),
};
