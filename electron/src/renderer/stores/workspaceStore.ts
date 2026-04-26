import { create } from 'zustand';
import type { ResultCardType } from '../types/events';
import {
  DEFAULT_AUDIENCE_VIEW,
  isAudienceView,
  type AudienceView,
} from '../domain/workspace/audienceView';
import {
  buildWorkspaceExportCandidates,
} from '../application/workspace/buildWorkspaceExportCandidates';
import type { FileEntry, PlotEntry } from './filesStore';

export const EVIDENCE_WORKSPACE_TABS = [
  'overview',
  'export',
] as const;

export const WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY = 'ds-agent-workspace-audience-view';

/**
 * Minimal Storage-like surface so the audience-view persistence helpers can
 * be exercised under Node (contract tests) without depending on the DOM.
 */
export interface AudienceViewStorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

let audienceViewStorageOverride: AudienceViewStorageLike | null = null;

function resolveAudienceViewStorage(): AudienceViewStorageLike | null {
  if (audienceViewStorageOverride) {
    return audienceViewStorageOverride;
  }
  try {
    if (typeof localStorage !== 'undefined') {
      return localStorage;
    }
  } catch {
    return null;
  }
  return null;
}

export function loadAudienceView(): AudienceView {
  const storage = resolveAudienceViewStorage();
  if (!storage) {
    return DEFAULT_AUDIENCE_VIEW;
  }
  try {
    const raw = storage.getItem(WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY);
    if (isAudienceView(raw)) {
      return raw;
    }
  } catch {
    // fall through to default
  }
  return DEFAULT_AUDIENCE_VIEW;
}

export function persistAudienceView(view: AudienceView): void {
  const storage = resolveAudienceViewStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY, view);
  } catch {
    // ignore: persistence is best-effort
  }
}

/**
 * Test seam: install a fake Storage so reducers can be exercised in Node.
 * Pass `null` to restore the default (real `localStorage`) lookup.
 */
export function __setAudienceViewStorageForTests(storage: AudienceViewStorageLike | null): void {
  audienceViewStorageOverride = storage;
}

export type EvidenceWorkspaceTab = (typeof EVIDENCE_WORKSPACE_TABS)[number];
export type WorkspaceReadModelStatus = 'loading' | 'ready';
export type WorkspacePinnedProjectionStatus = 'empty' | 'count_only' | 'ready';
export type WorkspacePinnedSelectionTarget = 'card' | 'result' | 'message';

export interface WorkspaceSectionSummary {
  id: EvidenceWorkspaceTab;
  label: string;
  description: string;
  itemCount: number;
  hasContent: boolean;
}

export interface WorkspaceExportCandidate {
  id: string;
  name: string;
  path: string;
  type: string;
  formats: readonly string[];
  sourceKind: 'file' | 'plot';
}

export interface WorkspaceArtifactsSnapshot {
  files: FileEntry[];
  plots: PlotEntry[];
  loading: boolean;
}

export interface WorkspacePinnedCardSource {
  messageId: string;
  runId: string;
  toolCallId?: string | null;
}

export interface WorkspacePinnedCardInput {
  cardId: string;
  resultId: string;
  type: ResultCardType;
  createdAt: number;
  source: WorkspacePinnedCardSource;
  pinned: boolean;
  archived?: boolean;
  [key: string]: unknown;
}

export interface WorkspacePinnedProjectionItem {
  cardId: string;
  resultId: string;
  messageId: string;
  runId: string;
  toolCallId: string | null;
  type: ResultCardType;
  createdAt: number;
  title: string;
  summary: string | null;
  artifactPath: string | null;
}

export interface WorkspacePinnedSnapshot {
  items: WorkspacePinnedCardInput[];
  fallbackCount: number;
}

export interface WorkspaceReadModel {
  status: WorkspaceReadModelStatus;
  nonPlotFileCount: number;
  plotCount: number;
  tableCount: number;
  pinnedCardCount: number;
  pinnedProjectionStatus: WorkspacePinnedProjectionStatus;
  exportCandidateCount: number;
  sections: WorkspaceSectionSummary[];
  tableFiles: FileEntry[];
  recentFiles: FileEntry[];
  pinnedItems: WorkspacePinnedProjectionItem[];
  exportCandidates: WorkspaceExportCandidate[];
  lastUpdatedAt: number | null;
}

interface WorkspaceState {
  activeTab: EvidenceWorkspaceTab;
  audienceView: AudienceView;
  pinnedSnapshot: WorkspacePinnedSnapshot;
  artifactSnapshot: WorkspaceArtifactsSnapshot;
  readModel: WorkspaceReadModel;
  setActiveTab: (tab: EvidenceWorkspaceTab) => void;
  setAudienceView: (view: AudienceView) => void;
  setPinnedCardCount: (count: number) => void;
  syncPinnedItems: (items: WorkspacePinnedCardInput[]) => void;
  syncFromArtifacts: (snapshot: WorkspaceArtifactsSnapshot) => void;
  reset: () => void;
}

const TABLE_EXTENSIONS = new Set(['csv', 'tsv', 'xlsx', 'xls', 'parquet', 'pq']);

