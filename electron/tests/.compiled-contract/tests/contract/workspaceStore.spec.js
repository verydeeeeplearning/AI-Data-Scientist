"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const workspaceStore_1 = require("../../src/renderer/stores/workspaceStore");
function run() {
    const files = [
        {
            name: 'model_report.md',
            path: 'reports/model_report.md',
            size: 2048,
            type: 'md',
            modifiedAt: 2000,
        },
        {
            name: 'metrics.csv',
            path: 'tables/metrics.csv',
            size: 4096,
            type: 'csv',
            modifiedAt: 3000,
        },
        {
            name: 'roc_curve.png',
            path: 'plots/roc_curve.png',
            size: 8192,
            type: 'png',
            modifiedAt: 1000,
        },
    ];
    const plots = [
        {
            name: 'roc_curve.png',
            path: 'plots/roc_curve.png',
            size: 8192,
            addedAt: 1500,
            modifiedAt: 1000,
        },
    ];
    const pinnedCards = [
        {
            cardId: 'card-1',
            resultId: 'result-1',
            type: 'insight',
            createdAt: 1000,
            source: {
                messageId: 'msg-assistant-1',
                runId: 'run-1',
            },
            pinned: true,
            archived: false,
            title: 'Retention drivers',
            summary: 'Top cohorts show stable retention after week four.',
        },
        {
            cardId: 'card-2',
            resultId: 'result-2',
            type: 'artifact',
            createdAt: 2000,
            source: {
                messageId: 'msg-assistant-2',
                runId: 'run-1',
                toolCallId: 'tool-7',
            },
            pinned: true,
            archived: false,
            path: 'reports/roc_curve.png',
        },
        {
            cardId: 'card-3',
            resultId: 'result-3',
            type: 'risk',
            createdAt: 3000,
            source: {
                messageId: 'msg-assistant-3',
                runId: 'run-2',
            },
            pinned: false,
            archived: false,
            title: 'Do not project',
        },
    ];
    const pinnedProjection = workspaceStore_1.__test.buildWorkspacePinnedProjection({
        items: pinnedCards,
        fallbackCount: 5,
    });
    strict_1.default.equal(pinnedProjection.status, 'ready');
    strict_1.default.equal(pinnedProjection.count, 2);
    strict_1.default.equal(pinnedProjection.items[0]?.cardId, 'card-2');
    strict_1.default.equal(pinnedProjection.items[0]?.artifactPath, 'reports/roc_curve.png');
    strict_1.default.equal(pinnedProjection.items[1]?.summary, 'Top cohorts show stable retention after week four.');
    strict_1.default.equal(workspaceStore_1.__test.findWorkspacePinnedItem(pinnedProjection.items, 'result', 'result-2')?.cardId, 'card-2');
    strict_1.default.equal(workspaceStore_1.__test.matchesWorkspacePinnedItem(pinnedProjection.items[1], 'message', 'msg-assistant-1'), true);
    const countOnlyProjection = workspaceStore_1.__test.buildWorkspacePinnedProjection({
        items: [],
        fallbackCount: 2,
    });
    strict_1.default.equal(countOnlyProjection.status, 'count_only');
    strict_1.default.equal(countOnlyProjection.count, 2);
    const readModel = workspaceStore_1.__test.buildWorkspaceReadModel({ files, plots, loading: false }, { items: pinnedCards, fallbackCount: 0 });
    strict_1.default.equal(readModel.status, 'ready');
    strict_1.default.equal(readModel.nonPlotFileCount, 2);
    strict_1.default.equal(readModel.plotCount, 1);
    strict_1.default.equal(readModel.tableCount, 1);
    strict_1.default.equal(readModel.pinnedCardCount, 2);
    strict_1.default.equal(readModel.pinnedProjectionStatus, 'ready');
    strict_1.default.equal(readModel.exportCandidateCount, 3);
    strict_1.default.deepEqual(readModel.exportCandidates.map((candidate) => ({
        id: candidate.id,
        name: candidate.name,
        path: candidate.path,
        type: candidate.type,
        formats: [...candidate.formats],
        sourceKind: candidate.sourceKind,
    })), [
        {
            id: 'plots/roc_curve.png',
            name: 'roc_curve.png',
            path: 'plots/roc_curve.png',
            type: 'png',
            formats: ['png'],
            sourceKind: 'file',
        },
        {
            id: 'reports/model_report.md',
            name: 'model_report.md',
            path: 'reports/model_report.md',
            type: 'md',
            formats: ['docx', 'html', 'pdf'],
            sourceKind: 'file',
        },
        {
            id: 'tables/metrics.csv',
            name: 'metrics.csv',
            path: 'tables/metrics.csv',
            type: 'csv',
            formats: ['html', 'xlsx'],
            sourceKind: 'file',
        },
    ]);
    strict_1.default.equal(readModel.sections.find((section) => section.id === 'summary')?.itemCount, 3);
    strict_1.default.equal(readModel.recentFiles[0]?.path, 'tables/metrics.csv');
    strict_1.default.equal(readModel.pinnedItems[0]?.cardId, 'card-2');
    workspaceStore_1.useWorkspaceStore.getState().reset();
    workspaceStore_1.useWorkspaceStore.getState().setPinnedCardCount(2);
    strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().readModel.pinnedProjectionStatus, 'count_only');
    strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().readModel.pinnedCardCount, 2);
    workspaceStore_1.useWorkspaceStore.getState().syncPinnedItems([pinnedCards[0]]);
    strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().readModel.pinnedProjectionStatus, 'ready');
    strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().readModel.pinnedCardCount, 1);
    strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().readModel.pinnedItems[0]?.cardId, 'card-1');
    workspaceStore_1.useWorkspaceStore.getState().syncFromArtifacts({
        files: [],
        plots: [],
        loading: true,
    });
    strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().readModel.status, 'loading');
    workspaceStore_1.useWorkspaceStore.getState().syncFromArtifacts({
        files: [
            {
                name: 'summary.html',
                path: 'reports/summary.html',
                size: 512,
                type: 'html',
                modifiedAt: 5000,
            },
        ],
        plots: [],
        loading: false,
    });
    strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().readModel.status, 'ready');
    strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().readModel.exportCandidateCount, 1);
    strict_1.default.deepEqual(workspaceStore_1.useWorkspaceStore.getState().readModel.exportCandidates.map((candidate) => ({
        id: candidate.id,
        name: candidate.name,
        path: candidate.path,
        type: candidate.type,
        formats: [...candidate.formats],
        sourceKind: candidate.sourceKind,
    })), [
        {
            id: 'reports/summary.html',
            name: 'summary.html',
            path: 'reports/summary.html',
            type: 'html',
            formats: ['html', 'pdf'],
            sourceKind: 'file',
        },
    ]);
    strict_1.default.equal(workspaceStore_1.useWorkspaceStore.getState().readModel.pinnedCardCount, 1);
    workspaceStore_1.useWorkspaceStore.getState().reset();
    console.log('[contract] PASS workspace-store (20 cases)');
}
run();
