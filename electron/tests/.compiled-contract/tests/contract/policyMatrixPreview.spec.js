"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const loadRiskTierMatrix_1 = require("../../src/renderer/application/policy/loadRiskTierMatrix");
const saveRiskTierMatrix_1 = require("../../src/renderer/application/policy/saveRiskTierMatrix");
const previewMatrixImpact_1 = require("../../src/renderer/application/policy/previewMatrixImpact");
function makePreviewPort(result) {
    const calls = [];
    const port = async (input) => {
        calls.push({ input });
        return result;
    };
    return { port, calls };
}
function makeLoadPort(result) {
    return async () => result;
}
function makeSavePort(snapshot) {
    const calls = [];
    const port = async (input) => {
        calls.push({ input });
        return snapshot;
    };
    return { port, calls };
}
async function run() {
    // === previewMatrixImpact forwards candidate matrix to the port verbatim ===
    {
        const { port, calls } = makePreviewPort({
            addedRows: ['prod_deploy'],
            removedRows: [],
            modifiedRows: ['data_loader'],
            historicalCounts: { 'data_loader.supervised=T1': 4 },
        });
        const result = await (0, previewMatrixImpact_1.previewMatrixImpact)(port, {
            candidateMatrix: { data_loader: { supervised: 'T2' } },
        });
        strict_1.default.equal(calls.length, 1);
        strict_1.default.deepEqual(calls[0]?.input.candidateMatrix, {
            data_loader: { supervised: 'T2' },
        });
        strict_1.default.deepEqual(result.addedRows, ['prod_deploy']);
        strict_1.default.equal(result.historicalCounts['data_loader.supervised=T1'], 4);
    }
    // === previewMatrixImpact rejects null/undefined candidateMatrix ===
    {
        const { port, calls } = makePreviewPort({
            addedRows: [],
            removedRows: [],
            modifiedRows: [],
            historicalCounts: {},
        });
        await strict_1.default.rejects(
        // @ts-expect-error intentionally bad input for the contract test
        () => (0, previewMatrixImpact_1.previewMatrixImpact)(port, { candidateMatrix: null }), /candidateMatrix is required/);
        strict_1.default.equal(calls.length, 0);
    }
    // === saveRiskTierMatrix rejects matrix with empty cell tier ===
    {
        const { port, calls } = makeSavePort({
            savedAt: 1.0,
            matrix: {},
            savedBy: null,
        });
        await strict_1.default.rejects(() => (0, saveRiskTierMatrix_1.saveRiskTierMatrix)(port, {
            matrix: { data_loader: { supervised: '' } },
        }), /invalid cell/);
        strict_1.default.equal(calls.length, 0);
    }
    // === loadRiskTierMatrix forwards to the port and returns the payload ===
    {
        const port = makeLoadPort({
            matrix: { data_loader: { supervised: 'T1' } },
            history: [
                {
                    savedAt: 100.0,
                    matrix: { data_loader: { supervised: 'T1' } },
                    savedBy: 'op@example.com',
                },
            ],
        });
        const result = await (0, loadRiskTierMatrix_1.loadRiskTierMatrix)(port);
        strict_1.default.deepEqual(result.matrix, { data_loader: { supervised: 'T1' } });
        strict_1.default.equal(result.history.length, 1);
        strict_1.default.equal(result.history[0]?.savedBy, 'op@example.com');
    }
    // === mergeImpactPreview overlays heuristic count without dropping fields ===
    {
        const merged = (0, previewMatrixImpact_1.mergeImpactPreview)({
            addedRows: ['a'],
            removedRows: ['b'],
            modifiedRows: ['c'],
            historicalCounts: { 'a.supervised=T1': 7 },
        }, 3.7);
        strict_1.default.deepEqual(merged.addedRows, ['a']);
        strict_1.default.deepEqual(merged.removedRows, ['b']);
        strict_1.default.deepEqual(merged.modifiedRows, ['c']);
        strict_1.default.equal(merged.historicalCounts['a.supervised=T1'], 7);
        // Heuristic count is floored to a non-negative integer.
        strict_1.default.equal(merged.heuristicChangedCells, 3);
        const negative = (0, previewMatrixImpact_1.mergeImpactPreview)({
            addedRows: [],
            removedRows: [],
            modifiedRows: [],
            historicalCounts: {},
        }, -2);
        strict_1.default.equal(negative.heuristicChangedCells, 0);
    }
    // === formatLastSavedLabel handles missing snapshot + missing savedBy ===
    {
        strict_1.default.equal((0, previewMatrixImpact_1.formatLastSavedLabel)(null), null);
        strict_1.default.equal((0, previewMatrixImpact_1.formatLastSavedLabel)(undefined), null);
        strict_1.default.equal((0, previewMatrixImpact_1.formatLastSavedLabel)({
            savedAt: 0,
            matrix: {},
            savedBy: null,
        }), null);
        const labelNoActor = (0, previewMatrixImpact_1.formatLastSavedLabel)({
            savedAt: 1700000000,
            matrix: {},
            savedBy: null,
        });
        strict_1.default.ok(labelNoActor && labelNoActor.startsWith('Last saved: '));
        strict_1.default.ok(labelNoActor && !labelNoActor.includes(' by '));
        const labelWithActor = (0, previewMatrixImpact_1.formatLastSavedLabel)({
            savedAt: 1700000000,
            matrix: {},
            savedBy: 'op@example.com',
        });
        strict_1.default.ok(labelWithActor && labelWithActor.endsWith(' by op@example.com'));
    }
    // === countMatrixCellDiff counts per-cell differences across both matrices ===
    {
        const diff = (0, previewMatrixImpact_1.countMatrixCellDiff)({ data_loader: { supervised: 'T1' } }, {
            data_loader: { supervised: 'T2', delegate: 'T0' },
            prod_deploy: { delegate: 'T3' },
        });
        // data_loader.supervised changed (T1->T2) + data_loader.delegate added
        // + prod_deploy.delegate added = 3 cells.
        strict_1.default.equal(diff, 3);
        strict_1.default.equal((0, previewMatrixImpact_1.countMatrixCellDiff)({}, {}), 0);
    }
    console.log('[contract] PASS policy-matrix-preview (7 cases)');
}
void run();
