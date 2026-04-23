"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.clampHeaderRow = clampHeaderRow;
exports.buildPreviewRequest = buildPreviewRequest;
exports.FilePreviewModal = FilePreviewModal;
const jsx_runtime_1 = require("react/jsx-runtime");
/**
 * FilePreviewModal renders the payload returned by the `files.preview` RPC.
 *
 * Supports:
 * - table: tabular previews with summary stats and column profiles
 * - text: truncated markdown / txt / json etc.
 * - binary/unknown: metadata only
 */
const react_1 = require("react");
const lucide_react_1 = require("lucide-react");
const primitives_1 = require("../../design-system/primitives");
const WsProvider_1 = require("../../hooks/WsProvider");
const PREVIEW_ROWS = 50;
function baseName(filePath) {
    return filePath.split(/[/\\]/).pop() ?? filePath;
}
function formatSize(bytes) {
    if (bytes < 1024)
        return `${bytes} B`;
    if (bytes < 1024 * 1024)
        return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
function iconFor(name) {
    const ext = name.split('.').pop()?.toLowerCase() ?? '';
    if (['csv', 'tsv', 'xlsx', 'xls', 'parquet', 'pq'].includes(ext))
        return lucide_react_1.FileSpreadsheet;
    if (['json', 'py', 'yaml', 'yml', 'toml'].includes(ext))
        return lucide_react_1.FileCode;
    if (['md', 'txt', 'log', 'ini'].includes(ext))
        return lucide_react_1.FileText;
    return lucide_react_1.File;
}
function clampHeaderRow(value) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed) || Number.isNaN(parsed)) {
        return 1;
    }
    return Math.min(Math.max(parsed, 1), 50);
}
function buildPreviewRequest(path, headerRow, sheetName) {
    const request = {
        path,
        rows: PREVIEW_ROWS,
        headerRow,
    };
    if (sheetName) {
        request.sheetName = sheetName;
    }
    return request;
}
function FilePreviewModal({ path, onClose }) {
    const { rpc } = (0, WsProvider_1.useWs)();
    const [payload, setPayload] = (0, react_1.useState)(null);
    const [error, setError] = (0, react_1.useState)(null);
    const [loading, setLoading] = (0, react_1.useState)(true);
    const [selectedSheet, setSelectedSheet] = (0, react_1.useState)('');
    const [headerRowDraft, setHeaderRowDraft] = (0, react_1.useState)('1');
    const [appliedSheet, setAppliedSheet] = (0, react_1.useState)(null);
    const [appliedHeaderRow, setAppliedHeaderRow] = (0, react_1.useState)(1);
    const restoreFocusRef = (0, react_1.useRef)(null);
    const generatedId = (0, react_1.useId)().replace(/:/g, '');
    const dialogId = `file-preview-dialog-${generatedId}`;
    const titleId = `${dialogId}-title`;
    const descriptionId = `${dialogId}-description`;
    const statusId = `${dialogId}-status`;
    const fileName = (0, react_1.useMemo)(() => baseName(path), [path]);
    const ext = (0, react_1.useMemo)(() => fileName.split('.').pop()?.toLowerCase() ?? '', [fileName]);
    const isExcel = ext === 'xlsx' || ext === 'xls';
    (0, react_1.useEffect)(() => {
        setPayload(null);
        setError(null);
        setSelectedSheet('');
        setHeaderRowDraft('1');
        setAppliedSheet(null);
        setAppliedHeaderRow(1);
    }, [path]);
    (0, react_1.useEffect)(() => {
        restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        const frame = window.requestAnimationFrame(() => {
            const dialog = document.getElementById(dialogId);
            if (dialog instanceof HTMLElement) {
                dialog.focus();
            }
        });
        return () => {
            window.cancelAnimationFrame(frame);
            restoreFocusRef.current?.focus();
        };
    }, [dialogId]);
    (0, react_1.useEffect)(() => {
        const handleKey = (event) => {
            if (event.key === 'Escape') {
                onClose();
            }
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [onClose]);
    (0, react_1.useEffect)(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        rpc('files.preview', buildPreviewRequest(path, appliedHeaderRow, appliedSheet))
            .then((data) => {
            if (!cancelled) {
                setPayload(data);
            }
        })
            .catch((err) => {
            if (!cancelled) {
                setError(String(err?.message ?? err));
            }
        })
            .finally(() => {
            if (!cancelled) {
                setLoading(false);
            }
        });
        return () => {
            cancelled = true;
        };
    }, [appliedHeaderRow, appliedSheet, path, rpc]);
    (0, react_1.useEffect)(() => {
        if (payload?.kind !== 'table') {
            return;
        }
        if (payload.selectedSheet) {
            setSelectedSheet(payload.selectedSheet);
        }
        if (appliedSheet === null && payload.selectedSheet) {
            setAppliedSheet(payload.selectedSheet);
        }
        setHeaderRowDraft(String(payload.headerRow ?? 1));
    }, [appliedSheet, payload]);
    const Icon = iconFor(fileName);
    const effectiveSelectedSheet = selectedSheet || (payload?.kind === 'table' ? payload.selectedSheet ?? '' : '');
    const canApplyWizard = !loading
        && (effectiveSelectedSheet !== (appliedSheet ?? '') || clampHeaderRow(headerRowDraft) !== appliedHeaderRow);
    const payloadSize = payload && 'size' in payload ? payload.size : null;
    const description = payload?.kind === 'table'
        ? 'Preview the sampled rows, schema details, and spreadsheet controls before analysis.'
        : 'Preview file contents and metadata before analysis.';
    return ((0, jsx_runtime_1.jsx)("div", { className: "fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-ds-4", onClick: onClose, children: (0, jsx_runtime_1.jsxs)(primitives_1.Card, { id: dialogId, role: "dialog", "aria-modal": "true", "aria-labelledby": titleId, "aria-describedby": (0, primitives_1.joinIds)(descriptionId, statusId), tabIndex: -1, className: "relative flex max-h-[85vh] w-[min(92vw,1100px)] flex-col overflow-hidden border-ds-border bg-ds-surface p-0 shadow-2xl", onClick: (event) => event.stopPropagation(), children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center gap-ds-2 border-b border-ds-border px-ds-4 py-ds-3", children: [(0, jsx_runtime_1.jsx)(Icon, { size: 16, className: "text-ds-muted", "aria-hidden": "true" }), (0, jsx_runtime_1.jsxs)("div", { className: "min-w-0 flex-1", children: [(0, jsx_runtime_1.jsx)("div", { id: titleId, className: "truncate text-ds-sm font-medium text-ds-text", children: fileName }), (0, jsx_runtime_1.jsx)("div", { id: descriptionId, className: "mt-ds-1 text-ds-xs text-ds-muted", children: description })] }), payloadSize != null ? ((0, jsx_runtime_1.jsx)(primitives_1.Badge, { compact: true, tone: "neutral", children: formatSize(payloadSize) })) : null, (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "ghost", size: "sm", "aria-label": "Close preview", className: "h-8 min-h-8 w-8 rounded-ds-md px-0 shadow-none", onClick: onClose, children: (0, jsx_runtime_1.jsx)(lucide_react_1.X, { size: 16, "aria-hidden": "true" }) })] }), (0, jsx_runtime_1.jsxs)("div", { className: "flex-1 overflow-auto p-ds-4", children: [(0, jsx_runtime_1.jsx)("div", { id: statusId, className: "sr-only", "aria-live": "polite", children: loading
                                ? 'Loading preview'
                                : error
                                    ? `Preview failed: ${error}`
                                    : payload?.kind === 'table'
                                        ? 'Tabular preview loaded'
                                        : 'Preview loaded' }), loading ? ((0, jsx_runtime_1.jsx)(primitives_1.Card, { className: "bg-ds-bg/40 text-ds-sm text-ds-muted shadow-none", children: "Loading preview..." })) : null, error ? ((0, jsx_runtime_1.jsxs)(primitives_1.Card, { tone: "danger", className: "text-ds-sm shadow-none", children: ["Failed to load: ", error] })) : null, !loading && !error && payload?.kind === 'table' ? ((0, jsx_runtime_1.jsx)(TablePreview, { payload: payload, isExcel: isExcel, selectedSheet: selectedSheet, onSelectSheet: setSelectedSheet, headerRowDraft: headerRowDraft, onChangeHeaderRow: setHeaderRowDraft, onApply: () => {
                                setAppliedSheet(selectedSheet || payload.selectedSheet || null);
                                setAppliedHeaderRow(clampHeaderRow(headerRowDraft));
                            }, canApplyWizard: canApplyWizard })) : null, !loading && !error && payload?.kind === 'text' ? ((0, jsx_runtime_1.jsxs)(primitives_1.Card, { className: "space-y-ds-3 bg-ds-bg/30 shadow-none", children: [(0, jsx_runtime_1.jsx)("pre", { className: "whitespace-pre-wrap break-words font-mono text-[12px] text-ds-text/90", children: payload.content }), payload.truncated ? ((0, jsx_runtime_1.jsx)(primitives_1.Badge, { compact: true, tone: "warning", children: "Truncated at 256 KB" })) : null] })) : null, !loading && !error && (payload?.kind === 'binary' || payload?.kind === 'unknown') ? ((0, jsx_runtime_1.jsxs)(primitives_1.Card, { className: "space-y-ds-2 bg-ds-bg/30 text-ds-sm text-ds-muted shadow-none", children: [(0, jsx_runtime_1.jsx)("div", { children: "Binary file. Inline preview is not available." }), 'message' in payload && payload.message ? ((0, jsx_runtime_1.jsx)("div", { className: "text-ds-xs", children: payload.message })) : null] })) : null, !loading && !error && payload?.kind === 'error' ? ((0, jsx_runtime_1.jsx)(primitives_1.Card, { tone: "danger", className: "text-ds-sm shadow-none", children: payload.error })) : null] })] }) }));
}
function TablePreview({ payload, isExcel, selectedSheet, onSelectSheet, headerRowDraft, onChangeHeaderRow, onApply, canApplyWizard, }) {
    const columnProfiles = payload.columnProfiles ?? [];
    const hasNulls = columnProfiles.some((column) => column.nullCount > 0);
    const showExcelWizard = isExcel && (payload.sheetNames?.length ?? 0) > 0;
    return ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-4", children: [showExcelWizard ? ((0, jsx_runtime_1.jsxs)(primitives_1.Card, { className: "space-y-ds-3 bg-ds-bg/40 shadow-none", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] font-medium uppercase tracking-wider text-ds-muted", children: "Excel preview" }), (0, jsx_runtime_1.jsxs)("div", { className: "grid gap-ds-3 sm:grid-cols-[minmax(0,1fr)_180px_auto]", children: [(0, jsx_runtime_1.jsx)(primitives_1.Select, { label: "Sheet", options: (payload.sheetNames ?? []).map((sheetName) => ({
                                    value: sheetName,
                                    label: sheetName,
                                })), value: selectedSheet || payload.selectedSheet || payload.sheetNames?.[0] || '', onChange: (event) => onSelectSheet(event.target.value) }), (0, jsx_runtime_1.jsx)(primitives_1.Input, { label: "Header row", type: "number", min: 1, max: 50, value: headerRowDraft, onChange: (event) => onChangeHeaderRow(event.target.value) }), (0, jsx_runtime_1.jsx)("div", { className: "flex items-end", children: (0, jsx_runtime_1.jsx)(primitives_1.Button, { variant: "secondary", size: "md", className: "w-full rounded-ds-lg px-ds-4", disabled: !canApplyWizard, onClick: onApply, children: "Apply" }) })] })] })) : null, (0, jsx_runtime_1.jsxs)("div", { className: "grid gap-ds-2 sm:grid-cols-2 xl:grid-cols-4", children: [(0, jsx_runtime_1.jsx)(SummaryCard, { label: "Rows", value: payload.rowCount != null
                            ? payload.rowCount.toLocaleString()
                            : `${payload.previewRows.toLocaleString()} preview` }), (0, jsx_runtime_1.jsx)(SummaryCard, { label: "Columns", value: payload.columns.length.toString() }), (0, jsx_runtime_1.jsx)(SummaryCard, { label: "File size", value: typeof payload.fileSizeMb === 'number'
                            ? `${payload.fileSizeMb.toFixed(2)} MB`
                            : formatSize(payload.size) }), (0, jsx_runtime_1.jsx)(SummaryCard, { label: payload.selectedSheet ? 'Sheet' : 'Encoding', value: payload.selectedSheet ?? payload.encodingDetected ?? 'Detected automatically' })] }), hasNulls ? ((0, jsx_runtime_1.jsx)(primitives_1.Card, { tone: "accent", className: "text-[11px] text-ds-muted shadow-none", children: "Blank values were detected in this preview. The agent can still analyze the file, but it may clean or impute missing values during preparation." })) : null, payload.selectedSheet && (payload.sheetNames?.length ?? 0) > 1 ? ((0, jsx_runtime_1.jsxs)("div", { className: "text-[11px] text-ds-muted", children: ["Previewing sheet ", (0, jsx_runtime_1.jsx)("span", { className: "font-medium text-ds-text", children: payload.selectedSheet }), ' ', "of ", payload.sheetNames?.length, " sheets."] })) : null, (0, jsx_runtime_1.jsx)("div", { className: "overflow-auto rounded-ds-xl border border-ds-border", children: (0, jsx_runtime_1.jsxs)("table", { className: "w-full border-collapse text-[11px]", children: [(0, jsx_runtime_1.jsxs)("caption", { className: "sr-only", children: ["Preview table for ", payload.path, " showing ", payload.previewRows, " rows."] }), (0, jsx_runtime_1.jsx)("thead", { className: "sticky top-0 bg-ds-surface", children: (0, jsx_runtime_1.jsx)("tr", { children: payload.columns.map((column) => ((0, jsx_runtime_1.jsx)("th", { className: "whitespace-nowrap border-b border-ds-border px-ds-2 py-ds-2 text-left font-medium text-ds-text", scope: "col", children: column }, column))) }) }), (0, jsx_runtime_1.jsx)("tbody", { children: payload.rows.map((row, rowIndex) => ((0, jsx_runtime_1.jsx)("tr", { className: "hover:bg-ds-bg/50", children: row.map((cell, cellIndex) => ((0, jsx_runtime_1.jsx)("td", { className: "whitespace-nowrap border-b border-ds-border/40 px-ds-2 py-ds-2 text-ds-text/80", children: cell || (0, jsx_runtime_1.jsx)("span", { className: "text-ds-muted/50", children: "empty" }) }, `${payload.columns[cellIndex] ?? cellIndex}-${rowIndex}`))) }, `${payload.path}-${rowIndex}`))) })] }) }), columnProfiles.length > 0 ? ((0, jsx_runtime_1.jsxs)("div", { className: "space-y-ds-2", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[11px] font-medium uppercase tracking-wider text-ds-muted", children: "Column profile" }), (0, jsx_runtime_1.jsx)("div", { className: "grid gap-ds-2 lg:grid-cols-2", children: columnProfiles.map((column) => ((0, jsx_runtime_1.jsxs)(primitives_1.Card, { className: "bg-ds-bg/40 shadow-none", children: [(0, jsx_runtime_1.jsxs)("div", { className: "flex items-center justify-between gap-ds-2", children: [(0, jsx_runtime_1.jsx)("div", { className: "truncate text-xs font-medium text-ds-text", children: column.name }), (0, jsx_runtime_1.jsx)(primitives_1.Badge, { compact: true, tone: "neutral", children: column.dtype })] }), (0, jsx_runtime_1.jsxs)("div", { className: "mt-ds-2 flex flex-wrap gap-ds-2 text-[10px] text-ds-muted", children: [(0, jsx_runtime_1.jsxs)("span", { children: [column.nullCount, " nulls"] }), (0, jsx_runtime_1.jsxs)("span", { children: [column.uniqueCount, " unique"] })] }), (0, jsx_runtime_1.jsx)("div", { className: "mt-ds-2 text-[10px] text-ds-muted", children: column.sampleValues.length > 0 ? ((0, jsx_runtime_1.jsxs)(jsx_runtime_1.Fragment, { children: ["Samples: ", column.sampleValues.join(', ')] })) : ('Samples: none in preview') })] }, column.name))) })] })) : null, (0, jsx_runtime_1.jsxs)("div", { className: "text-[11px] text-ds-muted", children: ["Showing ", payload.previewRows, payload.totalRows != null ? ` of ${payload.totalRows}` : '', " rows and ", payload.columns.length, ' ', "columns."] })] }));
}
function SummaryCard({ label, value }) {
    return ((0, jsx_runtime_1.jsxs)(primitives_1.Card, { className: "bg-ds-bg/40 px-ds-3 py-ds-3 shadow-none", children: [(0, jsx_runtime_1.jsx)("div", { className: "text-[10px] uppercase tracking-wider text-ds-muted", children: label }), (0, jsx_runtime_1.jsx)("div", { className: "mt-ds-1 text-ds-sm font-medium text-ds-text", children: value })] }));
}
