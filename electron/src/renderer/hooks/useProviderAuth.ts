/**
 * Keeps provider auth state synchronized with backend RPCs and OAuth events.
 */

import { useCallback, useEffect, useRef } from 'react';
import {
  useAuthStore,
  type AuthSnapshot,
  type OAuthAccountStatus,
  type ProviderFallbackEvent,
  type ProviderHealthStatus,
} from '../stores/authStore';
import { useVisiblePolling } from './useVisiblePolling';

type OnFn = (event: string, handler: (payload: Record<string, unknown>) => void) => () => void;
type RpcFn = (
  method: string,
  params?: Record<string, unknown>
) => Promise<Record<string, unknown>>;

function normalizeOauthStatuses(
  payload: unknown,
): Record<string, OAuthAccountStatus> {
  if (!payload || typeof payload !== 'object') {
    return {};
  }

  const raw = payload as Record<string, unknown>;
  const normalized: Record<string, OAuthAccountStatus> = {};
  for (const [provider, value] of Object.entries(raw)) {
    if (!value || typeof value !== 'object') {
      continue;
    }
    const entry = value as Record<string, unknown>;
    normalized[provider] = {
      authenticated: Boolean(entry.authenticated),
      email: typeof entry.email === 'string' ? entry.email : undefined,
      accountId: typeof entry.account_id === 'string' ? entry.account_id : undefined,
      managedBy: typeof entry.managed_by === 'string' ? entry.managed_by : undefined,
      expiresAt: typeof entry.expires_at === 'number' ? entry.expires_at : null,
      expired: Boolean(entry.expired),
    };
  }
  return normalized;
}

function normalizeProviderHealth(
  payload: unknown,
): Record<string, ProviderHealthStatus> {
  if (!Array.isArray(payload)) {
    return {};
  }

  const normalized: Record<string, ProviderHealthStatus> = {};
  for (const item of payload) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    const entry = item as Record<string, unknown>;
    const id = typeof entry.id === 'string' ? entry.id : '';
    if (!id) {
      continue;
    }

    normalized[id] = {
      id,
      label: typeof entry.label === 'string' ? entry.label : id,
      status:
        entry.status === 'ok' || entry.status === 'degraded' || entry.status === 'unavailable'
          ? entry.status
          : 'unavailable',
      hasCredentials: Boolean(entry.hasCredentials),
      authStatus: typeof entry.authStatus === 'string' ? entry.authStatus : 'unknown',
      latencyMs: typeof entry.latencyMs === 'number' ? entry.latencyMs : null,
      message: typeof entry.message === 'string' ? entry.message : '',
      checkedAt: typeof entry.checkedAt === 'number' ? entry.checkedAt : null,
      modelCount: typeof entry.modelCount === 'number' ? entry.modelCount : null,
    };
  }

  return normalized;
}

function normalizeFallbackEvent(payload: unknown): ProviderFallbackEvent | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }

  const entry = payload as Record<string, unknown>;
  const from = typeof entry.from === 'string' ? entry.from : '';
  const to = typeof entry.to === 'string' ? entry.to : '';
  if (!from || !to) {
    return null;
  }

  return {
    from,
    to,
    reason: typeof entry.reason === 'string' ? entry.reason : 'provider_error',
    message:
      typeof entry.message === 'string'
        ? entry.message
        : `Switched from ${from} to ${to}.`,
    occurredAt: typeof entry.occurredAt === 'number' ? entry.occurredAt : Date.now(),
    sessionId: typeof entry.sessionId === 'string' ? entry.sessionId : null,
    surface: typeof entry.surface === 'string' ? entry.surface : null,
  };
}

export async function fetchAuthSnapshot(rpc: RpcFn): Promise<AuthSnapshot> {
  const [providerData, oauthData, maskedKeys, providerHealthData] = await Promise.allSettled([
    rpc('provider.authStatus'),
    rpc('oauth.status'),
    getMaskedApiKeys(rpc),
    rpc('provider.health'),
  ]);

  return {
    providerStatuses:
      providerData.status === 'fulfilled'
        ? ((providerData.value.statuses as Record<string, string>) ?? {})
        : {},
    oauthStatuses:
      oauthData.status === 'fulfilled'
        ? normalizeOauthStatuses(oauthData.value.providers)
        : {},
    maskedKeys:
      maskedKeys.status === 'fulfilled'
        ? maskedKeys.value
        : {},
    providerHealth:
      providerHealthData.status === 'fulfilled'
        ? normalizeProviderHealth(providerHealthData.value.providers)
        : {},
  };
}

async function getMaskedApiKeys(rpc: RpcFn): Promise<Record<string, string>> {
  if (window.electronAPI?.getMaskedApiKeys) {
    try {
      const result = await window.electronAPI.getMaskedApiKeys();
      if (result.available) {
        return result.maskedKeys ?? {};
      }
    } catch (error) {
      console.warn('[useProviderAuth] desktop masked key lookup failed:', error);
    }
  }

  const apiKeyData = await rpc('config.getApiKeys');
  return (apiKeyData.keys as Record<string, string>) ?? {};
}

export function useProviderAuth(on: OnFn, rpc: RpcFn, connected: boolean) {
  const setSnapshot = useAuthStore((s) => s.setSnapshot);
  const setFallbackEvent = useAuthStore((s) => s.setFallbackEvent);
  const setLoading = useAuthStore((s) => s.setLoading);
  const resetAuth = useAuthStore((s) => s.resetAuth);
  const refreshGenerationRef = useRef(0);

  const refreshAuth = useCallback(async () => {
    setLoading(true);
    try {
      setSnapshot(await fetchAuthSnapshot(rpc));
    } finally {
      setLoading(false);
    }
  }, [rpc, setLoading, setSnapshot]);

  useEffect(() => {
    refreshGenerationRef.current += 1;
    if (!connected) {
      resetAuth();
    }

    return () => {
      refreshGenerationRef.current += 1;
    };
  }, [connected, refreshAuth, resetAuth]);

  const guardedRefresh = useCallback(async () => {
    const generation = refreshGenerationRef.current;
    try {
      await refreshAuth();
    } catch (err) {
      if (refreshGenerationRef.current === generation) {
        console.warn('[useProviderAuth] refresh failed:', err);
      }
    }
  }, [refreshAuth]);

  useVisiblePolling(() => {
    void guardedRefresh();
  }, { intervalMs: 10_000, enabled: connected });

  useEffect(() => {
    if (!connected) {
      return;
    }

    const unsubs = [
      on('oauth.complete', () => {
        void guardedRefresh();
      }),
      on('provider.fallback', (payload) => {
        const fallbackEvent = normalizeFallbackEvent(payload);
        if (fallbackEvent) {
          setFallbackEvent(fallbackEvent);
        }
      }),
    ];

    return () => {
      unsubs.forEach((unsub) => unsub());
    };
  }, [connected, guardedRefresh, on, setFallbackEvent]);
}
