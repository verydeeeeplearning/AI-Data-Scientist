import type {
  PromoteToArtifactInput,
  PromoteToArtifactPort,
  PromoteToArtifactResult,
} from './promoteToArtifactPort';
import { PROMOTE_AUDIENCES } from './promoteToArtifactPort';

export async function promoteToArtifact(
  port: PromoteToArtifactPort,
  input: PromoteToArtifactInput,
): Promise<PromoteToArtifactResult> {
  if (!input.runId.trim()) {
    throw new Error('runId is required');
  }
  if (!input.cardId.trim()) {
    throw new Error('cardId is required');
  }
  if (!PROMOTE_AUDIENCES.includes(input.audience)) {
    throw new Error(
      `audience must be one of: ${PROMOTE_AUDIENCES.join(', ')}`,
    );
  }
  return port(input);
}
