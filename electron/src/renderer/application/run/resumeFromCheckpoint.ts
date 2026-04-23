import type {
  ResumeFromCheckpointInput,
  ResumeFromCheckpointPort,
  ResumeFromCheckpointResult,
} from './resumeFromCheckpointPort';

export async function resumeFromCheckpoint(
  port: ResumeFromCheckpointPort,
  input: ResumeFromCheckpointInput,
): Promise<ResumeFromCheckpointResult> {
  if (!input.sessionId.trim()) {
    throw new Error('sessionId is required');
  }
  if (!input.message.trim()) {
    throw new Error('message is required');
  }
  return port(input);
}
