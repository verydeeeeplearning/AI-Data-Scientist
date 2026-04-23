"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const cardApi_1 = require("../../src/renderer/infrastructure/api/cardApi");
async function run() {
    const originalWindow = globalThis.window;
    const originalFetch = globalThis.fetch;
    const fetchCalls = [];
    Object.defineProperty(globalThis, 'window', {
        value: {
            location: {
                search: '?port=19999',
            },
        },
        configurable: true,
    });
    globalThis.fetch = (async (input, init) => {
        fetchCalls.push({ input, init });
        return {
            ok: true,
            json: async () => ({
                card: {
                    cardId: 'card-1',
                    resultId: 'result-1',
                    type: 'insight',
                    createdAt: 1713650000,
                    source: {
                        messageId: 'msg-1',
                        runId: 'run-1',
                    },
                    pinned: true,
                    archived: false,
                },
            }),
        };
    });
    try {
        const response = await (0, cardApi_1.setCardPinned)('card/1', true);
        strict_1.default.equal(fetchCalls.length, 1);
        strict_1.default.equal(fetchCalls[0]?.input, 'http://127.0.0.1:19999/api/cards/card%2F1/pin');
        strict_1.default.equal(fetchCalls[0]?.init?.method, 'POST');
        strict_1.default.equal(fetchCalls[0]?.init?.headers instanceof Object, true);
        strict_1.default.equal(fetchCalls[0]?.init?.body, JSON.stringify({ pinned: true }));
        strict_1.default.equal(response.card.cardId, 'card-1');
        strict_1.default.equal(response.card.pinned, true);
    }
    finally {
        if (typeof originalWindow === 'undefined') {
            delete globalThis.window;
        }
        else {
            Object.defineProperty(globalThis, 'window', {
                value: originalWindow,
                configurable: true,
            });
        }
        globalThis.fetch = originalFetch;
    }
    console.log('[contract] PASS card-api (5 cases)');
}
void run().catch((error) => {
    console.error(error);
    process.exit(1);
});
