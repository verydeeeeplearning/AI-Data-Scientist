"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createTrustStore = createTrustStore;
exports.bindTrustStoreHook = bindTrustStoreHook;
exports.getTrustEntry = getTrustEntry;
const zustand_1 = require("zustand");
const vanilla_1 = require("zustand/vanilla");
const trustMapper_1 = require("./trustMapper");
const EMPTY_ENTRY = Object.freeze({
    state: 'idle',
    data: null,
    error: null,
    requestedAt: null,
    receivedAt: null,
});
function normalizeResultId(resultId) {
    const normalized = resultId.trim();
    return normalized.length > 0 ? normalized : null;
}
function createEntryPatch(entry) {
    return {
        ...EMPTY_ENTRY,
        ...entry,
    };
}
function createTrustStore(fetcher) {
    const inflight = new Map();
    return (0, vanilla_1.createStore)((set, get) => ({
        entries: {},
        async ensure(resultId, options) {
            const normalizedResultId = normalizeResultId(resultId);
            if (!normalizedResultId) {
                return null;
            }
            const existing = get().entries[normalizedResultId];
            if (!options?.force && existing?.state === 'loaded' && existing.data) {
                return existing.data;
            }
            if (!options?.force) {
                const pending = inflight.get(normalizedResultId);
                if (pending) {
                    return pending;
                }
            }
            const requestedAt = Date.now();
            set((state) => ({
                entries: {
                    ...state.entries,
                    [normalizedResultId]: createEntryPatch({
                        ...(state.entries[normalizedResultId] ?? {}),
                        state: 'loading',
                        error: null,
                        requestedAt,
                    }),
                },
            }));
            const request = fetcher(normalizedResultId)
                .then((data) => {
                const receivedAt = Date.now();
                set((state) => ({
                    entries: {
                        ...state.entries,
                        [normalizedResultId]: createEntryPatch({
                            state: 'loaded',
                            data,
                            error: null,
                            requestedAt,
                            receivedAt,
                        }),
                    },
                }));
                return data;
            })
                .catch((error) => {
                const receivedAt = Date.now();
                const message = error instanceof Error ? error.message : 'Trust request failed';
                set((state) => ({
                    entries: {
                        ...state.entries,
                        [normalizedResultId]: createEntryPatch({
                            ...(state.entries[normalizedResultId] ?? {}),
                            state: 'error',
                            error: message,
                            receivedAt,
                        }),
                    },
                }));
                throw error;
            })
                .finally(() => {
                inflight.delete(normalizedResultId);
            });
            inflight.set(normalizedResultId, request);
            return request;
        },
        prime(resultId, payload) {
            const normalizedResultId = normalizeResultId(resultId);
            if (!normalizedResultId) {
                return null;
            }
            const data = (0, trustMapper_1.mapTrustPayload)(normalizedResultId, payload);
            set((state) => ({
                entries: {
                    ...state.entries,
                    [normalizedResultId]: createEntryPatch({
                        state: 'loaded',
                        data,
                        error: null,
                        requestedAt: state.entries[normalizedResultId]?.requestedAt ?? null,
                        receivedAt: Date.now(),
                    }),
                },
            }));
            return data;
        },
        invalidate(resultId) {
            if (typeof resultId === 'undefined') {
                inflight.clear();
                set({ entries: {} });
                return;
            }
            const normalizedResultId = normalizeResultId(resultId);
            if (!normalizedResultId) {
                return;
            }
            inflight.delete(normalizedResultId);
            set((state) => {
                const nextEntries = { ...state.entries };
                delete nextEntries[normalizedResultId];
                return { entries: nextEntries };
            });
        },
    }));
}
function bindTrustStoreHook(store) {
    return function useBoundTrustStore(selector) {
        return (0, zustand_1.useStore)(store, selector);
    };
}
function getTrustEntry(state, resultId) {
    const normalizedResultId = resultId ? normalizeResultId(resultId) : null;
    if (!normalizedResultId) {
        return EMPTY_ENTRY;
    }
    return state.entries[normalizedResultId] ?? EMPTY_ENTRY;
}
