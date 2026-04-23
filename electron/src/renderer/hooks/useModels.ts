import { useCallback, useEffect, useMemo, useState } from 'react';

import { buildModelProfiles } from '../application/llm/buildModelProfiles';
import { groupModelsByCapability } from '../application/llm/groupModelsByCapability';
import type {
  ModelCatalogEntry,
  ModelCapabilityGroup,
  ModelProfile,
} from '../domain/llm/modelCapability';

export type ModelEntry = ModelProfile;
export type ModelGroup = ModelCapabilityGroup;

type RpcFn = (method: string, params?: Record<string, unknown>) => Promise<Record<string, unknown>>;

export function useModels(rpc: RpcFn, connected: boolean) {
  const [catalog, setCatalog] = useState<ModelCatalogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [showLegacy, setShowLegacy] = useState(false);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    try {
      const data = await rpc('provider.models');
      setCatalog((data.models as ModelCatalogEntry[]) ?? []);
    } catch {
      setCatalog([]);
    } finally {
      setLoading(false);
    }
  }, [rpc]);

  useEffect(() => {
    if (connected) {
      void fetchModels();
    }
  }, [connected, fetchModels]);

  const models = useMemo<ModelEntry[]>(() => buildModelProfiles(catalog), [catalog]);
  const grouped = useMemo<ModelGroup[]>(
    () => groupModelsByCapability(models, showLegacy),
    [models, showLegacy],
  );

  return { models, grouped, loading, showLegacy, setShowLegacy, refetch: fetchModels };
}
