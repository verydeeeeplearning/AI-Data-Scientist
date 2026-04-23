"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const cardApi_1 = require("../../src/renderer/infrastructure/api/cardApi");
const useAudienceRenderedCard_1 = require("../../src/renderer/hooks/useAudienceRenderedCard");
async function run() {
    const originalWindow = globalThis.window;
    const originalFetch = globalThis.fetch;
    const fetchCalls = [];
    let cases = 0;
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
        if (String(input).includes('/render-for-audience')) {
            return {
                ok: true,
                json: async () => ({
                    renderedCard: {
                        summary: 'Revenue lifted',
                        body: '## Summary\n- Revenue increased',
                        sections: [
                            {
                                id: 'impact',
                                title: 'Impact',
                                body: 'Revenue increased by 12%',
                            },
                        ],
                    },
                }),
            };
        }
        return {
            ok: true,
            json: async () => ({ ok: true }),
        };
    });
    try {
        const rendered = await (0, cardApi_1.renderCardForAudience)({
            cardId: 'card-1',
            audience: 'exec',
            cardType: 'insight',
        });
        strict_1.default.equal(fetchCalls[0]?.input, 'http://127.0.0.1:19999/api/cards/render-for-audience');
        strict_1.default.equal(fetchCalls[0]?.init?.method, 'POST');
        strict_1.default.equal(rendered.summary, 'Revenue lifted');
        strict_1.default.equal(rendered.body, '## Summary\n- Revenue increased');
        strict_1.default.equal(rendered.sections.length, 1);
        strict_1.default.equal(rendered.sections[0]?.id, 'impact');
        cases += 5;
        await (0, cardApi_1.reportAudienceSwitch)({
            fromAudience: 'ds',
            toAudience: 'exec',
            sessionId: 'session-1',
        });
        strict_1.default.equal(fetchCalls[1]?.input, 'http://127.0.0.1:19999/api/cards/audience-switch');
        strict_1.default.equal(fetchCalls[1]?.init?.method, 'POST');
        strict_1.default.equal(fetchCalls[1]?.init?.body, JSON.stringify({
            fromAudience: 'ds',
            toAudience: 'exec',
            sessionId: 'session-1',
        }));
        cases += 3;
        const normalized = (0, cardApi_1.normalizeRenderedCard)({
            summary: 'Title',
            body: '  ',
            sections: [
                { id: 'a', title: 'A', body: 'B' },
                { id: ' ', title: 'Ignored', body: 'Ignored' },
            ],
        });
        strict_1.default.equal(normalized.summary, 'Title');
        strict_1.default.equal(normalized.body, null);
        strict_1.default.equal(normalized.sections.length, 1);
        strict_1.default.equal((0, cardApi_1.hasAudienceRenderedCardContent)(normalized), true);
        strict_1.default.equal((0, cardApi_1.hasAudienceRenderedCardContent)({ summary: null, body: null, sections: [] }), false);
        cases += 4;
        globalThis.fetch = (async () => ({
            ok: true,
            json: async () => ({
                renderedCard: {
                    summary: '   ',
                    body: '   ',
                    sections: [],
                },
            }),
        }));
        await strict_1.default.rejects((0, cardApi_1.renderCardForAudience)({
            cardId: 'card-empty',
            audience: 'ml',
            cardType: 'risk',
        }), (error) => {
            strict_1.default.equal(error instanceof Error ? error.message : String(error), 'Audience render response did not include usable content');
            return true;
        });
        cases += 1;
        strict_1.default.equal((0, useAudienceRenderedCard_1.resolveAudienceRenderedCardStatus)({
            renderedCard: null,
            isLoading: false,
            error: null,
            usesBackendRendering: false,
        }), 'original');
        strict_1.default.equal((0, useAudienceRenderedCard_1.resolveAudienceRenderedCardStatus)({
            renderedCard: null,
            isLoading: true,
            error: null,
            usesBackendRendering: true,
        }), 'loading-fallback');
        strict_1.default.equal((0, useAudienceRenderedCard_1.resolveAudienceRenderedCardStatus)({
            renderedCard: null,
            isLoading: false,
            error: 'backend unavailable',
            usesBackendRendering: true,
        }), 'error-fallback');
        strict_1.default.equal((0, useAudienceRenderedCard_1.resolveAudienceRenderedCardStatus)({
            renderedCard: {
                summary: 'Executive summary',
                body: null,
                sections: [],
            },
            isLoading: false,
            error: null,
            usesBackendRendering: true,
        }), 'rendered');
        cases += 4;
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
    console.log(`[contract] PASS audience-rendering-port (${cases} cases)`);
}
void run().catch((error) => {
    console.error(error);
    process.exit(1);
});
