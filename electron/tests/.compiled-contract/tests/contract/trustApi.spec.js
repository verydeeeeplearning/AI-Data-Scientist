"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const trustApi_1 = require("../../src/renderer/infrastructure/api/trustApi");
async function run() {
    const originalFetch = globalThis.fetch;
    const originalWindow = globalThis.window;
    try {
        globalThis.window = {
            location: { search: '?port=18888' },
        };
        let requestedUrl = null;
        let requestedInit;
        globalThis.fetch = (async (input, init) => {
            requestedUrl = typeof input === 'string' ? input : input.toString();
            requestedInit = init;
            return {
                ok: true,
                json: async () => ({
                    resultId: 'result/with/slash',
                    badges: [{ kind: 'verifier', status: 'pass', verifierId: 'vf-1' }],
                }),
            };
        });
        const trust = await (0, trustApi_1.fetchTrustByResultId)('result/with/slash');
        strict_1.default.equal(requestedUrl, 'http://127.0.0.1:18888/api/trust/result%2Fwith%2Fslash');
        strict_1.default.deepEqual(requestedInit, { cache: 'no-store' });
        strict_1.default.equal(trust.badges[0]?.kind, 'verifier');
        strict_1.default.equal(trust.badges[0]?.href, '/governance/verifier/vf-1');
        globalThis.fetch = (async () => ({
            ok: false,
            status: 404,
            json: async () => ({ detail: 'trust metadata not found' }),
        }));
        await strict_1.default.rejects((0, trustApi_1.fetchTrustByResultId)('missing-result'), /trust metadata not found/);
        console.log('[contract] PASS trust-api (2 cases)');
    }
    finally {
        globalThis.fetch = originalFetch;
        if (typeof originalWindow === 'undefined') {
            delete globalThis.window;
        }
        else {
            globalThis.window = originalWindow;
        }
    }
}
void run().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
