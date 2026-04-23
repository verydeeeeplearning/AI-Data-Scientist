"use strict";
/**
 * Files & Plots state — Zustand store for sidebar file explorer and plot gallery.
 *
 * Exposes three shapes of the same list:
 * - `files`: flat list (non-plot) with `modifiedAt` for sort-by-date
 * - `plots`: filtered subset for the PlotGallery
 * - `fileGroups` / `plotGroups`: grouped by top-level directory so the UI
 *   can render collapsible folder headers. Items at the workspace root land
 *   in the synthetic "" group.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.__test = exports.useFilesStore = void 0;
const zustand_1 = require("zustand");
const PLOT_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'svg', 'gif', 'webp', 'html']);
function isPlot(ext) {
    return PLOT_EXTENSIONS.has(ext.toLowerCase());
}
function topFolder(path) {
    const norm = path.replace(/\\/g, '/');
    const idx = norm.indexOf('/');
    return idx === -1 ? '' : norm.slice(0, idx);
}
function groupByFolder(entries) {
    const groups = new Map();
    for (const entry of entries) {
        const key = topFolder(entry.path);
        const bucket = groups.get(key);
        if (bucket) {
            bucket.push(entry);
        }
        else {
            groups.set(key, [entry]);
        }
    }
    // Root files ("") first, then named folders alphabetically
    return Array.from(groups.entries())
        .sort(([a], [b]) => (a === '' ? -1 : b === '' ? 1 : a.localeCompare(b)))
        .map(([folder, entries]) => ({ folder, entries }));
}
function buildDerived(rawFiles) {
    const nonPlots = rawFiles.filter((f) => !isPlot(f.type));
    const plots = rawFiles
        .filter((f) => isPlot(f.type))
        .map((f) => ({
        name: f.name,
        path: f.path,
        size: f.size,
        addedAt: Date.now(),
        modifiedAt: f.modifiedAt,
    }));
    return {
        files: rawFiles,
        plots,
        fileGroups: groupByFolder(nonPlots),
        plotGroups: groupByFolder(plots),
    };
}
exports.useFilesStore = (0, zustand_1.create)((set) => ({
    files: [],
    plots: [],
    fileGroups: [],
    plotGroups: [],
    loading: false,
    setFiles: (files) => set(buildDerived(files)),
    setLoading: (v) => set({ loading: v }),
    addFileFromEvent: (path, fileType, size) => {
        // 4.17 fix: Normalize Windows backslashes before splitting
        const normalizedPath = path.replace(/\\/g, '/');
        const name = normalizedPath.split('/').pop() ?? normalizedPath;
        const ext = name.includes('.') ? name.split('.').pop()?.toLowerCase() ?? '' : fileType;
        const entry = {
            name,
            path: normalizedPath,
            size,
            type: ext,
            modifiedAt: Date.now(),
        };
        set((s) => {
            // Replace any previous entry with the same path, otherwise append
            const existingIdx = s.files.findIndex((f) => f.path === entry.path);
            const next = existingIdx >= 0
                ? s.files.map((f, i) => (i === existingIdx ? entry : f))
                : [...s.files, entry];
            return buildDerived(next);
        });
    },
    removeFileByPath: (path) => {
        const normalized = path.replace(/\\/g, '/');
        set((s) => buildDerived(s.files.filter((f) => f.path !== normalized)));
    },
    clear: () => set({ files: [], plots: [], fileGroups: [], plotGroups: [] }),
}));
// Exported for tests.
exports.__test = { groupByFolder, topFolder, isPlot, buildDerived };
