"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const trustMapper_1 = require("../../src/renderer/application/trust/trustMapper");
function run() {
    {
        const trust = (0, trustMapper_1.mapTrustPayload)('result-42', {
            resultId: 'result-42',
            badges: [
                {
                    kind: 'verifier',
                    status: 'pass',
                    detail: 'Schema verified',
                    target: { kind: 'verifier', id: 'vf-1' },
                },
                {
                    kind: 'approval',
                    status: 'pending',
                    approvalId: 'approval-9',
                },
            ],
        });
        strict_1.default.equal(trust.resultId, 'result-42');
        strict_1.default.equal(trust.badges.length, 2);
        strict_1.default.equal(trust.badges[0]?.kind, 'verifier');
        strict_1.default.equal(trust.badges[0]?.status, 'pass');
        strict_1.default.equal(trust.badges[0]?.href, '/governance/verifier/vf-1');
        strict_1.default.equal(trust.badges[0]?.detail, 'Schema verified');
        strict_1.default.equal(trust.badges[1]?.kind, 'approval');
        strict_1.default.equal(trust.badges[1]?.status, 'pending');
        strict_1.default.equal(trust.badges[1]?.href, '/governance/approval/approval-9');
    }
    {
        const trust = (0, trustMapper_1.mapTrustPayload)('result-derived', {
            verifierStatus: 'warning',
            verifierId: 'vf-2',
            approvalStatus: 'queued',
            approvalId: 'approval-4',
            policyStatus: 'blocked',
            policyId: 'policy-3',
        });
        strict_1.default.deepEqual(trust.badges.map((badge) => badge.kind), ['verifier', 'approval', 'policy']);
        strict_1.default.deepEqual(trust.badges.map((badge) => badge.status), ['warn', 'pending', 'fail']);
        strict_1.default.deepEqual(trust.badges.map((badge) => badge.href), [
            '/governance/verifier/vf-2',
            '/governance/approval/approval-4',
            '/governance/policy/policy-3',
        ]);
    }
    console.log('[contract] PASS trust-mapper (2 cases)');
}
run();
