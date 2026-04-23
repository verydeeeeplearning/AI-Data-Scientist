"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.__test = exports.useWorkspaceStore = exports.WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY = exports.EVIDENCE_WORKSPACE_TABS = void 0;
exports.loadAudienceView = loadAudienceView;
exports.persistAudienceView = persistAudienceView;
exports.__setAudienceViewStorageForTests = __setAudienceViewStorageForTests;
exports.isEvidenceWorkspaceTab = isEvidenceWorkspaceTab;
exports.buildWorkspacePinnedProjectionItem = buildWorkspacePinnedProjectionItem;
exports.buildWorkspacePinnedProjection = buildWorkspacePinnedProjection;
exports.matchesWorkspacePinnedItem = matchesWorkspacePinnedItem;
exports.findWorkspacePinnedItem = findWorkspacePinnedItem;
exports.buildWorkspaceReadModel = buildWorkspaceReadModel;
const zustand_1 = require("zustand");
const audienceView_1 = require("../domain/workspace/audienceView");
const buildWorkspaceExportCandidates_1 = require("../application/workspace/buildWorkspaceExportCandidates");
exports.EVIDENCE_WORKSPACE_TABS = [
    'summary',
    'tables',
    'charts',
    'files',
    'export',
];
exports.WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY = 'ds-agent-workspace-audience-view';
let audienceViewStorageOverride = null;
function resolveAudienceViewStorage() {
    if (audienceViewStorageOverride) {
        return audienceViewStorageOverride;
    }
    try {
        if (typeof localStorage !== 'undefined') {
            return localStorage;
        }
    }
    catch {
        return null;
    }
    return null;
}
function loadAudienceView() {
    const storage = resolveAudienceViewStorage();
    if (!storage) {
        return audienceView_1.DEFAULT_AUDIENCE_VIEW;
    }
    try {
        const raw = storage.getItem(exports.WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY);
        if ((0, audienceView_1.isAudienceView)(raw)) {
            return raw;
        }
    }
    catch {
        // fall through to default
    }
    return audienceView_1.DEFAULT_AUDIENCE_VIEW;
}
function persistAudienceView(view) {
    const storage = resolveAudienceViewStorage();
    if (!storage) {
        return;
    }
    try {
        storage.setItem(exports.WORKSPACE_AUDIENCE_VIEW_STORAGE_KEY, view);
    }
    catch {
        // ignore: persistence is best-effort
    }
}
/**
 * Test seam: install a fake Storage so reducers can be exercised in Node.
 * Pass `null` to restore the default (real `localStorage`) lookup.
 */
