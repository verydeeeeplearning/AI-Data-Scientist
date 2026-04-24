import { createMobileError } from '../errors/mobileError';

export interface OutboxItem {
  readonly id: string;
  readonly kind: 'approval';
  readonly payload: Record<string, unknown>;
  readonly enqueuedAt: number;
  readonly attemptCount: number;
}

export interface IndexedDbOutbox {
  enqueue(item: Omit<OutboxItem, 'id'> & { id?: string }): Promise<string>;
  dequeue(id: string): Promise<void>;
  list(): Promise<OutboxItem[]>;
  clear(): Promise<void>;
  incrementAttemptCount(id: string): Promise<number>;
}

type SyncCapableRegistration = ServiceWorkerRegistration & {
  sync?: {
    register(tag: string): Promise<void>;
  };
};

const DB_NAME = 'ds-agent-outbox';
const DB_VERSION = 1;
const STORE_NAME = 'pending';
const INDEX_ENQUEUED_AT = 'enqueuedAt';

export const OUTBOX_CHANGED_EVENT = 'ds-agent-outbox-changed';
export const OUTBOX_SYNC_TAG = 'ds-agent-outbox-flush';

function getIndexedDb(factory?: IDBFactory): IDBFactory {
  const resolved = factory ?? globalThis.indexedDB;
  if (!resolved) {
    throw createMobileError('outbox_unavailable', 'indexedDB is unavailable');
  }
  return resolved;
}

function requestToPromise<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(
      createMobileError(
        'outbox_request_failed',
        request.error?.message ?? 'IndexedDB request failed',
        request.error?.message,
      ),
    );
  });
}

function transactionDone(transaction: IDBTransaction): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(
      createMobileError(
        'outbox_transaction_failed',
        transaction.error?.message ?? 'IndexedDB transaction failed',
        transaction.error?.message,
      ),
    );
    transaction.onabort = () => reject(
      createMobileError(
        'outbox_transaction_aborted',
        transaction.error?.message ?? 'IndexedDB transaction aborted',
        transaction.error?.message,
      ),
    );
  });
}

function buildId(): string {
  const cryptoRef = globalThis.crypto as Crypto | undefined;
  if (cryptoRef?.randomUUID) {
    return cryptoRef.randomUUID();
  }
  return `outbox-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function emitOutboxChanged(): void {
  if (typeof window === 'undefined') {
    return;
  }
  if (typeof window.dispatchEvent !== 'function' || typeof CustomEvent === 'undefined') {
    return;
  }
  window.dispatchEvent(new CustomEvent(OUTBOX_CHANGED_EVENT));
}

async function openDatabase(factory?: IDBFactory): Promise<IDBDatabase> {
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

export function createIndexedDbOutbox(factory?: IDBFactory): IndexedDbOutbox {
  return {
    async enqueue(item): Promise<string> {
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
      } satisfies OutboxItem);
      await transactionDone(transaction);
      emitOutboxChanged();
      return id;
    },

    async dequeue(id: string): Promise<void> {
      if (!id.trim()) return;
      const db = await openDatabase(factory);
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      transaction.objectStore(STORE_NAME).delete(id);
      await transactionDone(transaction);
      emitOutboxChanged();
    },

    async list(): Promise<OutboxItem[]> {
      const db = await openDatabase(factory);
      const transaction = db.transaction(STORE_NAME, 'readonly');
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAll();
      const result = await requestToPromise(request);
      await transactionDone(transaction);
      return (Array.isArray(result) ? result : [])
        .filter((item): item is OutboxItem => {
          if (!item || typeof item !== 'object') return false;
          const candidate = item as Partial<OutboxItem>;
          return (
            typeof candidate.id === 'string'
            && candidate.kind === 'approval'
            && typeof candidate.payload === 'object'
            && candidate.payload !== null
            && typeof candidate.enqueuedAt === 'number'
            && typeof candidate.attemptCount === 'number'
          );
        })
        .sort((left, right) => left.enqueuedAt - right.enqueuedAt);
    },

    async clear(): Promise<void> {
      const db = await openDatabase(factory);
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      transaction.objectStore(STORE_NAME).clear();
      await transactionDone(transaction);
      emitOutboxChanged();
    },

    async incrementAttemptCount(id: string): Promise<number> {
      if (!id.trim()) {
        throw createMobileError('outbox_id_required', 'id is required');
      }
      const db = await openDatabase(factory);
      const transaction = db.transaction(STORE_NAME, 'readwrite');
      const store = transaction.objectStore(STORE_NAME);
      const existing = await requestToPromise(store.get(id));
      if (!existing || typeof existing !== 'object') {
        await transactionDone(transaction);
        return 0;
      }
      const item = existing as OutboxItem;
      const next = item.attemptCount + 1;
      store.put({ ...item, attemptCount: next } satisfies OutboxItem);
      await transactionDone(transaction);
      emitOutboxChanged();
      return next;
    },
  };
}

export async function registerOutboxBackgroundSync(): Promise<boolean> {
  if (typeof navigator === 'undefined' || !('serviceWorker' in navigator)) {
    return false;
  }
  try {
    const registration = (await navigator.serviceWorker.ready) as SyncCapableRegistration;
    if (!registration.sync?.register) {
      return false;
    }
    await registration.sync.register(OUTBOX_SYNC_TAG);
    return true;
  } catch {
    return false;
  }
}

export const indexedDbOutbox = createIndexedDbOutbox();
