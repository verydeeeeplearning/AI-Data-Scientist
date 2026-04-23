"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const approvalModalModel_1 = require("../../src/renderer/components/approval/approvalModalModel");
const baseApproval = {
    approvalId: 'appr-001',
    sessionId: 'session-001',
    runId: 'run-001',
    surface: 'ws',
    question: 'Allow the agent to continue with the blocked step?',
    kind: 'generic',
    metadata: {},
    options: [],
    default: null,
    status: 'pending',
    response: null,
    source: null,
    actor: null,
    createdAt: 1713650000,
    updatedAt: 1713650000,
    resolvedAt: null,
};
function run() {
    // === mergeApprovalDetails keeps the workflow snapshot and overlays v2 fields ===
    {
        const details = (0, approvalModalModel_1.mergeApprovalDetails)(baseApproval, {
            workspaceId: 'workspace-42',
            riskCode: 'PAT_005_SECRET_ENV_ACCESS',
            affectedScopes: ['secret'],
            recommendedAlternative: 'Use the secret manager instead.',
            patternMatches: [
                {
                    patternId: 'PAT_005_SECRET_ENV_ACCESS',
                    description: 'Read environment secrets',
                    highlightedLines: [{ line: 4, reason: 'os.environ access' }],
                },
            ],
        });
        strict_1.default.equal(details.workspaceId, 'workspace-42');
        strict_1.default.equal(details.riskCode, 'PAT_005_SECRET_ENV_ACCESS');
        strict_1.default.deepEqual(details.affectedScopes, ['secret']);
        strict_1.default.equal(details.patternMatches[0]?.highlightedLines[0]?.line, 4);
        strict_1.default.equal(details.recommendedAlternative, 'Use the secret manager instead.');
    }
    // === semantic proposals expose their richer context and keep non-binary responses ===
    {
        const details = (0, approvalModalModel_1.mergeApprovalDetails)(baseApproval, {
            kind: 'semantic_proposal',
            options: ['approve', 'apply'],
            default: 'approve',
            metadata: {
                proposalType: 'verified_query',
                targetId: 'metric.revenue',
                risk: 'high',
                confidence: 0.91,
                autoApplyEligible: true,
            },
        });
        const viewModel = (0, approvalModalModel_1.buildApprovalModalViewModel)(details);
        strict_1.default.equal(viewModel.title, 'Semantic proposal approval');
        strict_1.default.deepEqual(viewModel.responseOptions, ['approve', 'apply']);
        strict_1.default.equal(viewModel.severity, 'medium');
        strict_1.default.ok(viewModel.infoRows.some((row) => row.label === 'Proposal' && row.value === 'Verified Query'));
        strict_1.default.ok(viewModel.infoRows.some((row) => row.label === 'Confidence' && row.value === '91%'));
    }
    // === binary approve/reject options stay out of the response chip list ===
    {
        const details = (0, approvalModalModel_1.mergeApprovalDetails)(baseApproval, {
            options: ['approve', 'reject'],
            default: 'reject',
        });
        const viewModel = (0, approvalModalModel_1.buildApprovalModalViewModel)(details);
        strict_1.default.deepEqual(viewModel.responseOptions, []);
        strict_1.default.equal(viewModel.title, 'Operator approval required');
    }
    // === code preview trims around highlighted lines and keeps the snippet language ===
    {
        const details = (0, approvalModalModel_1.mergeApprovalDetails)(baseApproval, {
            affectedScopes: ['network'],
            metadata: {
                sql: [
                    'SELECT metric_name, metric_value',
                    'FROM warehouse.metrics_daily',
                    'WHERE snapshot_date >= CURRENT_DATE - 7',
                    'ORDER BY snapshot_date DESC',
                ].join('\n'),
            },
            patternMatches: [
                {
                    patternId: 'PAT_008_HTTP_REQUEST_UNAPPROVED',
                    description: 'Unapproved HTTP request',
                    highlightedLines: [{ line: 2, reason: 'Review the selected relation before allowing outbound access.' }],
                },
            ],
        });
        const viewModel = (0, approvalModalModel_1.buildApprovalModalViewModel)(details);
        strict_1.default.equal(viewModel.codePreview?.language, 'sql');
        strict_1.default.equal(viewModel.codePreview?.lines[1]?.number, 2);
        strict_1.default.equal(viewModel.codePreview?.lines[1]?.reason, 'Review the selected relation before allowing outbound access.');
    }
    console.log('[contract] PASS approval-modal-model (4 cases)');
}
run();
