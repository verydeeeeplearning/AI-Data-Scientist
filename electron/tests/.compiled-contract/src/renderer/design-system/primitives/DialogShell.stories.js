"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SpaciousDensity = exports.ComfortableDensity = exports.CompactDensity = exports.DangerTone = exports.Default = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const applyDensityScale_1 = require("../../application/layout/applyDensityScale");
const Button_1 = require("./Button");
const DialogShell_1 = require("./DialogShell");
const meta = {
    title: 'Design System/Primitives/DialogShell',
    component: DialogShell_1.DialogShell,
    tags: ['autodocs'],
    parameters: {
        layout: 'fullscreen',
    },
    args: {
        open: true,
        title: 'Approve high-impact rerun',
        description: 'The agent wants to retrain the production churn model with a new cohort split. Review the risk summary before continuing.',
        children: ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "rounded-ds-lg border border-ds-border bg-ds-bg/60 p-ds-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-ds-xs uppercase tracking-widest text-ds-muted", children: "Impact" }), (0, jsx_runtime_1.jsx)("div", { className: "mt-ds-2 text-ds-sm text-ds-text", children: "This rerun will replace the current forecast baseline and notify subscribed operators." })] }), (0, jsx_runtime_1.jsxs)("div", { className: "rounded-ds-lg border border-ds-border bg-ds-bg/60 p-ds-3", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-ds-xs uppercase tracking-widest text-ds-muted", children: "Evidence" }), (0, jsx_runtime_1.jsx)("div", { className: "mt-ds-2 text-ds-sm text-ds-text", children: "Drift detectors flagged feature instability across two acquisition channels." })] })] })),
        footer: ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", children: "Cancel" }), (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "primary", children: "Approve rerun" })] })),
    },
};
exports.default = meta;
exports.Default = {};
exports.DangerTone = {
    args: {
        tone: 'danger',
        title: 'Delete archived workspace',
        description: 'Deleting this workspace removes the local transcript cache and export history for every run linked to the project.',
        footer: ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", children: "Keep workspace" }), (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "danger", children: "Delete workspace" })] })),
    },
};
function DensityShowcase({ mode }) {
    return ((0, jsx_runtime_1.jsx)("div", { "data-density": mode, style: (0, applyDensityScale_1.applyDensityScale)(mode), className: "min-h-screen bg-ds-bg p-ds-6", children: (0, jsx_runtime_1.jsx)(DialogShell_1.DialogShell, { open: true, title: `Approve rerun (${mode})`, description: "Review the risk summary before continuing.", footer: (0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "secondary", children: "Cancel" }), (0, jsx_runtime_1.jsx)(Button_1.Button, { variant: "primary", children: "Approve" })] }), children: (0, jsx_runtime_1.jsxs)("div", { className: "text-ds-sm text-ds-text", children: ["Density ", mode, " preview of the dialog shell. Padding and font scales follow the active mode."] }) }) }));
}
exports.CompactDensity = {
    render: () => (0, jsx_runtime_1.jsx)(DensityShowcase, { mode: "compact" }),
};
exports.ComfortableDensity = {
    render: () => (0, jsx_runtime_1.jsx)(DensityShowcase, { mode: "comfortable" }),
};
exports.SpaciousDensity = {
    render: () => (0, jsx_runtime_1.jsx)(DensityShowcase, { mode: "spacious" }),
};
