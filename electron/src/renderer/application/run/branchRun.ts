import type {
  BranchRunInput,
  BranchRunPort,
  BranchRunResult,
} from './branchRunPort';

export async function branchRun(
  port: BranchRunPort,
  input: BranchRunInput,
): Promise<BranchRunResult> {
  if (!input.parentRunId.trim()) {
    throw new Error('parentRunId is required');
  }
  if (!input.message.trim()) {
    throw new Error('message is required');
  }
  return port(input);
}
