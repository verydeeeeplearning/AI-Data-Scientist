import { useCallback } from 'react';
import type { SaveCheckpointPort } from '../application/run/saveCheckpointPort';
import { useWs } from './WsProvider';

interface CheckpointSaveResponse {
  checkpoint?: {
    id?: string;
    sessionId?: string;
    name?: string;
    transcriptStep?: number;
    createdAt?: number;
    description?: string | null;
  };
}

export function useSaveCheckpoint(): SaveCheckpointPort {
  const { rpc } = useWs();
  return useCallback<SaveCheckpointPort>(
    async ({ sessionId, name, description }) => {
      const params: Record<string, unknown> = { sessionId, name };
      if (description !== undefined && description !== null && description !== '') {
        params.description = description;
      }
      const response = (await rpc('checkpoint.save', params)) as CheckpointSaveResponse;
      const ckpt = response?.checkpoint ?? {};
      return {
        checkpointId: typeof ckpt.id === 'string' ? ckpt.id : '',
        sessionId: typeof ckpt.sessionId === 'string' ? ckpt.sessionId : sessionId,
        name: typeof ckpt.name === 'string' ? ckpt.name : name,
        transcriptStep:
          typeof ckpt.transcriptStep === 'number' ? ckpt.transcriptStep : 0,
        createdAt: typeof ckpt.createdAt === 'number' ? ckpt.createdAt : Date.now() / 1000,
        description:
          typeof ckpt.description === 'string' && ckpt.description.length > 0
            ? ckpt.description
            : null,
      };
    },
    [rpc],
  );
}
