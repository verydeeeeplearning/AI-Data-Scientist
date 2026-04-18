/**
 * useModels hook — fetches model catalog from backend.
 *
 * Calls provider.models RPC on connect, groups by authType.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

export interface ModelEntry {
  id: string;
  provider: string;
  displayName: string;
  maxContext: number;
  maxOutput: number;
  authType: 'api_key' | 'oauth' | 'free_api_key' | 'local';
  legacy: boolean;
}

export interface ModelGroup {
  title: string;
  authType: string;
  models: ModelEntry[];
}

type RpcFn = (method: string, params?: Record<string, unknown>) => Promise<Record<string, unknown>>;

const AUTH_TYPE_ORDER: Record<string, number> = {
  oauth: 0,
  free_api_key: 1,
  api_key: 2,
  local: 3,
};

const AUTH_TYPE_TITLES: Record<string, string> = {
  oauth: 'OAuth (Free)',
  free_api_key: 'Free API',
  api_key: 'API Key',
  local: 'Local',
};

function groupModels(models: ModelEntry[], showLegacy: boolean): ModelGroup[] {
  const filtered = showLegacy ? models : models.filter((m) => !m.legacy);

  const groups = new Map<string, ModelEntry[]>();
  for (const m of filtered) {
    const key = m.authType;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(m);
  }

  return Array.from(groups.entries())
    .sort(([a], [b]) => (AUTH_TYPE_ORDER[a] ?? 99) - (AUTH_TYPE_ORDER[b] ?? 99))
    .map(([authType, models]) => ({
      title: AUTH_TYPE_TITLES[authType] ?? authType,
      authType,
      models,
    }));
}

export function useModels(
  rpc: RpcFn,
  connected: boolean,
) {
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showLegacy, setShowLegacy] = useState(false);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    try {
      const data = await rpc('provider.models');
      setModels((data.models as ModelEntry[]) ?? []);
    } catch {
      // Fallback: empty — UI can still show text input
    } finally {
      setLoading(false);
    }
  }, [rpc]);

  useEffect(() => {
    if (connected) fetchModels();
  }, [connected, fetchModels]);

  const grouped = useMemo(() => groupModels(models, showLegacy), [models, showLegacy]);

  return { models, grouped, loading, showLegacy, setShowLegacy, refetch: fetchModels };
}
