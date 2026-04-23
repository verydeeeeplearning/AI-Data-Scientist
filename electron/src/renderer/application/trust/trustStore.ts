import { useStore } from 'zustand';
import { createStore, type StoreApi } from 'zustand/vanilla';
import type { FetchTrustPort } from './fetchTrustPort';
import { mapTrustPayload } from './trustMapper';
import type { TrustMetadata } from './trustTypes';

export type TrustLoadState = 'idle' | 'loading' | 'loaded' | 'error';

export interface TrustEntry {
  readonly state: TrustLoadState;
  readonly data: TrustMetadata | null;
  readonly error: string | null;
  readonly requestedAt: number | null;
  readonly receivedAt: number | null;
}

export interface TrustState {
  readonly entries: Record<string, TrustEntry>;
  ensure: (resultId: string, options?: { force?: boolean }) => Promise<TrustMetadata | null>;
  prime: (resultId: string, payload: unknown) => TrustMetadata | null;
  invalidate: (resultId?: string) => void;
}

export type TrustFetcher = FetchTrustPort;

const EMPTY_ENTRY: TrustEntry = Object.freeze({
  state: 'idle',
  data: null,
  error: null,
  requestedAt: null,
  receivedAt: null,
});

function normalizeResultId(resultId: string): string | null {
  const normalized = resultId.trim();
  return normalized.length > 0 ? normalized : null;
}

function createEntryPatch(entry: Partial<TrustEntry>): TrustEntry {
  return {
    ...EMPTY_ENTRY,
    ...entry,
  };
}

export function createTrustStore(fetcher: TrustFetcher): StoreApi<TrustState> {
  const inflight = new Map<string, Promise<TrustMetadata | null>>();

  return createStore<TrustState>((set, get) => ({
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
        .catch((error: unknown) => {
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

      const data = mapTrustPayload(normalizedResultId, payload);
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

export function bindTrustStoreHook(store: StoreApi<TrustState>) {
  return function useBoundTrustStore<T>(selector: (state: TrustState) => T): T {
    return useStore(store, selector);
  };
}

export function getTrustEntry(state: TrustState, resultId: string | null | undefined): TrustEntry {
  const normalizedResultId = resultId ? normalizeResultId(resultId) : null;
  if (!normalizedResultId) {
    return EMPTY_ENTRY;
  }
  return state.entries[normalizedResultId] ?? EMPTY_ENTRY;
}
