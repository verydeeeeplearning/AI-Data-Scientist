import type { MissionContext } from '../../domain/mission';

export interface GetMissionContextPort {
  (sessionId: string): Promise<MissionContext>;
}
