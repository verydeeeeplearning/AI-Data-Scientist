import { useCallback, useEffect, useState } from 'react';
import { listLineage } from '../application/run/listLineage';
import type {
  ListLineagePort,
  ListLineageResult,
  RunLineageNode,
} from '../application/run/listLineagePort';
import { useWs } from './WsProvider';

interface LineageRpcResponse {
  rootRunId?: string;
  seedRunId?: string;
  nodes?: unknown[];
}

function normalizeLineageNode(value: unknown): RunLineageNode | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const record = value as Record<string, unknown>;
  const runId = typeof record.runId === 'string' ? record.runId : '';
  const sessionId = typeof record.sessionId === 'string' ? record.sessionId : '';
  if (!runId || !sessionId) {
    return null;
  }
  return {
    runId,
    sessionId,
    status: typeof record.status === 'string' ? record.status : 'unknown',
    message: typeof record.message === 'string' ? record.message : '',
    createdAt: typeof record.createdAt === 'number' ? record.createdAt : 0,
    startedAt: typeof record.startedAt === 'number' ? record.startedAt : 0,
    finishedAt: typeof record.finishedAt === 'number' ? record.finishedAt : null,
    branchedFromRunId:
      typeof record.branchedFromRunId === 'string' ? record.branchedFromRunId : null,
    rerunFromNodeId:
      typeof record.rerunFromNodeId === 'string' ? record.rerunFromNodeId : null,
    depth: typeof record.depth === 'number' ? record.depth : 0,
    isRoot: record.isRoot === true,
    isSeed: record.isSeed === true,
  };
}

function normalizeResponse(
  response: LineageRpcResponse,
  rootRunId: string,
): ListLineageResult {
  return {
    rootRunId: typeof response.rootRunId === 'string' ? response.rootRunId : rootRunId,
    seedRunId: typeof response.seedRunId === 'string' ? response.seedRunId : rootRunId,
    nodes: Array.isArray(response.nodes)
      ? response.nodes
          .map(normalizeLineageNode)
          .filter((node): node is RunLineageNode => node !== null)
      : [],
  };
}

export function useListLineage(rootRunId: string | null | undefined) {
  const { rpc } = useWs();
  const [data, setData] = useState<ListLineageResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const port = useCallback<ListLineagePort>(
    async ({ rootRunId: requestedRootRunId }) => {
      const response = (await rpc('runs.list_lineage', {
        rootRunId: requestedRootRunId,
      })) as LineageRpcResponse;
      return normalizeResponse(response, requestedRootRunId);
    },
    [rpc],
  );

  const refresh = useCallback(async () => {
    const normalizedRootRunId = rootRunId?.trim() ?? '';
    if (!normalizedRootRunId) {
      setData(null);
      setError(null);
      setLoading(false);
      return null;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await listLineage(port, {
        rootRunId: normalizedRootRunId,
      });
      setData(result);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setData(null);
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [port, rootRunId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    rootRunId: data?.rootRunId ?? null,
    seedRunId: data?.seedRunId ?? null,
    nodes: data?.nodes ?? [],
    loading,
    error,
    refresh,
  };
}
