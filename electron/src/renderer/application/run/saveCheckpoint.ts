import type {
  SaveCheckpointInput,
  SaveCheckpointPort,
  SaveCheckpointResult,
} from './saveCheckpointPort';

export async function saveCheckpoint(
  port: SaveCheckpointPort,
  input: SaveCheckpointInput,
): Promise<SaveCheckpointResult> {
  if (!input.sessionId.trim()) {
    throw new Error('sessionId is required');
  }
  if (!input.name.trim()) {
    throw new Error('name is required');
  }
  return port(input);
}
