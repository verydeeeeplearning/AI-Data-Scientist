"use strict";
/**
 * Chat state and result-card hydration store.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.useChatStore = void 0;
exports.normalizeResultCardPayload = normalizeResultCardPayload;
exports.normalizeResultCardCollection = normalizeResultCardCollection;
exports.normalizeStreamDonePayload = normalizeStreamDonePayload;
exports.normalizeChatHistoryPayload = normalizeChatHistoryPayload;
const zustand_1 = require("zustand");
const RESULT_CARD_TYPES = new Set([
    'insight',
    'experiment',
    'risk',
    'artifact',
    'other',
]);
let msgCounter = 0;
function nextMsgId() {
    return `msg-${++msgCounter}-${Date.now().toString(36)}`;
}
function isRecord(value) {
    return typeof value === 'object' && value !== null;
}
function isNonEmptyString(value) {
    return typeof value === 'string' && value.trim().length > 0;
}
function normalizeCardId(payload) {
    if (isNonEmptyString(payload.cardId)) {
        return payload.cardId;
    }
    if (isNonEmptyString(payload.id)) {
        return payload.id;
    }
    return null;
}
function normalizeResultId(payload, cardId) {
    if (isNonEmptyString(payload.resultId)) {
        return payload.resultId;
    }
    return cardId;
}
function normalizeCreatedAt(value) {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value;
    }
    if (!isNonEmptyString(value)) {
        return null;
    }
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
        return numeric;
    }
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed / 1000 : null;
}
function normalizeCardSource(value, messageIdFallback) {
    if (!isRecord(value) || !isNonEmptyString(value.runId)) {
        return null;
    }
    const messageId = isNonEmptyString(value.messageId)
        ? value.messageId
        : (isNonEmptyString(messageIdFallback) ? messageIdFallback : null);
    if (!messageId) {
        return null;
    }
    return {
        messageId,
        runId: value.runId,
        toolCallId: isNonEmptyString(value.toolCallId) ? value.toolCallId : null,
    };
}
function normalizeResultCardType(value) {
    if (isNonEmptyString(value) && RESULT_CARD_TYPES.has(value)) {
        return value;
    }
    return 'other';
}
function sortCards(cards) {
    return [...cards].sort((left, right) => {
        if (left.createdAt !== right.createdAt) {
            return left.createdAt - right.createdAt;
        }
        return left.cardId.localeCompare(right.cardId);
    });
}
function indexCardsByMessageId(cardsById) {
    const next = {};
    for (const card of sortCards(Object.values(cardsById))) {
        const messageId = card.source.messageId;
        next[messageId] = [...(next[messageId] ?? []), card.cardId];
    }
    return next;
}
function buildCardState(cards) {
    const cardsById = {};
    for (const card of cards) {
        cardsById[card.cardId] = card;
    }
    return {
        cardsById,
        cardIdsByMessageId: indexCardsByMessageId(cardsById),
    };
}
function normalizeHistoryMessageRecord(item) {
    if (!isRecord(item)) {
        return { message: null, cards: [] };
    }
    const messageId = isNonEmptyString(item.messageId) ? item.messageId : undefined;
    return {
        message: {
            messageId,
            role: typeof item.role === 'string' ? item.role : 'assistant',
            content: typeof item.content === 'string' ? item.content : '',
        },
        cards: normalizeResultCardCollection(item.cards, { messageIdFallback: messageId ?? null }),
    };
}
function normalizeResultCardPayload(payload, options = {}) {
    if (!isRecord(payload)) {
        return null;
    }
    const cardId = normalizeCardId(payload);
    if (!cardId) {
        return null;
    }
    const source = normalizeCardSource(payload.source, options.messageIdFallback);
    if (!source) {
        return null;
    }
    const normalized = {
        ...payload,
        cardId,
        resultId: normalizeResultId(payload, cardId),
        type: normalizeResultCardType(payload.type),
        createdAt: normalizeCreatedAt(payload.createdAt) ?? Date.now() / 1000,
        source,
        trustStrip: isRecord(payload.trustStrip) ? payload.trustStrip : null,
        pinned: payload.pinned === true,
        archived: payload.archived === true,
    };
    delete normalized.id;
    return normalized;
}
function normalizeResultCardCollection(payload, options = {}) {
    if (!Array.isArray(payload)) {
        return [];
    }
    const cardsById = {};
    for (const item of payload) {
        const card = normalizeResultCardPayload(item, options);
        if (card) {
            cardsById[card.cardId] = card;
        }
    }
    return sortCards(Object.values(cardsById));
}
function normalizeStreamDonePayload(payload) {
    if (!isRecord(payload)) {
        return { content: '', messageId: null, cards: [] };
    }
    const messageId = isNonEmptyString(payload.messageId) ? payload.messageId : null;
    const normalized = {
        content: typeof payload.content === 'string' ? payload.content : '',
        messageId,
        cards: normalizeResultCardCollection(payload.cards, { messageIdFallback: messageId }),
    };
    if (typeof payload.cost === 'number' && Number.isFinite(payload.cost)) {
        normalized.cost = payload.cost;
    }
    return normalized;
}
function normalizeChatHistoryPayload(payload) {
    if (!isRecord(payload)) {
        return { messages: [], cards: [] };
    }
    const messages = [];
    const cardsById = {};
    if (Array.isArray(payload.messages)) {
        for (const item of payload.messages) {
            const normalized = normalizeHistoryMessageRecord(item);
            if (normalized.message && normalized.message.content.length > 0) {
                messages.push(normalized.message);
            }
            for (const card of normalized.cards) {
                cardsById[card.cardId] = card;
            }
        }
    }
    for (const card of normalizeResultCardCollection(payload.cards)) {
        cardsById[card.cardId] = card;
    }
    return {
        messages,
        cards: sortCards(Object.values(cardsById)),
    };
}
exports.useChatStore = (0, zustand_1.create)((set) => ({
    messages: [],
    toolActivities: [],
    isStreaming: false,
    streamBuffer: '',
    sessionId: null,
    cardsById: {},
    cardIdsByMessageId: {},
    addUserMessage: (content) => {
        const id = nextMsgId();
        set((s) => ({
            messages: [...s.messages, {
                    id,
                    role: 'user',
                    content,
                    timestamp: Date.now(),
                }],
        }));
        return id;
    },
    startAssistantMessage: () => {
        const id = nextMsgId();
        set((s) => ({
            messages: [...s.messages, {
                    id,
                    role: 'assistant',
                    content: '',
                    timestamp: Date.now(),
                }],
            streamBuffer: '',
            isStreaming: true,
        }));
        return id;
    },
    appendStreamDelta: (token) => {
        set((s) => {
            const msgs = [...s.messages];
            if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
                msgs[msgs.length - 1] = {
                    ...msgs[msgs.length - 1],
                    content: msgs[msgs.length - 1].content + token,
                };
            }
            return { messages: msgs, streamBuffer: s.streamBuffer + token };
        });
    },
    finalizeStream: (content, messageId) => {
        set((s) => {
            const msgs = [...s.messages];
            if (msgs.length > 0 && msgs[msgs.length - 1].role === 'assistant') {
                msgs[msgs.length - 1] = {
                    ...msgs[msgs.length - 1],
                    id: typeof messageId === 'string' && messageId.length > 0
                        ? messageId
                        : msgs[msgs.length - 1].id,
                    content,
                };
            }
            return { messages: msgs, isStreaming: false, streamBuffer: '' };
        });
    },
    setStreaming: (v) => set({ isStreaming: v }),
    setSessionId: (id) => set({ sessionId: id }),
    upsertCards: (cards) => {
        if (cards.length === 0) {
            return;
        }
        set((s) => {
            const cardsById = { ...s.cardsById };
            for (const card of cards) {
                cardsById[card.cardId] = {
                    ...(cardsById[card.cardId] ?? {}),
                    ...card,
                };
            }
            return {
                cardsById,
                cardIdsByMessageId: indexCardsByMessageId(cardsById),
            };
        });
    },
    replaceConversation: (messages, sessionId, cards = []) => set({
        messages: messages.map((message, index) => ({
            id: typeof message.messageId === 'string' && message.messageId.length > 0
                ? message.messageId
                : nextMsgId(),
            role: message.role === 'user' ? 'user' : 'assistant',
            content: message.content,
            timestamp: Date.now() + index,
        })),
        ...buildCardState(cards),
        toolActivities: [],
        isStreaming: false,
        streamBuffer: '',
        sessionId,
    }),
    addToolActivity: (name, args) => {
        set((s) => ({
            toolActivities: [...s.toolActivities, {
                    name,
                    status: 'running',
                    args,
                    startedAt: Date.now(),
                }],
        }));
    },
    completeToolActivity: (name, success, elapsed, result) => {
        set((s) => {
            const next = [...s.toolActivities];
            for (let index = next.length - 1; index >= 0; index -= 1) {
                const activity = next[index];
                if (activity.name === name && activity.status === 'running') {
                    next[index] = {
                        ...activity,
                        status: success ? 'done' : 'error',
                        elapsed,
                        result,
                    };
                    break;
                }
            }
            return { toolActivities: next };
        });
    },
    clearToolActivities: () => set({ toolActivities: [] }),
    resetConversation: (keepSessionId = false) => set((s) => ({
        messages: [],
        toolActivities: [],
        isStreaming: false,
        streamBuffer: '',
        sessionId: keepSessionId ? s.sessionId : null,
        cardsById: {},
        cardIdsByMessageId: {},
    })),
    clearMessages: () => set({
        messages: [],
        toolActivities: [],
        isStreaming: false,
        streamBuffer: '',
        sessionId: null,
        cardsById: {},
        cardIdsByMessageId: {},
    }),
}));
