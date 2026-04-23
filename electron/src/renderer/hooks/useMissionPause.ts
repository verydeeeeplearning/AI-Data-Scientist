import { useMemo } from 'react';
import type { PauseAgentPort } from '../application/mission/pauseAgentPort';
import { requestAgentPause } from '../infrastructure/api/missionApi';

export function useMissionPause(): PauseAgentPort {
  return useMemo<PauseAgentPort>(() => (input) => requestAgentPause(input), []);
}
