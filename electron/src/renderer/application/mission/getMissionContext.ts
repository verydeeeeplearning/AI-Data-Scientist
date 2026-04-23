import type { MissionContext } from '../../domain/mission';
import type { GetMissionContextPort } from './getMissionContextPort';

export async function getMissionContext(
  port: GetMissionContextPort,
  sessionId: string,
): Promise<MissionContext> {
  return port(sessionId);
}
