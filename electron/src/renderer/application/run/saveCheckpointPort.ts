export interface SaveCheckpointInput {
  readonly sessionId: string;
  readonly name: string;
  readonly description?: string | null;
}

export interface SaveCheckpointResult {
  readonly checkpointId: string;
  readonly sessionId: string;
  readonly name: string;
  readonly transcriptStep: number;
  readonly createdAt: number;
  readonly description: string | null;
}

export interface SaveCheckpointPort {
  (input: SaveCheckpointInput): Promise<SaveCheckpointResult>;
}
