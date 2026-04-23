"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const workspaceRoute_1 = require("../../src/renderer/application/workspace/workspaceRoute");
const resolveExportWizardSelection_1 = require("../../src/renderer/application/workspace/resolveExportWizardSelection");
function run() {
    const route = (0, workspaceRoute_1.parseEvidenceWorkspaceRoute)({
        subPath: 'workspace/export/detail/result/result-42',
    });
    strict_1.default.deepEqual(route, {
        tab: 'export',
        focus: {
            mode: 'detail',
            target: 'result',
            value: 'result-42',
        },
    });
    const candidates = [
        {
            id: 'tables/metrics.csv',
            name: 'metrics.csv',
            path: 'tables/metrics.csv',
        },
        {
            id: 'reports/model_report.md',
            name: 'model_report.md',
            path: 'reports/model_report.md',
        },
        {
            id: 'plots/roc_curve.png',
            name: 'roc_curve.png',
            path: 'plots/roc_curve.png',
        },
    ];
    const selection = (0, resolveExportWizardSelection_1.resolveExportWizardSelection)({
        focus: route.focus,
        candidates,
        cards: [
            {
                cardId: 'card-1',
                resultId: 'result-42',
                artifactPath: 'reports/model_report.md',
            },
        ],
        pinnedItems: [],
    });
    strict_1.default.equal(selection.shouldAutoOpen, true);
    strict_1.default.equal(selection.preferredCandidateId, 'reports/model_report.md');
    strict_1.default.deepEqual((0, resolveExportWizardSelection_1.prioritizeExportWizardCandidates)(candidates, selection.preferredCandidateId).map((candidate) => candidate.id), ['reports/model_report.md', 'tables/metrics.csv', 'plots/roc_curve.png']);
    const pinnedSelection = (0, resolveExportWizardSelection_1.resolveExportWizardSelection)({
        focus: {
            mode: 'detail',
            target: 'result',
            value: 'result-99',
        },
        candidates,
        cards: [],
        pinnedItems: [
            {
                cardId: 'card-9',
                resultId: 'result-99',
                artifactPath: 'plots/roc_curve.png',
            },
        ],
    });
    strict_1.default.equal(pinnedSelection.shouldAutoOpen, true);
    strict_1.default.equal(pinnedSelection.preferredCandidateId, 'plots/roc_curve.png');
    const noMatchSelection = (0, resolveExportWizardSelection_1.resolveExportWizardSelection)({
        focus: {
            mode: 'detail',
            target: 'result',
            value: 'result-100',
        },
        candidates,
        cards: [
            {
                cardId: 'card-2',
                resultId: 'result-100',
            },
        ],
        pinnedItems: [],
    });
    strict_1.default.equal(noMatchSelection.shouldAutoOpen, true);
    strict_1.default.equal(noMatchSelection.preferredCandidateId, null);
    strict_1.default.deepEqual((0, resolveExportWizardSelection_1.prioritizeExportWizardCandidates)(candidates, noMatchSelection.preferredCandidateId).map((candidate) => candidate.id), ['tables/metrics.csv', 'reports/model_report.md', 'plots/roc_curve.png']);
    const passiveSelection = (0, resolveExportWizardSelection_1.resolveExportWizardSelection)({
        focus: {
            mode: 'highlight',
            target: 'result',
            value: 'result-42',
        },
        candidates,
        cards: [
            {
                cardId: 'card-1',
                resultId: 'result-42',
                artifactPath: 'reports/model_report.md',
            },
        ],
        pinnedItems: [],
    });
    strict_1.default.equal(passiveSelection.shouldAutoOpen, false);
    strict_1.default.equal(passiveSelection.preferredCandidateId, null);
    console.log('[contract] PASS resolve-export-wizard-selection (5 cases)');
}
run();
