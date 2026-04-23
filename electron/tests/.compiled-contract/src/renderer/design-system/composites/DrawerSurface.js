"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DrawerSurface = DrawerSurface;
exports.DrawerSurfaceHeader = DrawerSurfaceHeader;
exports.DrawerSurfaceBody = DrawerSurfaceBody;
exports.DrawerSurfaceEyebrow = DrawerSurfaceEyebrow;
exports.DrawerSurfaceSection = DrawerSurfaceSection;
exports.DrawerSurfaceSectionTitle = DrawerSurfaceSectionTitle;
exports.DrawerSurfaceStatGrid = DrawerSurfaceStatGrid;
exports.DrawerSurfaceStat = DrawerSurfaceStat;
const jsx_runtime_1 = require("react/jsx-runtime");
const utils_1 = require("../primitives/utils");
function DrawerSurface({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("section", { className: (0, utils_1.cn)('flex h-full min-h-0 flex-col border-l border-ds-border bg-ds-surface/95 text-ds-text shadow-ds-lg', className), ...rest, children: children }));
}
function DrawerSurfaceHeader({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('flex items-start gap-ds-3 border-b border-ds-border/80 px-ds-4 py-ds-4', className), ...rest, children: children }));
}
function DrawerSurfaceBody({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('min-h-0 flex-1 overflow-y-auto px-ds-4 py-ds-4 space-y-ds-4', className), ...rest, children: children }));
}
function DrawerSurfaceEyebrow({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('text-ds-xs font-semibold uppercase tracking-widest text-ds-muted', className), ...rest, children: children }));
}
function DrawerSurfaceSection({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("section", { className: (0, utils_1.cn)('rounded-ds-lg border border-ds-border/70 bg-ds-bg/70 p-ds-3', className), ...rest, children: children }));
}
function DrawerSurfaceSectionTitle({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("h3", { className: (0, utils_1.cn)('text-ds-xs font-semibold uppercase tracking-widest text-ds-muted', className), ...rest, children: children }));
}
function DrawerSurfaceStatGrid({ className, children, ...rest }) {
    return ((0, jsx_runtime_1.jsx)("div", { className: (0, utils_1.cn)('grid grid-cols-2 gap-ds-2', className), ...rest, children: children }));
}
function DrawerSurfaceStat({ label, value, className, ...rest }) {
    return ((0, jsx_runtime_1.jsxs)("div", { className: (0, utils_1.cn)('rounded-ds-md border border-ds-border/70 bg-ds-surface/60 px-ds-3 py-ds-2', className), ...rest, children: [(0, jsx_runtime_1.jsx)("div", { className: "text-ds-2xs uppercase tracking-wider text-ds-muted", children: label }), (0, jsx_runtime_1.jsx)("div", { className: "mt-ds-1 text-ds-sm text-ds-text", children: value })] }));
}
