export type PauseAgentReason = 'budget_warning' | 'manual';

export interface PauseAgentInput {
  readonly sessionId: string;
  readonly reason: PauseAgentReason;
}

export interface PauseAgentResult {
  readonly paused: boolean;
  readonly previousStatus: 'running' | 'idle' | 'paused';
}

export interface PauseAgentPort {
  (input: PauseAgentInput): Promise<PauseAgentResult>;
}