function __setAudienceViewStorageForTests(storage) {
    audienceViewStorageOverride = storage;
}
const TABLE_EXTENSIONS = new Set(['csv', 'tsv', 'xlsx', 'xls', 'parquet', 'pq']);
const EMPTY_SNAPSHOT = {
    files: [],
    plots: [],
    loading: false,
};
const EMPTY_PINNED_SNAPSHOT = {
    items: [],
    fallbackCount: 0,
};
const TITLE_KEYS = ['title', 'headline', 'name', 'label', 'artifactLabel'];
const SUMMARY_KEYS = ['summary', 'description', 'insight', 'text', 'note', 'caption'];
const ARTIFACT_PATH_KEYS = ['artifactPath', 'artifact_path', 'filePath', 'file_path', 'path'];
function isEvidenceWorkspaceTab(value) {
    return value != null && exports.EVIDENCE_WORKSPACE_TABS.includes(value);
}
function isNonEmptyString(value) {
    return typeof value === 'string' && value.trim().length > 0;
}
function normalizePinnedFallbackCount(value) {
    if (!Number.isFinite(value)) {
        return 0;
    }
    return Math.max(0, Math.floor(value));
}
function formatPinnedTypeLabel(type) {
    return type.charAt(0).toUpperCase() + type.slice(1);
}
function pickFirstString(values) {
    for (const value of values) {
        if (isNonEmptyString(value)) {
            return value.trim();
        }
    }
    return null;
}
function truncateText(value, maxLength) {
    if (value.length <= maxLength) {
        return value;
    }
    return `${value.slice(0, maxLength - 1).trimEnd()}...`;
}
function normalizePinnedCreatedAt(value) {
    if (!Number.isFinite(value)) {
        return Date.now();
    }
    return value >= 1000000000000 ? value : value * 1000;
}
function buildSection(id, label, description, itemCount, hasContent) {
    return {
        id,
        label,
        description,
        itemCount,
        hasContent,
    };
}
function deriveLatestTimestamp(files, plots, pinnedItems) {
    let latest = null;
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
function derivePinnedArtifactPath(card) {
    return pickFirstString(ARTIFACT_PATH_KEYS.map((key) => card[key]));
}
function derivePinnedTitle(card, artifactPath) {
    const artifactName = artifactPath?.split(/[\\/]/).pop() ?? null;
    const title = pickFirstString([
        ...TITLE_KEYS.map((key) => card[key]),
        artifactName,
    ]);
    return title ?? `${formatPinnedTypeLabel(card.type)} result`;
}
function derivePinnedSummary(card, artifactPath) {
    const summary = pickFirstString([
        ...SUMMARY_KEYS.map((key) => card[key]),
        artifactPath ? `Artifact path: ${artifactPath}` : null,
    ]);
    return summary ? truncateText(summary, 220) : null;
}
function buildWorkspacePinnedProjectionItem(card) {
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
function buildWorkspacePinnedProjection(snapshot) {
    const itemsById = {};
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
function matchesWorkspacePinnedItem(item, target, value) {
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
function findWorkspacePinnedItem(items, target, value) {
    return items.find((item) => matchesWorkspacePinnedItem(item, target, value)) ?? null;
}
function buildWorkspaceReadModel(snapshot, pinnedSnapshot) {
    const plotPaths = new Set(snapshot.plots.map((plot) => plot.path));
    const nonPlotFiles = snapshot.files.filter((file) => !plotPaths.has(file.path));
    const tableFiles = nonPlotFiles.filter((file) => TABLE_EXTENSIONS.has(file.type.toLowerCase()));
    const pinnedProjection = buildWorkspacePinnedProjection(pinnedSnapshot);
    const exportCandidates = (0, buildWorkspaceExportCandidates_1.buildWorkspaceExportCandidates)(snapshot);
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
            buildSection('summary', 'Summary', 'Workspace readiness, pinned evidence projection, and artifact coverage.', pinnedProjection.count + (hasArtifacts ? 1 : 0), hasArtifacts || pinnedProjection.count > 0),
            buildSection('tables', 'Tables', 'Structured datasets and metric tables discoverable from current artifacts.', tableFiles.length, tableFiles.length > 0),
            buildSection('charts', 'Charts', 'Plot gallery surface backed by locally available chart artifacts.', snapshot.plots.length, snapshot.plots.length > 0),
            buildSection('files', 'Files', 'Workspace file system view for uploaded and generated evidence.', nonPlotFiles.length, nonPlotFiles.length > 0),
            buildSection('export', 'Export', 'Run-level export scaffolding built from currently export-capable local artifacts.', exportCandidateCount, exportCandidateCount > 0),
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
exports.useWorkspaceStore = (0, zustand_1.create)((set) => ({
    activeTab: 'summary',
    audienceView: loadAudienceView(),
    pinnedSnapshot: EMPTY_PINNED_SNAPSHOT,
    artifactSnapshot: EMPTY_SNAPSHOT,
    readModel: INITIAL_READ_MODEL,
    setActiveTab: (tab) => set({ activeTab: tab }),
    setAudienceView: (view) => {
        if (!(0, audienceView_1.isAudienceView)(view)) {
            return;
        }
        persistAudienceView(view);
        set({ audienceView: view });
    },
    setPinnedCardCount: (count) => set((state) => {
        const pinnedSnapshot = {
            items: state.pinnedSnapshot.items,
            fallbackCount: normalizePinnedFallbackCount(count),
        };
        return {
            pinnedSnapshot,
            readModel: buildWorkspaceReadModel(state.artifactSnapshot, pinnedSnapshot),
        };
    }),
    syncPinnedItems: (items) => set((state) => {
        const pinnedSnapshot = {
            items: [...items],
            fallbackCount: state.pinnedSnapshot.fallbackCount,
        };
        return {
            pinnedSnapshot,
            readModel: buildWorkspaceReadModel(state.artifactSnapshot, pinnedSnapshot),
        };
    }),
    syncFromArtifacts: (snapshot) => set((state) => ({
        artifactSnapshot: snapshot,
        readModel: buildWorkspaceReadModel(snapshot, state.pinnedSnapshot),
    })),
    reset: () => set({
        activeTab: 'summary',
        audienceView: loadAudienceView(),
        pinnedSnapshot: EMPTY_PINNED_SNAPSHOT,
        artifactSnapshot: EMPTY_SNAPSHOT,
        readModel: INITIAL_READ_MODEL,
    }),
}));
exports.__test = {
    buildWorkspacePinnedProjection,
    buildWorkspacePinnedProjectionItem,
    buildWorkspaceReadModel,
    findWorkspacePinnedItem,
    isEvidenceWorkspaceTab,
    matchesWorkspacePinnedItem,
};
