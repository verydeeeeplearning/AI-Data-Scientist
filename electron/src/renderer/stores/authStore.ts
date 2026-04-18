/**
 * Shared auth snapshot for provider status, OAuth accounts, and masked keys.
 */

import { create } from 'zustand';

export interface OAuthAccountStatus {
  authenticated: boolean;
  email?: string;
  accountId?: string;
  managedBy?: string;
  expiresAt?: number | null;
  expired?: boolean;
}

export interface ProviderHealthStatus {
  id: string;
  label: string;
  status: 'ok' | 'degraded' | 'unavailable';
  hasCredentials: boolean;
  authStatus: string;
  latencyMs?: number | null;
  message: string;
  checkedAt?: number | null;
  modelCount?: number | null;
}

export interface ProviderFallbackEvent {
  from: string;
  to: string;
  reason: string;
  message: string;
  occurredAt: number;
  sessionId?: string | null;
  surface?: string | null;
}

export interface AuthSnapshot {
  providerStatuses: Record<string, string>;
  maskedKeys: Record<string, string>;
  oauthStatuses: Record<string, OAuthAccountStatus>;
  providerHealth: Record<string, ProviderHealthStatus>;
}

interface AuthState extends AuthSnapshot {
  loading: boolean;
  lastUpdatedAt: number | null;
  lastFallbackEvent: ProviderFallbackEvent | null;

  setSnapshot: (snapshot: AuthSnapshot) => void;
  setFallbackEvent: (event: ProviderFallbackEvent) => void;
  setLoading: (loading: boolean) => void;
  resetAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  providerStatuses: {},
  maskedKeys: {},
  oauthStatuses: {},
  providerHealth: {},
  loading: false,
  lastUpdatedAt: null,
  lastFallbackEvent: null,

  setSnapshot: (snapshot) =>
    set({
      ...snapshot,
      lastUpdatedAt: Date.now(),
    }),
  setFallbackEvent: (lastFallbackEvent) => set({ lastFallbackEvent }),
  setLoading: (loading) => set({ loading }),
  resetAuth: () =>
    set({
      providerStatuses: {},
      maskedKeys: {},
      oauthStatuses: {},
      providerHealth: {},
      loading: false,
      lastUpdatedAt: null,
      lastFallbackEvent: null,
    }),
}));
