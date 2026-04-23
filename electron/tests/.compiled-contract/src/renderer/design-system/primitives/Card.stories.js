"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SpaciousDensity = exports.ComfortableDensity = exports.CompactDensity = exports.Danger = exports.Accent = exports.Elevated = exports.Default = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const applyDensityScale_1 = require("../../application/layout/applyDensityScale");
const Card_1 = require("./Card");
const meta = {
    title: 'Design System/Primitives/Card',
    component: Card_1.Card,
    tags: ['autodocs'],
    args: {
        children: ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-2", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-ds-xs uppercase tracking-widest text-ds-muted", children: "Mission" }), (0, jsx_runtime_1.jsx)("div", { className: "text-ds-lg font-semibold text-ds-text", children: "Churn prediction refresh" }), (0, jsx_runtime_1.jsx)("div", { className: "text-ds-sm text-ds-muted", children: "Rebuild the monthly churn forecast with the current subscription cohort." })] })),
    },
};
exports.default = meta;
exports.Default = {};
exports.Elevated = {
    args: {
        tone: 'elevated',
    },
};
exports.Accent = {
    args: {
        tone: 'accent',
    },
};
exports.Danger = {
    args: {
        tone: 'danger',
    },
};
function DensityShowcase({ mode, args }) {
    return ((0, jsx_runtime_1.jsxs)("div", { "data-density": mode, style: (0, applyDensityScale_1.applyDensityScale)(mode), className: "grid gap-ds-3 bg-ds-bg p-ds-4", children: [(0, jsx_runtime_1.jsx)(Card_1.Card, { ...args, tone: "default" }), (0, jsx_runtime_1.jsx)(Card_1.Card, { ...args, tone: "elevated" }), (0, jsx_runtime_1.jsx)(Card_1.Card, { ...args, tone: "accent" })] }));
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
