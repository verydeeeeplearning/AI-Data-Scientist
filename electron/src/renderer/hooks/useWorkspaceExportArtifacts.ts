import { useCallback, useEffect, useState } from 'react';
import { listRunExportArtifacts } from '../application/workspace/listRunExportArtifacts';
import type {
  ListRunExportArtifactsPort,
  RunExportArtifactCandidate,
  RunExportArtifactFile,
} from '../application/workspace/listRunExportArtifactsPort';
import { fetchRunExportArtifacts } from '../infrastructure/api/exportArtifactsApi';

interface WorkspaceExportArtifactsState {
  readonly runId: string | null;
  readonly sessionId: string | null;
  readonly files: readonly RunExportArtifactFile[];
  readonly exportCandidates: readonly RunExportArtifactCandidate[];
  readonly loading: boolean;
  readonly error: string | null;
  readonly refresh: () => Promise<void>;
}

export function useWorkspaceExportArtifacts(
  runId: string | null | undefined,
): WorkspaceExportArtifactsState {
  const [resolvedRunId, setResolvedRunId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [files, setFiles] = useState<readonly RunExportArtifactFile[]>([]);
  const [exportCandidates, setExportCandidates] = useState<readonly RunExportArtifactCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const port = useCallback<ListRunExportArtifactsPort>(
    async ({ runId: requestedRunId }) => fetchRunExportArtifacts({ runId: requestedRunId }),
    [],
  );

  const refresh = useCallback(async () => {
    const normalizedRunId = runId?.trim() ?? '';
    if (!normalizedRunId) {
      setResolvedRunId(null);
      setSessionId(null);
      setFiles([]);
      setExportCandidates([]);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await listRunExportArtifacts(port, {
        runId: normalizedRunId,
      });
      setResolvedRunId(result.runId);
      setSessionId(result.sessionId);
      setFiles(result.files);
      setExportCandidates(result.exportCandidates);
    } catch (err) {
      setResolvedRunId(normalizedRunId);
      setSessionId(null);
      setFiles([]);
      setExportCandidates([]);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [port, runId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    runId: resolvedRunId,
    sessionId,
    files,
    exportCandidates,
    loading,
    error,
    refresh,
  };
}
