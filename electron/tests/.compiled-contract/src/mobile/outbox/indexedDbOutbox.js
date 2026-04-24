"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.indexedDbOutbox = exports.OUTBOX_SYNC_TAG = exports.OUTBOX_CHANGED_EVENT = void 0;
exports.createIndexedDbOutbox = createIndexedDbOutbox;
exports.registerOutboxBackgroundSync = registerOutboxBackgroundSync;
const mobileError_1 = require("../errors/mobileError");
const DB_NAME = 'ds-agent-outbox';
const DB_VERSION = 1;
const STORE_NAME = 'pending';
const INDEX_ENQUEUED_AT = 'enqueuedAt';
exports.OUTBOX_CHANGED_EVENT = 'ds-agent-outbox-changed';
exports.OUTBOX_SYNC_TAG = 'ds-agent-outbox-flush';
function getIndexedDb(factory) {
    const resolved = factory ?? globalThis.indexedDB;
    if (!resolved) {
        throw (0, mobileError_1.createMobileError)('outbox_unavailable', 'indexedDB is unavailable');
    }
    return resolved;
}
function requestToPromise(request) {
    return new Promise((resolve, reject) => {
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject((0, mobileError_1.createMobileError)('outbox_request_failed', request.error?.message ?? 'IndexedDB request failed', request.error?.message));
    });
}
function transactionDone(transaction) {
    return new Promise((resolve, reject) => {
        transaction.oncomplete = () => resolve();
        transaction.onerror = () => reject((0, mobileError_1.createMobileError)('outbox_transaction_failed', transaction.error?.message ?? 'IndexedDB transaction failed', transaction.error?.message));
        transaction.onabort = () => reject((0, mobileError_1.createMobileError)('outbox_transaction_aborted', transaction.error?.message ?? 'IndexedDB transaction aborted', transaction.error?.message));
    });
}
function buildId() {
    const cryptoRef = globalThis.crypto;
    if (cryptoRef?.randomUUID) {
        return cryptoRef.randomUUID();
    }
    return `outbox-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}
function emitOutboxChanged() {
    if (typeof window === 'undefined') {
        return;
    }
    if (typeof window.dispatchEvent !== 'function' || typeof CustomEvent === 'undefined') {
        return;
    }
    window.dispatchEvent(new CustomEvent(exports.OUTBOX_CHANGED_EVENT));
}
async function openDatabase(factory) {
    const indexedDb = getIndexedDb(factory);
    const request = indexedDb.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
        const db = request.result;
        const store = db.objectStoreNames.contains(STORE_NAME)
            ? request.transaction?.objectStore(STORE_NAME)
            : db.createObjectStore(STORE_NAME, { keyPath: 'id' });
        if (store && !store.indexNames.contains(INDEX_ENQUEUED_AT)) {
            store.createIndex(INDEX_ENQUEUED_AT, INDEX_ENQUEUED_AT, { unique: false });
        }
    };
    return requestToPromise(request);
}
function createIndexedDbOutbox(factory) {
    return {
        async enqueue(item) {
            const db = await openDatabase(factory);
            const transaction = db.transaction(STORE_NAME, 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const id = item.id?.trim() || buildId();
            store.put({
                id,
                kind: item.kind,
                payload: item.payload,
                enqueuedAt: item.enqueuedAt,
                attemptCount: item.attemptCount,
            });
            await transactionDone(transaction);
            emitOutboxChanged();
            return id;
        },
        async dequeue(id) {
            if (!id.trim())
                return;
            const db = await openDatabase(factory);
            const transaction = db.transaction(STORE_NAME, 'readwrite');
            transaction.objectStore(STORE_NAME).delete(id);
            await transactionDone(transaction);
            emitOutboxChanged();
        },
        async list() {
            const db = await openDatabase(factory);
            const transaction = db.transaction(STORE_NAME, 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.getAll();
            const result = await requestToPromise(request);
            await transactionDone(transaction);
            return (Array.isArray(result) ? result : [])
                .filter((item) => {
                if (!item || typeof item !== 'object')
                    return false;
                const candidate = item;
                return (typeof candidate.id === 'string'
                    && candidate.kind === 'approval'
                    && typeof candidate.payload === 'object'
                    && candidate.payload !== null
                    && typeof candidate.enqueuedAt === 'number'
                    && typeof candidate.attemptCount === 'number');
            })
                .sort((left, right) => left.enqueuedAt - right.enqueuedAt);
        },
        async clear() {
            const db = await openDatabase(factory);
            const transaction = db.transaction(STORE_NAME, 'readwrite');
            transaction.objectStore(STORE_NAME).clear();
            await transactionDone(transaction);
            emitOutboxChanged();
        },
        async incrementAttemptCount(id) {
            if (!id.trim()) {
                throw (0, mobileError_1.createMobileError)('outbox_id_required', 'id is required');
            }
            const db = await openDatabase(factory);
            const transaction = db.transaction(STORE_NAME, 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const existing = await requestToPromise(store.get(id));
            if (!existing || typeof existing !== 'object') {
                await transactionDone(transaction);
                return 0;
            }
            const item = existing;
            const next = item.attemptCount + 1;
            store.put({ ...item, attemptCount: next });
            await transactionDone(transaction);
            emitOutboxChanged();
            return next;
        },
    };
}
async function registerOutboxBackgroundSync() {
    if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) {
        return false;
    }
    try {
        const registration = (await navigator.serviceWorker.ready);
        if (!registration.sync?.register) {
            return false;
        }
        await registration.sync.register(exports.OUTBOX_SYNC_TAG);
        return true;
    }
    catch {
        return false;
    }
}
exports.indexedDbOutbox = createIndexedDbOutbox();
