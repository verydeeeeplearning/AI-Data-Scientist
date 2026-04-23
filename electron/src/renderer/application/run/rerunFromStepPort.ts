export interface RerunFromStepInput {
  readonly parentRunId: string;
  readonly planNodeId: string;
  readonly message?: string | null;
  readonly model?: string | null;
}

export interface RerunFromStepResult {
  readonly runId: string;
  readonly sessionId: string;
  readonly branchedFromRunId: string | null;
  readonly rerunFromNodeId: string | null;
}

export interface RerunFromStepPort {
  (input: RerunFromStepInput): Promise<RerunFromStepResult>;
}
