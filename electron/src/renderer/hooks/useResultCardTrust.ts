import { useEffect } from 'react';
import { getTrustEntry } from '../application/trust/trustStore';
import { useTrustStore } from './useTrustStore';

export interface UseResultCardTrustOptions {
  readonly enabled?: boolean;
  readonly initialData?: unknown;
}

export interface ResultCardTrustState {
  readonly trust: ReturnType<typeof getTrustEntry>['data'];
  readonly badges: NonNullable<ReturnType<typeof getTrustEntry>['data']>['badges'];
  readonly state: ReturnType<typeof getTrustEntry>['state'];
  readonly error: string | null;
  readonly isIdle: boolean;
  readonly isLoading: boolean;
  readonly isLoaded: boolean;
  readonly isError: boolean;
  load: (options?: { force?: boolean }) => Promise<ReturnType<typeof getTrustEntry>['data']>;
  refresh: () => Promise<ReturnType<typeof getTrustEntry>['data']>;
}

const EMPTY_BADGES: readonly [] = Object.freeze([]);

export function useResultCardTrust(
  resultId: string | null | undefined,
  options: UseResultCardTrustOptions = {},
): ResultCardTrustState {
  const entry = useTrustStore((state) => getTrustEntry(state, resultId));
  const ensure = useTrustStore((state) => state.ensure);
  const prime = useTrustStore((state) => state.prime);

  useEffect(() => {
    if (!resultId || options.initialData == null) {
      return;
    }
    prime(resultId, options.initialData);
  }, [options.initialData, prime, resultId]);

  useEffect(() => {
    if (!options.enabled || !resultId || entry.state !== 'idle' || options.initialData != null) {
      return;
    }
    void ensure(resultId);
  }, [ensure, entry.state, options.enabled, options.initialData, resultId]);

  return {
    trust: entry.data,
    badges: entry.data?.badges ?? EMPTY_BADGES,
    state: entry.state,
    error: entry.error,
    isIdle: entry.state === 'idle',
    isLoading: entry.state === 'loading',
    isLoaded: entry.state === 'loaded',
    isError: entry.state === 'error',
    load: (loadOptions) => (resultId ? ensure(resultId, loadOptions) : Promise.resolve(null)),
    refresh: () => (resultId ? ensure(resultId, { force: true }) : Promise.resolve(null)),
  };
}
