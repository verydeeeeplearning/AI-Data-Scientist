"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const trustStore_1 = require("../../src/renderer/application/trust/trustStore");
function buildTrust(resultId) {
    return {
        resultId,
        badges: [
            {
                key: 'verifier',
                kind: 'verifier',
                label: 'Verifier',
                status: 'pass',
                detail: 'Verified',
                href: '/governance/verifier/verifier-1',
                target: {
                    path: '/governance/verifier/verifier-1',
                    sectionId: 'review',
                    detailKind: 'verifier',
                    detailId: 'verifier-1',
                },
            },
        ],
        fetchedAt: Date.now(),
        updatedAt: null,
    };
}
async function run() {
    {
        let calls = 0;
        const store = (0, trustStore_1.createTrustStore)(async (resultId) => {
            calls += 1;
            return buildTrust(resultId);
        });
        const first = store.getState().ensure('result-1');
        const second = store.getState().ensure('result-1');
        strict_1.default.equal(store.getState().entries['result-1']?.state, 'loading');
        const [trust, dedupedTrust] = await Promise.all([first, second]);
        strict_1.default.equal(trust?.resultId, 'result-1');
        strict_1.default.equal(dedupedTrust?.resultId, 'result-1');
        strict_1.default.equal(calls, 1);
        const cached = await store.getState().ensure('result-1');
        strict_1.default.equal(cached, trust);
        strict_1.default.equal(calls, 1);
        strict_1.default.equal(store.getState().entries['result-1']?.state, 'loaded');
    }
    {
        let shouldReject = true;
        const store = (0, trustStore_1.createTrustStore)(async (resultId) => {
            if (shouldReject) {
                shouldReject = false;
                throw new Error('backend unavailable');
            }
            return buildTrust(resultId);
        });
        await strict_1.default.rejects(store.getState().ensure('result-2'), /backend unavailable/);
        strict_1.default.equal(store.getState().entries['result-2']?.state, 'error');
        strict_1.default.equal(store.getState().entries['result-2']?.error, 'backend unavailable');
        const trust = await store.getState().ensure('result-2', { force: true });
        strict_1.default.equal(trust?.resultId, 'result-2');
        strict_1.default.equal(store.getState().entries['result-2']?.state, 'loaded');
    }
    console.log('[contract] PASS trust-store (2 cases)');
}
void run().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
