"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const riskTierMatrix_1 = require("../../src/renderer/application/policy/riskTierMatrix");
function run() {
    // === normalizeRiskTierMatrix strips blanks and preserves populated cells ===
    {
        const normalized = (0, riskTierMatrix_1.normalizeRiskTierMatrix)({
            prod_deploy: { supervised: 'T3', delegate: ' ' },
            ' ': { autopilot: 'T1' },
            jira_create: { delegate: 'T1' },
            bad_row: null,
        });
        strict_1.default.deepEqual(normalized, {
            prod_deploy: { supervised: 'T3' },
            jira_create: { delegate: 'T1' },
        });
    }
    // === countRiskTierCellDiff and countRiskTierRowDiff agree on changed cells ===
    {
        const current = {
            prod_deploy: { supervised: 'T2', delegate: 'T1' },
            jira_create: { delegate: 'T0' },
        };
        const draft = {
            prod_deploy: { supervised: 'T3', delegate: 'T1' },
            jira_create: { delegate: 'T0' },
            slack_post: { autopilot: 'T1' },
        };
        strict_1.default.equal((0, riskTierMatrix_1.countRiskTierCellDiff)(current, draft), 2);
        strict_1.default.equal((0, riskTierMatrix_1.countRiskTierRowDiff)(current, draft), 2);
    }
    // === resolveRiskTierSavedBy prefers higher-trust organization members ===
    {
        const savedBy = (0, riskTierMatrix_1.resolveRiskTierSavedBy)({
            members: [
                { userId: 'viewer@example.com', role: 'viewer' },
                { userId: 'admin@example.com', role: 'admin' },
                { userId: 'editor@example.com', role: 'editor' },
            ],
        });
        strict_1.default.equal(savedBy, 'admin@example.com');
        strict_1.default.equal((0, riskTierMatrix_1.resolveRiskTierSavedBy)({ members: [] }), null);
    }
    // === formatRiskTierSnapshotLabel mirrors the editor header copy ===
    {
        strict_1.default.equal((0, riskTierMatrix_1.formatRiskTierSnapshotLabel)(null), null);
        strict_1.default.equal((0, riskTierMatrix_1.formatRiskTierSnapshotLabel)({
            savedAt: 0,
            matrix: {},
            savedBy: null,
        }), null);
        const label = (0, riskTierMatrix_1.formatRiskTierSnapshotLabel)({
            savedAt: 1700000000,
            matrix: {},
            savedBy: 'admin@example.com',
        });
        strict_1.default.ok(label?.includes('Last saved:'));
        strict_1.default.ok(label?.endsWith('by admin@example.com'));
    }
    console.log('[contract] PASS risk-tier-matrix-editor (4 cases)');
}
run();
