import type {
  RerunFromStepInput,
  RerunFromStepPort,
  RerunFromStepResult,
} from './rerunFromStepPort';

export async function rerunFromStep(
  port: RerunFromStepPort,
  input: RerunFromStepInput,
): Promise<RerunFromStepResult> {
  if (!input.parentRunId.trim()) {
    throw new Error('parentRunId is required');
  }
  if (!input.planNodeId.trim()) {
    throw new Error('planNodeId is required');
  }
  return port(input);
}
