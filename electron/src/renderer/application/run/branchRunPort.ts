export interface BranchRunInput {
  readonly parentRunId: string;
  readonly message: string;
  readonly model?: string | null;
  readonly checkpointId?: string | null;
}

export interface BranchRunResult {
  readonly runId: string;
  readonly sessionId: string;
  readonly branchedFromRunId: string | null;
}

export interface BranchRunPort {
  (input: BranchRunInput): Promise<BranchRunResult>;
}