const EMPTY_SNAPSHOT: WorkspaceArtifactsSnapshot = {
  files: [],
  plots: [],
  loading: false,
};

const EMPTY_PINNED_SNAPSHOT: WorkspacePinnedSnapshot = {
  items: [],
  fallbackCount: 0,
};

const TITLE_KEYS = ['title', 'headline', 'name', 'label', 'artifactLabel'] as const;
const SUMMARY_KEYS = ['summary', 'description', 'insight', 'text', 'note', 'caption'] as const;
const ARTIFACT_PATH_KEYS = ['artifactPath', 'artifact_path', 'filePath', 'file_path', 'path'] as const;

export function isEvidenceWorkspaceTab(value: string | undefined | null): value is EvidenceWorkspaceTab {
  return value != null && EVIDENCE_WORKSPACE_TABS.includes(value as EvidenceWorkspaceTab);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function normalizePinnedFallbackCount(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.floor(value));
}

function formatPinnedTypeLabel(type: ResultCardType): string {
  return type.charAt(0).toUpperCase() + type.slice(1);
}

function pickFirstString(values: readonly unknown[]): string | null {
  for (const value of values) {
    if (isNonEmptyString(value)) {
      return value.trim();
    }
  }
  return null;
}

function truncateText(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }
  return `${value.slice(0, maxLength - 1).trimEnd()}...`;
}

function normalizePinnedCreatedAt(value: number): number {
  if (!Number.isFinite(value)) {
    return Date.now();
  }
  return value >= 1_000_000_000_000 ? value : value * 1000;
}

function buildSection(
  id: EvidenceWorkspaceTab,
  label: string,
  description: string,
  itemCount: number,
  hasContent: boolean,
): WorkspaceSectionSummary {
  return {
    id,
    label,
    description,
    itemCount,
    hasContent,
  };
}

function deriveLatestTimestamp(
  files: FileEntry[],
  plots: PlotEntry[],
  pinnedItems: WorkspacePinnedProjectionItem[],
): number | null {
  let latest: number | null = null;

  for (const file of files) {
    if (file.modifiedAt == null) {
      continue;
    }
    latest = latest == null || file.modifiedAt > latest ? file.modifiedAt : latest;
  }

  for (const plot of plots) {
    const candidate = plot.modifiedAt ?? plot.addedAt;
    latest = latest == null || candidate > latest ? candidate : latest;
  }

  for (const item of pinnedItems) {
    latest = latest == null || item.createdAt > latest ? item.createdAt : latest;
  }

  return latest;
}

function derivePinnedArtifactPath(card: WorkspacePinnedCardInput): string | null {
  return pickFirstString(ARTIFACT_PATH_KEYS.map((key) => card[key]));
}

function derivePinnedTitle(
  card: WorkspacePinnedCardInput,
  artifactPath: string | null,
): string {
  const artifactName = artifactPath?.split(/[\\/]/).pop() ?? null;
  const title = pickFirstString([
    ...TITLE_KEYS.map((key) => card[key]),
    artifactName,
  ]);

  return title ?? `${formatPinnedTypeLabel(card.type)} result`;
}

function derivePinnedSummary(
  card: WorkspacePinnedCardInput,
  artifactPath: string | null,
): string | null {
  const summary = pickFirstString([
    ...SUMMARY_KEYS.map((key) => card[key]),
    artifactPath ? `Artifact path: ${artifactPath}` : null,
  ]);

  return summary ? truncateText(summary, 220) : null;
}

export function buildWorkspacePinnedProjectionItem(
  card: WorkspacePinnedCardInput,
): WorkspacePinnedProjectionItem {
  const artifactPath = derivePinnedArtifactPath(card);

  return {
    cardId: card.cardId,
    resultId: card.resultId,
    messageId: card.source.messageId,
    runId: card.source.runId,
    toolCallId: card.source.toolCallId ?? null,
    type: card.type,
    createdAt: normalizePinnedCreatedAt(card.createdAt),
    title: derivePinnedTitle(card, artifactPath),
    summary: derivePinnedSummary(card, artifactPath),
    artifactPath,
  };
}

export function buildWorkspacePinnedProjection(
  snapshot: WorkspacePinnedSnapshot,
): {
  count: number;
  status: WorkspacePinnedProjectionStatus;
  items: WorkspacePinnedProjectionItem[];
} {
  const itemsById: Record<string, WorkspacePinnedProjectionItem> = {};

  for (const card of snapshot.items) {
    if (!card.pinned || card.archived === true) {
      continue;
    }
    itemsById[card.cardId] = buildWorkspacePinnedProjectionItem(card);
  }

  const items = Object.values(itemsById).sort((left, right) => {
    if (left.createdAt !== right.createdAt) {
      return right.createdAt - left.createdAt;
    }
    return left.cardId.localeCompare(right.cardId);
  });

  if (items.length > 0) {
    return {
      count: items.length,
      status: 'ready',
      items,
    };
  }

  const fallbackCount = normalizePinnedFallbackCount(snapshot.fallbackCount);
  return {
    count: fallbackCount,
    status: fallbackCount > 0 ? 'count_only' : 'empty',
    items: [],
  };
}

