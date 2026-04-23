import { useCallback } from 'react';
import type {
  PromoteAudience,
  PromoteToArtifactPort,
} from '../application/run/promoteToArtifactPort';
import { PROMOTE_AUDIENCES } from '../application/run/promoteToArtifactPort';
import { useWs } from './WsProvider';

interface RunPromoteResponse {
  artifact?: {
    artifactId?: string;
    runId?: string;
    cardId?: string;
    audience?: string;
    title?: string;
    createdAt?: number;
  };
}

function coerceAudience(value: unknown): PromoteAudience {
  if (typeof value === 'string') {
    const normalized = value.toLowerCase() as PromoteAudience;
    if ((PROMOTE_AUDIENCES as readonly string[]).includes(normalized)) {
      return normalized;
    }
  }
  return 'ds';
}

export function usePromoteToArtifact(): PromoteToArtifactPort {
  const { rpc } = useWs();
  return useCallback<PromoteToArtifactPort>(
    async ({ runId, cardId, audience, title }) => {
      const params: Record<string, unknown> = {
        runId,
        cardId,
        audience,
      };
      if (typeof title === 'string' && title.trim().length > 0) {
        params.title = title;
      }
      const response = (await rpc('run.promote', params)) as RunPromoteResponse;
      const payload = response?.artifact ?? {};
      return {
        artifactId: typeof payload.artifactId === 'string' ? payload.artifactId : '',
        runId: typeof payload.runId === 'string' ? payload.runId : runId,
        cardId: typeof payload.cardId === 'string' ? payload.cardId : cardId,
        audience: coerceAudience(payload.audience ?? audience),
        title: typeof payload.title === 'string' ? payload.title : cardId,
        createdAt:
          typeof payload.createdAt === 'number'
            ? payload.createdAt
            : Date.now() / 1000,
      };
    },
    [rpc],
  );
}
