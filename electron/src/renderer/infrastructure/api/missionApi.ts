import type { MissionContext } from '../../domain/mission';
import type {
  PauseAgentInput,
  PauseAgentResult,
} from '../../application/mission/pauseAgentPort';

interface MissionApiResponse {
  mission: MissionContext;
}

interface PauseAgentApiResponse {
  paused: boolean;
  previousStatus: 'running' | 'idle' | 'paused';
}

function getBackendBaseUrl(): string {
  const params = new URLSearchParams(window.location.search);
  const rawPort = params.get('port');
  const port = rawPort ? Number.parseInt(rawPort, 10) : 18790;
  return `http://127.0.0.1:${Number.isFinite(port) ? port : 18790}`;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  return fallback;
}

export async function fetchCurrentMissionContext(sessionId: string): Promise<MissionContext> {
  const query = new URLSearchParams({ sessionId });
  const response = await fetch(`${getBackendBaseUrl()}/api/mission/current?${query.toString()}`, {
    cache: 'no-store',
  });

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Ignore non-JSON error bodies.
    }
    throw new Error(
      extractErrorMessage(payload, `Mission context request failed with status ${response.status}`),
    );
  }

  const payload = (await response.json()) as MissionApiResponse;
  return payload.mission;
}

export async function requestAgentPause(input: PauseAgentInput): Promise<PauseAgentResult> {
  const response = await fetch(`${getBackendBaseUrl()}/api/mission/pause`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessionId: input.sessionId,
      reason: input.reason,
    }),
  });

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Ignore non-JSON error bodies.
    }
    throw new Error(
      extractErrorMessage(payload, `Mission pause request failed with status ${response.status}`),
    );
  }

  const payload = (await response.json()) as PauseAgentApiResponse;
  return {
    paused: payload.paused,
    previousStatus: payload.previousStatus,
  };
}
