import { useCallback } from 'react';
import type { ResumeFromCheckpointPort } from '../application/run/resumeFromCheckpointPort';
import { useWs } from './WsProvider';

interface RunStartResponse {
  runId?: string;
  sessionId?: string;
  resumedFromCheckpoint?: boolean;
}

export function useResumeFromCheckpoint(): ResumeFromCheckpointPort {
  const { rpc } = useWs();
  return useCallback<ResumeFromCheckpointPort>(
    async ({ sessionId, message, model }) => {
      const params: Record<string, unknown> = {
        sessionId,
        message,
        resumeFromCheckpoint: true,
      };
      if (model) {
        params.model = model;
      }
      const response = (await rpc('run.start', params)) as RunStartResponse;
      return {
        resumed: Boolean(response?.resumedFromCheckpoint),
        runId: typeof response?.runId === 'string' ? response.runId : null,
        sessionId:
          typeof response?.sessionId === 'string' ? response.sessionId : sessionId,
      };
    },
    [rpc],
  );
}
