import type {
  ListRunExportArtifactsInput,
  ListRunExportArtifactsResult,
  RunExportArtifactCandidate,
  RunExportArtifactFile,
} from '../../application/workspace/listRunExportArtifactsPort';
import { getBackendBase } from '../../utils/backendUrl';

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail;
  }
  return fallback;
}

function normalizeArtifactFile(payload: unknown): RunExportArtifactFile | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const name = typeof record.name === 'string' ? record.name.trim() : '';
  const path = typeof record.path === 'string' ? record.path.trim() : '';
  const type = typeof record.type === 'string' ? record.type.trim() : '';
  const size = typeof record.size === 'number' ? record.size : 0;
  const modifiedAt = typeof record.modifiedAt === 'number' ? record.modifiedAt : undefined;
  if (!name || !path || !type || !Number.isFinite(size)) {
    return null;
  }
  return {
    name,
    path,
    size,
    type,
    modifiedAt,
  };
}

function normalizeArtifactCandidate(payload: unknown): RunExportArtifactCandidate | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  const record = payload as Record<string, unknown>;
  const name = typeof record.name === 'string' ? record.name.trim() : '';
  const path = typeof record.path === 'string' ? record.path.trim() : '';
  const type = typeof record.type === 'string' ? record.type.trim() : '';
  const formats = Array.isArray(record.formats)
    ? record.formats
        .filter((entry): entry is string => typeof entry === 'string' && entry.trim().length > 0)
        .map((entry) => entry.trim())
    : [];
  if (!name || !path || !type || formats.length === 0) {
    return null;
  }
  return {
    name,
    path,
    type,
    formats,
  };
}

export async function fetchRunExportArtifacts(
  input: ListRunExportArtifactsInput,
): Promise<ListRunExportArtifactsResult> {
  const encodedRunId = encodeURIComponent(input.runId);
  const response = await fetch(`${getBackendBase()}/api/export/runs/${encodedRunId}/artifacts`);

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Ignore non-JSON bodies.
    }
    throw new Error(
      extractErrorMessage(
        payload,
        `Export artifacts request failed with status ${response.status}`,
      ),
    );
  }

  const payload = (await response.json()) as Record<string, unknown>;
  const run = payload.run;
  const runRecord = run && typeof run === 'object' ? (run as Record<string, unknown>) : null;
  const runId =
    typeof runRecord?.runId === 'string' && runRecord.runId.trim().length > 0
      ? runRecord.runId.trim()
      : input.runId;
  const sessionId =
    typeof runRecord?.sessionId === 'string' && runRecord.sessionId.trim().length > 0
      ? runRecord.sessionId.trim()
      : '';

  return {
    runId,
    sessionId,
    files: Array.isArray(payload.files)
      ? payload.files
          .map((entry) => normalizeArtifactFile(entry))
          .filter((entry): entry is RunExportArtifactFile => entry !== null)
      : [],
    exportCandidates: Array.isArray(payload.exportCandidates)
      ? payload.exportCandidates
          .map((entry) => normalizeArtifactCandidate(entry))
          .filter((entry): entry is RunExportArtifactCandidate => entry !== null)
      : [],
  };
}
