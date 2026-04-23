import { useCallback, useEffect, useState } from 'react';
import { useWs } from './WsProvider';

export interface PromotedArtifactRecord {
  readonly artifactId: string;
  readonly runId: string;
  readonly cardId: string;
  readonly audience: string;
  readonly title: string;
  readonly createdAt: number;
}

interface PromotedArtifactsRpcResponse {
  artifacts?: unknown[];
}

function normalizePromotedArtifact(value: unknown): PromotedArtifactRecord | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const record = value as Record<string, unknown>;
  const artifactId = typeof record.artifactId === 'string' ? record.artifactId : '';
  const runId = typeof record.runId === 'string' ? record.runId : '';
  const cardId = typeof record.cardId === 'string' ? record.cardId : '';
  if (!artifactId || !runId || !cardId) {
    return null;
  }
  return {
    artifactId,
    runId,
    cardId,
    audience: typeof record.audience === 'string' ? record.audience : 'ds',
    title: typeof record.title === 'string' ? record.title : cardId,
    createdAt: typeof record.createdAt === 'number' ? record.createdAt : 0,
  };
}

export function useRunPromotedArtifacts(
  runId: string | null | undefined,
  cardId: string | null | undefined,
  refreshToken = 0,
) {
  const { rpc } = useWs();
  const [artifacts, setArtifacts] = useState<PromotedArtifactRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const normalizedRunId = runId?.trim() ?? '';
    if (!normalizedRunId) {
      setArtifacts([]);
      setLoading(false);
      setError(null);
      return [];
    }
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, unknown> = { runId: normalizedRunId, limit: 10 };
      if (cardId && cardId.trim()) {
        params.cardId = cardId.trim();
      }
      const response = (await rpc('run.list_promoted', params)) as PromotedArtifactsRpcResponse;
      const nextArtifacts = Array.isArray(response.artifacts)
        ? response.artifacts
            .map(normalizePromotedArtifact)
            .filter((artifact): artifact is PromotedArtifactRecord => artifact !== null)
        : [];
      setArtifacts(nextArtifacts);
      return nextArtifacts;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setArtifacts([]);
      setError(message);
      return [];
    } finally {
      setLoading(false);
    }
  }, [cardId, rpc, runId]);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshToken]);

  return { artifacts, loading, error, refresh };
}
