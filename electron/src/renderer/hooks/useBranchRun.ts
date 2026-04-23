import { useCallback } from 'react';
import type { BranchRunPort } from '../application/run/branchRunPort';
import { useWs } from './WsProvider';

interface RunBranchResponse {
  runId?: string;
  sessionId?: string;
  branchedFromRunId?: string | null;
}

export function useBranchRun(): BranchRunPort {
  const { rpc } = useWs();
  return useCallback<BranchRunPort>(
    async ({ parentRunId, message, model, checkpointId }) => {
      const params: Record<string, unknown> = { parentRunId, message };
      if (model) {
        params.model = model;
      }
      if (checkpointId) {
        params.checkpointId = checkpointId;
      }
      const response = (await rpc('run.branch', params)) as RunBranchResponse;
      return {
        runId: typeof response?.runId === 'string' ? response.runId : '',
        sessionId: typeof response?.sessionId === 'string' ? response.sessionId : '',
        branchedFromRunId:
          typeof response?.branchedFromRunId === 'string'
            ? response.branchedFromRunId
            : null,
      };
    },
    [rpc],
  );
}
