"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.FileExplorer = FileExplorer;
const jsx_runtime_1 = require("react/jsx-runtime");
/**
 * File explorer — files grouped by top-level folder with preview + delete.
 *
 * Layout:
 *   Files header (icon, count, refresh button)
 *   ├─ (workspace root)
 *   │   • titanic.csv       (preview / delete on hover)
 *   │   • report.md         (preview / delete on hover)
 *   └─ projects/
 *       • meta.json
 *       ...
 *
 * Plot files are hidden here (they live in PlotGallery instead).
 */
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
const filesStore_1 = require("../../stores/filesStore");
const i18nStore_1 = require("../../stores/i18nStore");
const WsProvider_1 = require("../../hooks/WsProvider");
const FilePreviewModal_1 = require("./FilePreviewModal");
const TYPE_ICONS = {
    csv: lucide_react_1.FileSpreadsheet,
    tsv: lucide_react_1.FileSpreadsheet,
    xlsx: lucide_react_1.FileSpreadsheet,
    xls: lucide_react_1.FileSpreadsheet,
    parquet: lucide_react_1.FileSpreadsheet,
    pq: lucide_react_1.FileSpreadsheet,
    json: lucide_react_1.FileCode,
    yaml: lucide_react_1.FileCode,
    yml: lucide_react_1.FileCode,
    py: lucide_react_1.FileCode,
    md: lucide_react_1.FileText,
    txt: lucide_react_1.FileText,
    log: lucide_react_1.FileText,
};
// File types where an inline preview makes sense.
const PREVIEWABLE = new Set([
    'csv',
    'tsv',
    'xlsx',
    'xls',
    'parquet',
    'pq',
    'md',
    'txt',
    'log',
    'json',
    'yaml',
    'yml',
    'toml',
    'py',
    'ini',
]);
// P1-12: Map source file type → available export targets.
const EXPORT_TARGETS = {
    md: [
        { format: 'pdf', label: 'PDF' },
        { format: 'docx', label: 'Word (.docx)' },
        { format: 'html', label: 'HTML' },
    ],
    markdown: [
        { format: 'pdf', label: 'PDF' },
        { format: 'docx', label: 'Word (.docx)' },
        { format: 'html', label: 'HTML' },
    ],
    csv: [
        { format: 'xlsx', label: 'Excel (.xlsx)' },
        { format: 'html', label: 'HTML' },
    ],
    tsv: [
        { format: 'xlsx', label: 'Excel (.xlsx)' },
        { format: 'html', label: 'HTML' },
    ],
    ipynb: [
        { format: 'pdf', label: 'PDF' },
        { format: 'html', label: 'HTML' },
        { format: 'ipynb', label: 'Notebook copy' },
    ],
    html: [{ format: 'pdf', label: 'PDF' }],
    htm: [{ format: 'pdf', label: 'PDF' }],
};
function formatSize(bytes) {
    if (bytes < 1024)
        return `${bytes}B`;
    if (bytes < 1024 * 1024)
        return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}
