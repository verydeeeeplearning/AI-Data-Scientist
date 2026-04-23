export interface RunLineageNode {
  readonly runId: string;
  readonly sessionId: string;
  readonly status: string;
  readonly message: string;
  readonly createdAt: number;
  readonly startedAt: number;
  readonly finishedAt?: number | null;
  readonly branchedFromRunId?: string | null;
  readonly rerunFromNodeId?: string | null;
  readonly depth: number;
  readonly isRoot: boolean;
  readonly isSeed: boolean;
}

export interface ListLineageInput {
  readonly rootRunId: string;
}

export interface ListLineageResult {
  readonly rootRunId: string;
  readonly seedRunId: string;
  readonly nodes: readonly RunLineageNode[];
}

export interface ListLineagePort {
  (input: ListLineageInput): Promise<ListLineageResult>;
}
