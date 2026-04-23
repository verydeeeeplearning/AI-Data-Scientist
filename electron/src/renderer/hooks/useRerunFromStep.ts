import { useCallback } from 'react';
import type { RerunFromStepPort } from '../application/run/rerunFromStepPort';
import { useWs } from './WsProvider';

interface RunRerunResponse {
  runId?: string;
  sessionId?: string;
  branchedFromRunId?: string | null;
  rerunFromNodeId?: string | null;
}

export function useRerunFromStep(): RerunFromStepPort {
  const { rpc } = useWs();
  return useCallback<RerunFromStepPort>(
    async ({ parentRunId, planNodeId, message, model }) => {
      const params: Record<string, unknown> = { parentRunId, planNodeId };
      if (typeof message === 'string' && message.trim().length > 0) {
        params.message = message;
      }
      if (typeof model === 'string' && model.trim().length > 0) {
        params.model = model;
      }
      const response = (await rpc('run.rerun', params)) as RunRerunResponse;
      return {
        runId: typeof response?.runId === 'string' ? response.runId : '',
        sessionId: typeof response?.sessionId === 'string' ? response.sessionId : '',
        branchedFromRunId:
          typeof response?.branchedFromRunId === 'string'
            ? response.branchedFromRunId
            : null,
        rerunFromNodeId:
          typeof response?.rerunFromNodeId === 'string'
            ? response.rerunFromNodeId
            : null,
      };
    },
    [rpc],
  );
}