export function matchesWorkspacePinnedItem(
  item: WorkspacePinnedProjectionItem,
  target: WorkspacePinnedSelectionTarget,
  value: string,
): boolean {
  switch (target) {
    case 'card':
      return item.cardId === value;
    case 'result':
      return item.resultId === value;
    case 'message':
      return item.messageId === value;
    default:
      return false;
  }
}

export function findWorkspacePinnedItem(
  items: WorkspacePinnedProjectionItem[],
  target: WorkspacePinnedSelectionTarget,
  value: string,
): WorkspacePinnedProjectionItem | null {
  return items.find((item) => matchesWorkspacePinnedItem(item, target, value)) ?? null;
}

export function buildWorkspaceReadModel(
  snapshot: WorkspaceArtifactsSnapshot,
  pinnedSnapshot: WorkspacePinnedSnapshot,
): WorkspaceReadModel {
  const plotPaths = new Set(snapshot.plots.map((plot) => plot.path));
  const nonPlotFiles = snapshot.files.filter((file) => !plotPaths.has(file.path));
  const tableFiles = nonPlotFiles.filter((file) => TABLE_EXTENSIONS.has(file.type.toLowerCase()));
  const pinnedProjection = buildWorkspacePinnedProjection(pinnedSnapshot);
  const exportCandidates = buildWorkspaceExportCandidates(snapshot);

  const hasArtifacts = nonPlotFiles.length > 0 || snapshot.plots.length > 0;
  const exportCandidateCount = exportCandidates.length;

  return {
    status: snapshot.loading && !hasArtifacts ? 'loading' : 'ready',
    nonPlotFileCount: nonPlotFiles.length,
    plotCount: snapshot.plots.length,
    tableCount: tableFiles.length,
    pinnedCardCount: pinnedProjection.count,
    pinnedProjectionStatus: pinnedProjection.status,
    exportCandidateCount,
    sections: [
      buildSection(
        'overview',
        'Overview',
        'Workspace readiness, pinned evidence projection, and artifact coverage.',
        pinnedProjection.count + (hasArtifacts ? 1 : 0),
        hasArtifacts || pinnedProjection.count > 0,
      ),
      buildSection(
        'export',
        'Export',
        'Run-level export scaffolding built from currently export-capable local artifacts.',
        exportCandidateCount,
        exportCandidateCount > 0,
      ),
    ],
    tableFiles,
    recentFiles: [...nonPlotFiles]
      .sort((left, right) => (right.modifiedAt ?? 0) - (left.modifiedAt ?? 0))
      .slice(0, 5),
    pinnedItems: pinnedProjection.items,
    exportCandidates,
    lastUpdatedAt: deriveLatestTimestamp(nonPlotFiles, snapshot.plots, pinnedProjection.items),
  };
}

const INITIAL_READ_MODEL = buildWorkspaceReadModel(EMPTY_SNAPSHOT, EMPTY_PINNED_SNAPSHOT);

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  activeTab: 'overview',
  audienceView: loadAudienceView(),
  pinnedSnapshot: EMPTY_PINNED_SNAPSHOT,
  artifactSnapshot: EMPTY_SNAPSHOT,
  readModel: INITIAL_READ_MODEL,

  setActiveTab: (tab) => set({ activeTab: tab }),

  setAudienceView: (view) => {
    if (!isAudienceView(view)) {
      return;
    }
    persistAudienceView(view);
    set({ audienceView: view });
  },

  setPinnedCardCount: (count) =>
    set((state) => {
      const pinnedSnapshot = {
        items: state.pinnedSnapshot.items,
        fallbackCount: normalizePinnedFallbackCount(count),
      };

      return {
        pinnedSnapshot,
        readModel: buildWorkspaceReadModel(state.artifactSnapshot, pinnedSnapshot),
      };
    }),

  syncPinnedItems: (items) =>
    set((state) => {
      const pinnedSnapshot = {
        items: [...items],
        fallbackCount: state.pinnedSnapshot.fallbackCount,
      };

      return {
        pinnedSnapshot,
        readModel: buildWorkspaceReadModel(state.artifactSnapshot, pinnedSnapshot),
      };
    }),

  syncFromArtifacts: (snapshot) =>
    set((state) => ({
      artifactSnapshot: snapshot,
      readModel: buildWorkspaceReadModel(snapshot, state.pinnedSnapshot),
    })),

  reset: () =>
    set({
      activeTab: 'overview',
      audienceView: loadAudienceView(),
      pinnedSnapshot: EMPTY_PINNED_SNAPSHOT,
      artifactSnapshot: EMPTY_SNAPSHOT,
      readModel: INITIAL_READ_MODEL,
    }),
}));

export const __test = {
  buildWorkspacePinnedProjection,
  buildWorkspacePinnedProjectionItem,
  buildWorkspaceReadModel,
  findWorkspacePinnedItem,
  isEvidenceWorkspaceTab,
  matchesWorkspacePinnedItem,
};
