import type {
  ListLineageInput,
  ListLineagePort,
  ListLineageResult,
} from './listLineagePort';

export async function listLineage(
  port: ListLineagePort,
  input: ListLineageInput,
): Promise<ListLineageResult> {
  const rootRunId = input.rootRunId.trim();
  if (!rootRunId) {
    throw new Error('rootRunId is required');
  }
  return port({ rootRunId });
}
