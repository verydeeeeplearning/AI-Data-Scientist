import { useCallback, useEffect, useState } from 'react';
import { getMissionContext } from '../application/mission/getMissionContext';
import {
  getMissionConnectionStateFromWs,
  mergeMissionContext,
  type MissionContext,
} from '../domain/mission';
import { fetchCurrentMissionContext } from '../infrastructure/api/missionApi';
import { subscribeToMissionContextUpdates } from '../infrastructure/ws/wsMissionSubscriber';
import { useWs } from './WsProvider';

export function useMissionContext(sessionId: string | null) {
  const { status, on } = useWs();
  const [mission, setMission] = useState<MissionContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!sessionId) {
      setMission(null);
      setError(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const nextMission = await getMissionContext(fetchCurrentMissionContext, sessionId);
      setMission({
        ...nextMission,
        connection: {
          ...nextMission.connection,
          state: getMissionConnectionStateFromWs(status),
        },
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [sessionId, status]);

  useEffect(() => {
    if (!sessionId) {
      setMission(null);
      setError(null);
      setLoading(false);
      return;
    }
    if (status === 'connected') {
      void refresh();
    }
  }, [refresh, sessionId, status]);

  useEffect(() => {
    if (!sessionId) {
      return () => undefined;
    }

    return subscribeToMissionContextUpdates(on, sessionId, (patch) => {
      setMission((current) => {
        if (!current) {
          void fetchCurrentMissionContext(sessionId)
            .then((nextMission) => {
              setMission({
                ...nextMission,
                connection: {
                  ...nextMission.connection,
                  state: getMissionConnectionStateFromWs(status),
                },
              });
            })
            .catch((err) => {
              console.warn('[useMissionContext] refresh after patch failed:', err);
            });
          return current;
        }
        return mergeMissionContext(current, patch);
      });
    });
  }, [on, sessionId, status]);

  useEffect(() => {
    setMission((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        connection: {
          ...current.connection,
          state: getMissionConnectionStateFromWs(status),
        },
      };
    });
  }, [status]);

  return { mission, loading, error, refresh };
}
