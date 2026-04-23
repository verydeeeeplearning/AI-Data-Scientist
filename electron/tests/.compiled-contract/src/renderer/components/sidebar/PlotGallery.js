"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.PlotGallery = PlotGallery;
const jsx_runtime_1 = require("react/jsx-runtime");
/**
 * Plot gallery — thumbnails of generated plots in sidebar, grouped by folder.
 *
 * Layout:
 *   Plots (count)
 *   ├─ (workspace root)
 *   │   [thumb] [thumb]
 *   └─ eda_titanic/
 *       [thumb] [thumb] [thumb]
 *
 * Hover a thumbnail to reveal a delete button. Click to open the full-size
 * modal, which also has a delete action.
 */
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
const filesStore_1 = require("../../stores/filesStore");
const i18nStore_1 = require("../../stores/i18nStore");
const WsProvider_1 = require("../../hooks/WsProvider");
const backendUrl_1 = require("../../utils/backendUrl");
// 4.14 fix: Dynamic backend URL instead of hardcoded port
const BACKEND_BASE = (0, backendUrl_1.getBackendBase)();
function plotSrc(path) {
    return `${BACKEND_BASE}/api/plots/${encodeURIComponent(path)}`;
}
function PlotGallery() {
    const { plots, plotGroups } = (0, filesStore_1.useFilesStore)();
    const { t } = (0, i18nStore_1.useI18n)();
    const [selectedPlot, setSelectedPlot] = (0, react_1.useState)(null);
    return ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-ds-muted uppercase tracking-wider", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.BarChart3, { size: 12 }), t('sidebar.plots'), plots.length > 0 && ((0, jsx_runtime_1.jsx)("span", { className: "ml-1 bg-ds-accent/20 text-ds-accent text-[10px] px-1.5 rounded-full", children: plots.length }))] }), (0, jsx_runtime_1.jsx)("div", { className: "px-1", children: plots.length === 0 ? ((0, jsx_runtime_1.jsx)("div", { className: "px-3 py-2 text-[11px] text-ds-muted/60", children: t('sidebar.noPlots') })) : (plotGroups.map((group) => ((0, jsx_runtime_1.jsx)(PlotFolder, { group: group, onSelect: setSelectedPlot }, group.folder || '__root__')))) })] }), selectedPlot && ((0, jsx_runtime_1.jsx)(PlotModal, { plot: selectedPlot, onClose: () => setSelectedPlot(null) }))] }));
}
function PlotFolder({ group, onSelect, }) {
    const [expanded, setExpanded] = (0, react_1.useState)(true);
    const isRoot = group.folder === '';
    return ((0, jsx_runtime_1.jsxs)("div", { className: "mb-1", children: [!isRoot && ((0, jsx_runtime_1.jsxs)("button", { onClick: () => setExpanded((e) => !e), className: "w-full flex items-center gap-1 px-2 py-0.5 rounded hover:bg-ds-bg text-[11px] text-ds-muted hover:text-ds-text transition-colors", children: [expanded ? (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronDown, { size: 11 }) : (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronRight, { size: 11 }), (0, jsx_runtime_1.jsx)(lucide_react_1.Folder, { size: 11 }), (0, jsx_runtime_1.jsx)("span", { className: "truncate", children: group.folder }), (0, jsx_runtime_1.jsx)("span", { className: "ml-auto text-[10px] text-ds-muted/50", children: group.entries.length })] })), expanded && ((0, jsx_runtime_1.jsx)("div", { className: `grid grid-cols-2 gap-1 ${isRoot ? 'px-2' : 'pl-3 pr-2 ml-2 border-l border-ds-border/40'}`, children: group.entries.map((plot) => ((0, jsx_runtime_1.jsx)(PlotThumbnail, { plot: plot, onSelect: onSelect }, plot.path))) }))] }));
}
function PlotThumbnail({ plot, onSelect, }) {
    const { rpc } = (0, WsProvider_1.useWs)();
    const { t } = (0, i18nStore_1.useI18n)();
    const [busy, setBusy] = (0, react_1.useState)(false);
    const handleDelete = (0, react_1.useCallback)(async (e) => {
        e.stopPropagation();
        const ok = window.confirm(t('sidebar.deleteConfirm', { name: plot.name }));
        if (!ok)
            return;
        setBusy(true);
        try {
            await rpc('files.delete', { path: plot.path });
        }
        catch (err) {
            console.error('[PlotGallery] delete failed:', err);
            window.alert(t('sidebar.deleteFailed', { message: err?.message ?? String(err) }));
        }
        finally {
            setBusy(false);
        }
    }, [rpc, plot, t]);
    return ((0, jsx_runtime_1.jsxs)("div", { className: "relative group", children: [(0, jsx_runtime_1.jsxs)("button", { onClick: () => onSelect(plot), className: "\n          block w-full rounded border border-ds-border overflow-hidden\n          hover:border-ds-accent transition-colors cursor-pointer\n          bg-ds-bg\n        ", title: plot.name, children: [(0, jsx_runtime_1.jsx)("img", { src: plotSrc(plot.path), alt: plot.name, className: "w-full h-16 object-cover", loading: "lazy" }), (0, jsx_runtime_1.jsx)("div", { className: "px-1 py-0.5 text-[9px] text-ds-muted truncate", children: plot.name })] }), (0, jsx_runtime_1.jsx)("button", { onClick: handleDelete, disabled: busy, className: "\n          absolute top-0.5 right-0.5 p-1 rounded\n          bg-black/60 text-white/90 hover:bg-red-500/80\n          opacity-0 group-hover:opacity-100 transition-opacity\n          disabled:opacity-50\n        ", title: t('sidebar.delete'), "aria-label": t('sidebar.delete'), children: busy ? (0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { size: 11, className: "animate-spin" }) : (0, jsx_runtime_1.jsx)(lucide_react_1.Trash2, { size: 11 }) })] }));
}
function PlotModal({ plot, onClose }) {
    const { rpc } = (0, WsProvider_1.useWs)();
    const { t } = (0, i18nStore_1.useI18n)();
    const [busy, setBusy] = (0, react_1.useState)(false);
    (0, react_1.useEffect)(() => {
        const handleKey = (e) => {
            if (e.key === 'Escape')
                onClose();
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [onClose]);
    const handleDelete = (0, react_1.useCallback)(async () => {
        const ok = window.confirm(t('sidebar.deleteConfirm', { name: plot.name }));
        if (!ok)
            return;
        setBusy(true);
        try {
            await rpc('files.delete', { path: plot.path });
            onClose();
        }
        catch (err) {
            console.error('[PlotGallery] delete failed:', err);
            window.alert(t('sidebar.deleteFailed', { message: err?.message ?? String(err) }));
            setBusy(false);
        }
    }, [rpc, plot, onClose, t]);
    return ((0, jsx_runtime_1.jsx)("div", { role: "dialog", "aria-modal": "true", "aria-labelledby": "plot-gallery-title", className: "fixed inset-0 z-50 flex items-center justify-center bg-black/70", onClick: onClose, children: (0, jsx_runtime_1.jsxs)("div", { className: "relative max-w-[90vw] max-h-[90vh] bg-ds-surface rounded-lg border border-ds-border shadow-2xl overflow-hidden", onClick: (e) => e.stopPropagation(), children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center justify-between px-4 py-2 border-b border-ds-border gap-3", children: [(0, jsx_runtime_1.jsx)("span", { id: "plot-gallery-title", className: "text-sm text-ds-text font-medium truncate flex-1", children: plot.path }), (0, jsx_runtime_1.jsx)("button", { onClick: handleDelete, disabled: busy, className: "p-1 rounded hover:bg-red-500/20 text-ds-muted hover:text-red-400 transition-colors disabled:opacity-50", title: t('sidebar.delete'), "aria-label": t('sidebar.delete'), children: busy ? (0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { size: 15, className: "animate-spin" }) : (0, jsx_runtime_1.jsx)(lucide_react_1.Trash2, { size: 15 }) }), (0, jsx_runtime_1.jsx)("button", { onClick: onClose, className: "p-1 rounded hover:bg-ds-bg text-ds-muted hover:text-ds-text transition-colors", children: (0, jsx_runtime_1.jsx)(lucide_react_1.X, { size: 16 }) })] }), (0, jsx_runtime_1.jsx)("div", { className: "p-4 flex items-center justify-center", children: (0, jsx_runtime_1.jsx)("img", { src: plotSrc(plot.path), alt: plot.name, className: "max-w-full max-h-[80vh] object-contain" }) })] }) }));
}