function formatRelative(ms) {
    if (!ms)
        return '';
    const diff = Date.now() - ms;
    if (diff < 60000)
        return 'just now';
    if (diff < 3600000)
        return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000)
        return `${Math.floor(diff / 3600000)}h ago`;
    return `${Math.floor(diff / 86400000)}d ago`;
}
function FileIcon({ type }) {
    const Icon = TYPE_ICONS[type] ?? lucide_react_1.FileText;
    return (0, jsx_runtime_1.jsx)(Icon, { size: 13, className: "text-ds-muted flex-shrink-0" });
}
function FileExplorer({ onRefresh }) {
    const { fileGroups, files, loading } = (0, filesStore_1.useFilesStore)();
    const { t } = (0, i18nStore_1.useI18n)();
    const totalNonPlot = fileGroups.reduce((n, g) => n + g.entries.length, 0);
    const [previewPath, setPreviewPath] = (0, react_1.useState)(null);
    return ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: [(0, jsx_runtime_1.jsxs)("div", { children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center justify-between px-3 py-1.5", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center gap-1.5 text-xs font-medium text-ds-muted uppercase tracking-wider", children: [(0, jsx_runtime_1.jsx)(lucide_react_1.Files, { size: 12 }), t('sidebar.files'), totalNonPlot > 0 && ((0, jsx_runtime_1.jsx)("span", { className: "ml-1 bg-ds-accent/20 text-ds-accent text-[10px] px-1.5 rounded-full", children: totalNonPlot }))] }), (0, jsx_runtime_1.jsx)("button", { onClick: onRefresh, disabled: loading, className: "p-0.5 rounded hover:bg-ds-bg text-ds-muted hover:text-ds-text transition-colors", title: t('sidebar.refreshFiles'), "aria-label": t('sidebar.refreshFiles'), children: loading ? ((0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { size: 12, className: "animate-spin" })) : ((0, jsx_runtime_1.jsx)(lucide_react_1.RefreshCw, { size: 12 })) })] }), (0, jsx_runtime_1.jsx)("div", { className: "px-1", children: totalNonPlot === 0 ? ((0, jsx_runtime_1.jsx)("div", { className: "px-3 py-2 text-[11px] text-ds-muted/60", children: files.length === 0 ? t('sidebar.noFiles') : t('sidebar.onlyPlots') })) : (fileGroups.map((group) => ((0, jsx_runtime_1.jsx)(FolderGroup, { group: group, onPreview: setPreviewPath }, group.folder || '__root__')))) })] }), previewPath && ((0, jsx_runtime_1.jsx)(FilePreviewModal_1.FilePreviewModal, { path: previewPath, onClose: () => setPreviewPath(null) }))] }));
}
function FolderGroup({ group, onPreview, }) {
    // Root files always visible; named folders collapsible (expanded by default).
    const [expanded, setExpanded] = (0, react_1.useState)(true);
    const isRoot = group.folder === '';
    return ((0, jsx_runtime_1.jsxs)("div", { className: "mb-0.5", children: [!isRoot && ((0, jsx_runtime_1.jsxs)("button", { onClick: () => setExpanded((e) => !e), className: "w-full flex items-center gap-1 px-2 py-0.5 rounded hover:bg-ds-bg text-[11px] text-ds-muted hover:text-ds-text transition-colors", children: [expanded ? (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronDown, { size: 11 }) : (0, jsx_runtime_1.jsx)(lucide_react_1.ChevronRight, { size: 11 }), (0, jsx_runtime_1.jsx)(lucide_react_1.Folder, { size: 11 }), (0, jsx_runtime_1.jsx)("span", { className: "truncate", children: group.folder }), (0, jsx_runtime_1.jsx)("span", { className: "ml-auto text-[10px] text-ds-muted/50", children: group.entries.length })] })), expanded && ((0, jsx_runtime_1.jsx)("div", { className: isRoot ? '' : 'pl-3 border-l border-ds-border/40 ml-2', children: group.entries.map((file) => ((0, jsx_runtime_1.jsx)(FileRow, { file: file, onPreview: onPreview }, file.path))) }))] }));
}
function FileRow({ file, onPreview, }) {
    const { rpc } = (0, WsProvider_1.useWs)();
    const { t } = (0, i18nStore_1.useI18n)();
    const [busy, setBusy] = (0, react_1.useState)(false);
    const [exportOpen, setExportOpen] = (0, react_1.useState)(false);
    const [exporting, setExporting] = (0, react_1.useState)(null);
    const exportMenuRef = (0, react_1.useRef)(null);
    (0, react_1.useEffect)(() => {
        if (!exportOpen)
            return;
        const handler = (event) => {
            if (!exportMenuRef.current)
                return;
            if (exportMenuRef.current.contains(event.target))
                return;
            setExportOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [exportOpen]);
    const handleDelete = (0, react_1.useCallback)(async (e) => {
        e.stopPropagation();
        const ok = window.confirm(t('sidebar.deleteConfirm', { name: file.name }));
        if (!ok)
            return;
        setBusy(true);
        try {
            await rpc('files.delete', { path: file.path });
        }
        catch (err) {
            console.error('[FileExplorer] delete failed:', err);
            window.alert(t('sidebar.deleteFailed', { message: err?.message ?? String(err) }));
        }
        finally {
            setBusy(false);
        }
    }, [rpc, file, t]);
    const handlePreview = (0, react_1.useCallback)((e) => {
        e.stopPropagation();
        onPreview(file.path);
    }, [file.path, onPreview]);
    const handleExport = (0, react_1.useCallback)(async (format) => {
        if (!window.electronAPI?.finishArtifactExport) {
            window.alert(t('sidebar.exportDesktopOnly'));
            return;
        }
        setExportOpen(false);
        setExporting(format);
        try {
            const staged = (await rpc('files.export', { path: file.path, format }));
            const result = await window.electronAPI.finishArtifactExport({
                stagedPath: staged.exportPath,
                suggestedFilename: staged.suggestedFilename,
                format: staged.format,
                needsPdfRender: staged.needsPdfRender,
            });
            if (!result.canceled && result.error) {
                window.alert(t('sidebar.exportFailed', { message: result.error }));
            }
        }
        catch (err) {
            console.error('[FileExplorer] export failed:', err);
            window.alert(t('sidebar.exportFailed', { message: err?.message ?? String(err) }));
        }
        finally {
            setExporting(null);
        }
    }, [rpc, file.path, t]);
    const previewable = PREVIEWABLE.has(file.type.toLowerCase());
    const exportTargets = EXPORT_TARGETS[file.type.toLowerCase()] ?? [];
    const exportable = exportTargets.length > 0;
    return ((0, jsx_runtime_1.jsxs)("div", { className: "\n        flex items-center gap-2 px-2 py-1 rounded\n        hover:bg-ds-bg group text-xs\n      ", title: `${file.path} (${formatSize(file.size)})`, children: [(0, jsx_runtime_1.jsx)(FileIcon, { type: file.type }), (0, jsx_runtime_1.jsx)("button", { onClick: previewable ? handlePreview : undefined, disabled: !previewable, className: "truncate text-left text-ds-text/80 group-hover:text-ds-text flex-1 min-w-0 disabled:cursor-default", children: file.name }), (0, jsx_runtime_1.jsx)("span", { className: "text-[10px] text-ds-muted/50 flex-shrink-0 hidden group-hover:inline", children: formatRelative(file.modifiedAt) }), (0, jsx_runtime_1.jsx)("span", { className: "text-[10px] text-ds-muted/50 flex-shrink-0", children: formatSize(file.size) }), (0, jsx_runtime_1.jsxs)("div", { className: "hidden group-hover:flex items-center gap-0.5 flex-shrink-0", children: [previewable && ((0, jsx_runtime_1.jsx)("button", { onClick: handlePreview, className: "p-0.5 rounded hover:bg-ds-surface text-ds-muted hover:text-ds-accent transition-colors", title: t('sidebar.preview'), "aria-label": t('sidebar.preview'), children: (0, jsx_runtime_1.jsx)(lucide_react_1.Eye, { size: 12 }) })), exportable && ((0, jsx_runtime_1.jsxs)("div", { className: "relative", ref: exportMenuRef, children: [(0, jsx_runtime_1.jsx)("button", { onClick: (e) => {
                                    e.stopPropagation();
                                    setExportOpen((open) => !open);
                                }, disabled: exporting !== null, className: "p-0.5 rounded hover:bg-ds-surface text-ds-muted hover:text-ds-accent transition-colors disabled:opacity-50", title: t('sidebar.exportAs'), "aria-label": t('sidebar.exportAs'), children: exporting ? ((0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { size: 12, className: "animate-spin" })) : ((0, jsx_runtime_1.jsx)(lucide_react_1.Download, { size: 12 })) }), exportOpen && ((0, jsx_runtime_1.jsxs)("div", { className: "absolute right-0 top-full z-10 mt-1 w-36 rounded-md border border-ds-border bg-ds-surface shadow-lg", children: [(0, jsx_runtime_1.jsx)("div", { className: "px-2 py-1 text-[10px] uppercase tracking-wider text-ds-muted", children: t('sidebar.exportAs') }), exportTargets.map((target) => ((0, jsx_runtime_1.jsx)("button", { onClick: () => void handleExport(target.format), className: "flex w-full items-center px-2 py-1 text-left text-[11px] text-ds-text hover:bg-ds-bg", children: target.label }, target.format)))] }))] })), (0, jsx_runtime_1.jsx)("button", { onClick: handleDelete, disabled: busy, className: "p-0.5 rounded hover:bg-ds-surface text-ds-muted hover:text-red-400 transition-colors disabled:opacity-50", title: t('sidebar.delete'), "aria-label": t('sidebar.delete'), children: busy ? (0, jsx_runtime_1.jsx)(lucide_react_1.Loader2, { size: 12, className: "animate-spin" }) : (0, jsx_runtime_1.jsx)(lucide_react_1.Trash2, { size: 12 }) })] })] }));
}
