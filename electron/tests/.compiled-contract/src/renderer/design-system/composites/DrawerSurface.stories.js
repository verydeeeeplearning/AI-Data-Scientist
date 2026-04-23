"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.IncidentMode = exports.Default = void 0;
const jsx_runtime_1 = require("react/jsx-runtime");
const lucide_react_1 = require("lucide-react");
const primitives_1 = require("../primitives");
const DrawerSurface_1 = require("./DrawerSurface");
function DrawerSurfaceDemo({ eyebrow, title, description, statusTone, statusLabel, bodyClassName, }) {
    return ((0, jsx_runtime_1.jsx)("div", { className: "min-h-screen bg-ds-bg p-ds-6", children: (0, jsx_runtime_1.jsxs)(DrawerSurface_1.DrawerSurface, { className: "mx-auto max-w-3xl rounded-ds-xl border", children: [(0, jsx_runtime_1.jsx)(DrawerSurface_1.DrawerSurfaceHeader, { children: (0, jsx_runtime_1.jsxs)("div", { className: "min-w-0 flex-1 space-y-ds-2", children: [(0, jsx_runtime_1.jsx)(DrawerSurface_1.DrawerSurfaceEyebrow, { children: eyebrow }), (0, jsx_runtime_1.jsxs)("div", { className: "flex flex-wrap items-start justify-between gap-ds-3", children: [(0, jsx_runtime_1.jsxs)("div", { className: "min-w-0 space-y-ds-2", children: [(0, jsx_runtime_1.jsx)("h2", { className: "text-ds-xl font-semibold text-ds-text", children: title }), (0, jsx_runtime_1.jsx)("p", { className: "max-w-2xl text-ds-sm leading-6 text-ds-muted", children: description })] }), (0, jsx_runtime_1.jsx)(primitives_1.Badge, { tone: statusTone, compact: true, className: "normal-case", children: statusLabel })] })] }) }), (0, jsx_runtime_1.jsxs)(DrawerSurface_1.DrawerSurfaceBody, { className: bodyClassName, children: [(0, jsx_runtime_1.jsxs)(DrawerSurface_1.DrawerSurfaceStatGrid, { children: [(0, jsx_runtime_1.jsx)(DrawerSurface_1.DrawerSurfaceStat, { label: "Run", value: "run-2026-04-20-017" }), (0, jsx_runtime_1.jsx)(DrawerSurface_1.DrawerSurfaceStat, { label: "Owner", value: "autonomous-runtime" }), (0, jsx_runtime_1.jsx)(DrawerSurface_1.DrawerSurfaceStat, { label: "Stage", value: "verification" }), (0, jsx_runtime_1.jsx)(DrawerSurface_1.DrawerSurfaceStat, { label: "Latency", value: "1.24s" })] }), (0, jsx_runtime_1.jsxs)(DrawerSurface_1.DrawerSurfaceSection, { children: [(0, jsx_runtime_1.jsx)(DrawerSurface_1.DrawerSurfaceSectionTitle, { children: "Summary" }), (0, jsx_runtime_1.jsx)("p", { className: "mt-ds-3 text-ds-sm leading-6 text-ds-text", children: "This drawer surface is intended for inspector-style flows where the header, stat grid, and structured sections must stay visually consistent across runtime consoles." })] }), (0, jsx_runtime_1.jsxs)(DrawerSurface_1.DrawerSurfaceSection, { children: [(0, jsx_runtime_1.jsx)(DrawerSurface_1.DrawerSurfaceSectionTitle, { children: "Suggested Actions" }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-ds-3 flex flex-wrap gap-ds-2", children: [(0, jsx_runtime_1.jsx)(primitives_1.Button, { size: "sm", variant: "primary", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.ShieldCheck, { size: 14, "aria-hidden": "true" }), children: "Approve next step" }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { size: "sm", variant: "secondary", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.ArrowUpRight, { size: 14, "aria-hidden": "true" }), children: "Open evidence" }), (0, jsx_runtime_1.jsx)(primitives_1.Button, { size: "sm", variant: "danger", leadingIcon: (0, jsx_runtime_1.jsx)(lucide_react_1.AlertTriangle, { size: 14, "aria-hidden": "true" }), children: "Freeze writes" })] })] })] })] }) }));
}
const meta = {
    title: 'Design System/Composites/DrawerSurface',
    component: DrawerSurface_1.DrawerSurface,
    tags: ['autodocs'],
    parameters: {
        layout: 'fullscreen',
        docs: {
            description: {
                component: 'Inspector-style drawer composite for runtime and operator side panels. Use it when a surface needs shared header, stat-grid, and section chrome rather than a raw modal shell.',
            },
        },
    },
};
exports.default = meta;
exports.Default = {
    render: () => ((0, jsx_runtime_1.jsx)(DrawerSurfaceDemo, { eyebrow: "Runtime inspector", title: "Run Detail Console", description: "Shared drawer chrome for side-panel workflows, status summaries, and structured task follow-through.", statusTone: "success", statusLabel: "Healthy" })),
};
exports.IncidentMode = {
    render: () => ((0, jsx_runtime_1.jsx)(DrawerSurfaceDemo, { eyebrow: "Operator override", title: "Incident Review Surface", description: "Use the same drawer shell for escalated runtime events that need stronger visual urgency and action affordances.", statusTone: "warning", statusLabel: "Attention needed", bodyClassName: "bg-ds-warning/5" })),
};
