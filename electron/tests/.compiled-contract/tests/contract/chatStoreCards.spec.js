"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const chatStore_1 = require("../../src/renderer/stores/chatStore");
function makeCard(overrides = {}) {
    return {
        cardId: 'card-1',
        resultId: 'result-1',
        type: 'other',
        createdAt: 1713650000,
        source: {
            messageId: 'msg-assistant-1',
            runId: 'run-1',
            toolCallId: null,
        },
        pinned: false,
        archived: false,
        trustStrip: null,
        title: 'Fallback',
        body: 'payload',
        ...overrides,
    };
}
function resetStore() {
    chatStore_1.useChatStore.setState({
        messages: [],
        toolActivities: [],
        isStreaming: false,
        streamBuffer: '',
        sessionId: null,
        cardsById: {},
        cardIdsByMessageId: {},
    });
}
function run() {
    // === stream.done normalization preserves explicit messageId/cardId/resultId split ===
    {
        const normalized = (0, chatStore_1.normalizeStreamDonePayload)({
            content: 'Analysis complete.',
            cost: 0.42,
            messageId: 'msg-assistant-1',
            cards: [
                {
                    cardId: 'card-1',
                    resultId: 'result-1',
                    type: 'insight',
                    createdAt: 1713650000,
                    source: {
                        messageId: 'msg-assistant-1',
                        runId: 'run-1',
                    },
                    pinned: false,
                    archived: false,
                    title: 'Retention lifted',
                },
            ],
        });
        strict_1.default.equal(normalized.messageId, 'msg-assistant-1');
        strict_1.default.equal(normalized.cards.length, 1);
        strict_1.default.equal(normalized.cards[0].cardId, 'card-1');
        strict_1.default.equal(normalized.cards[0].resultId, 'result-1');
        strict_1.default.equal(normalized.cards[0].source.messageId, 'msg-assistant-1');
    }
    // === legacy id fallback stays at normalization boundary ===
    {
        const normalized = (0, chatStore_1.normalizeResultCardPayload)({
            id: 'legacy-card-1',
            type: 'other',
            createdAt: 1713650000,
            source: {
                runId: 'run-legacy',
            },
            title: 'Legacy',
            body: 'legacy payload',
        }, { messageIdFallback: 'msg-legacy-1' });
        strict_1.default.ok(normalized);
        strict_1.default.equal(normalized?.cardId, 'legacy-card-1');
        strict_1.default.equal(normalized?.resultId, 'legacy-card-1');
        strict_1.default.equal(normalized?.source.messageId, 'msg-legacy-1');
        strict_1.default.equal('id' in (normalized ?? {}), false);
    }
    // === store hydrates cards and indexes them by source message id ===
    {
        resetStore();
        chatStore_1.useChatStore.getState().replaceConversation([
            { messageId: 'msg-user-1', role: 'user', content: 'Analyze retention' },
            { messageId: 'msg-assistant-1', role: 'assistant', content: 'Summary' },
        ], 'session-1', [
            makeCard(),
            makeCard({
                cardId: 'card-2',
                resultId: 'result-2',
                createdAt: 1713650010,
                title: 'Follow-up',
            }),
        ]);
        const state = chatStore_1.useChatStore.getState();
        strict_1.default.equal(state.sessionId, 'session-1');
        strict_1.default.deepEqual(state.cardIdsByMessageId['msg-assistant-1'], ['card-1', 'card-2']);
        strict_1.default.equal(state.cardsById['card-2']?.resultId, 'result-2');
    }
    // === upsertCards merges updates and replaceConversation clears prior card state ===
    {
        chatStore_1.useChatStore.getState().upsertCards([
            makeCard({
                cardId: 'card-1',
                resultId: 'result-1',
                pinned: true,
            }),
        ]);
        let state = chatStore_1.useChatStore.getState();
        strict_1.default.equal(state.cardsById['card-1']?.pinned, true);
        chatStore_1.useChatStore.getState().replaceConversation([{ messageId: 'msg-user-2', role: 'user', content: 'New session' }], 'session-2', []);
        state = chatStore_1.useChatStore.getState();
        strict_1.default.equal(state.sessionId, 'session-2');
        strict_1.default.deepEqual(state.cardsById, {});
        strict_1.default.deepEqual(state.cardIdsByMessageId, {});
    }
    console.log('[contract] PASS chat-store-cards (4 cases)');
}
run();
