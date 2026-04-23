export interface ResumeFromCheckpointInput {
  readonly sessionId: string;
  readonly message: string;
  readonly model?: string | null;
}

export interface ResumeFromCheckpointResult {
  readonly resumed: boolean;
  readonly runId: string | null;
  readonly sessionId: string;
}

export interface ResumeFromCheckpointPort {
  (input: ResumeFromCheckpointInput): Promise<ResumeFromCheckpointResult>;
}
