import type { MissionContextPatch } from '../../domain/mission';
import type { MissionContextUpdatedEvent } from '../../types/events';

type OnFn = (event: string, handler: (payload: unknown) => void) => () => void;

function isMissionContextUpdate(payload: unknown): payload is MissionContextUpdatedEvent {
  if (typeof payload !== 'object' || payload === null) {
    return false;
  }

  const candidate = payload as { sessionId?: unknown };
  return (
    candidate.sessionId === undefined
    || candidate.sessionId === null
    || typeof candidate.sessionId === 'string'
  );
}

function getScopedSessionId(payload: MissionContextUpdatedEvent): string | null {
  if (typeof payload.sessionId !== 'string') {
    return null;
  }

  const normalized = payload.sessionId.trim();
  return normalized ? normalized : null;
}

function toMissionContextPatch(payload: MissionContextUpdatedEvent): MissionContextPatch {
  const { sessionId: _sessionId, delta: _delta, ...patch } = payload;
  return patch;
}

export function subscribeToMissionContextUpdates(
  on: OnFn,
  sessionId: string,
  handler: (patch: MissionContextPatch) => void,
): () => void {
  return on('mission.context.updated', (payload) => {
    if (!isMissionContextUpdate(payload)) {
      return;
    }

    const payloadSessionId = getScopedSessionId(payload);
    if (payloadSessionId && payloadSessionId !== sessionId) {
      return;
    }

    handler(toMissionContextPatch(payload));
  });
}
