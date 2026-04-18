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

import { create } from 'zustand';

export interface FileEntry {
  name: string;
  path: string;
  size: number;
  type: string; // extension without dot
  modifiedAt?: number; // ms since epoch
}

export interface PlotEntry {
  name: string;
  path: string;
  size: number;
  addedAt: number;
  modifiedAt?: number;
}

export interface FileGroup {
  folder: string; // "" for workspace root
  entries: FileEntry[];
}

export interface PlotGroup {
  folder: string;
  entries: PlotEntry[];
}

const PLOT_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'svg', 'gif', 'webp', 'html']);

function isPlot(ext: string): boolean {
  return PLOT_EXTENSIONS.has(ext.toLowerCase());
}

function topFolder(path: string): string {
  const norm = path.replace(/\\/g, '/');
  const idx = norm.indexOf('/');
  return idx === -1 ? '' : norm.slice(0, idx);
}

function groupByFolder<T extends { path: string }>(
  entries: T[]
): { folder: string; entries: T[] }[] {
  const groups = new Map<string, T[]>();
  for (const entry of entries) {
    const key = topFolder(entry.path);
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(entry);
    } else {
      groups.set(key, [entry]);
    }
  }
  // Root files ("") first, then named folders alphabetically
  return Array.from(groups.entries())
    .sort(([a], [b]) => (a === '' ? -1 : b === '' ? 1 : a.localeCompare(b)))
    .map(([folder, entries]) => ({ folder, entries }));
}

interface FilesState {
  files: FileEntry[];
  plots: PlotEntry[];
  fileGroups: FileGroup[];
  plotGroups: PlotGroup[];
  loading: boolean;

  setFiles: (files: FileEntry[]) => void;
  setLoading: (v: boolean) => void;
  addFileFromEvent: (path: string, fileType: string, size: number) => void;
  removeFileByPath: (path: string) => void;
  clear: () => void;
}

function buildDerived(rawFiles: FileEntry[]): {
  files: FileEntry[];
  plots: PlotEntry[];
  fileGroups: FileGroup[];
  plotGroups: PlotGroup[];
} {
  const nonPlots = rawFiles.filter((f) => !isPlot(f.type));
  const plots: PlotEntry[] = rawFiles
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

export const useFilesStore = create<FilesState>((set) => ({
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

    const entry: FileEntry = {
      name,
      path: normalizedPath,
      size,
      type: ext,
      modifiedAt: Date.now(),
    };

    set((s) => {
      // Replace any previous entry with the same path, otherwise append
      const existingIdx = s.files.findIndex((f) => f.path === entry.path);
      const next =
        existingIdx >= 0
          ? s.files.map((f, i) => (i === existingIdx ? entry : f))
          : [...s.files, entry];
      return buildDerived(next);
    });
  },

  removeFileByPath: (path) => {
    const normalized = path.replace(/\\/g, '/');
    set((s) => buildDerived(s.files.filter((f) => f.path !== normalized)));
  },

  clear: () =>
    set({ files: [], plots: [], fileGroups: [], plotGroups: [] }),
}));

// Exported for tests.
export const __test = { groupByFolder, topFolder, isPlot, buildDerived };
