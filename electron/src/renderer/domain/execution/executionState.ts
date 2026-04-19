export type ExecutionMode = 'auto' | 'supervised' | 'step-by-step';
export type QualityPreset = 'best_quality' | 'balanced' | 'fast' | 'local' | 'custom';

export interface ExecutionState {
  readonly model: string;
  readonly qualityPreset: QualityPreset;
  readonly mode: ExecutionMode;
  readonly cost: number;
  readonly step: number;
  readonly activeSessions: number;
  readonly connected: boolean;
}

const DEFAULT_MODEL = 'anthropic/claude-sonnet-4-6';

export function createExecutionState(overrides: Partial<ExecutionState> = {}): ExecutionState {
  return Object.freeze({
    model: DEFAULT_MODEL,
    qualityPreset: 'balanced',
    mode: 'auto',
    cost: 0,
    step: 0,
    activeSessions: 0,
    connected: false,
    ...overrides,
  });
}

export function normalizeQualityPreset(value: unknown): QualityPreset {
  if (
    value === 'best_quality'
    || value === 'balanced'
    || value === 'fast'
    || value === 'local'
    || value === 'custom'
  ) {
    return value;
  }
  return 'custom';
}

function normalizeMode(value: unknown, current: ExecutionMode): ExecutionMode {
  if (value === 'auto' || value === 'supervised' || value === 'step-by-step') {
    return value;
  }
  return current;
}

export function reduceSetModel(state: ExecutionState, model: string): ExecutionState {
  return createExecutionState({ ...state, model });
}

export function reduceSetQualityPreset(
  state: ExecutionState,
  qualityPreset: QualityPreset,
): ExecutionState {
  return createExecutionState({ ...state, qualityPreset });
}

export function reduceSetMode(state: ExecutionState, mode: ExecutionMode): ExecutionState {
  return createExecutionState({ ...state, mode });
}

export function reduceSetCost(state: ExecutionState, cost: number): ExecutionState {
  return createExecutionState({ ...state, cost });
}

export function reduceSetStep(state: ExecutionState, step: number): ExecutionState {
  return createExecutionState({ ...state, step });
}

export function reduceSetActiveSessions(state: ExecutionState, n: number): ExecutionState {
  return createExecutionState({ ...state, activeSessions: n });
}

export function reduceSetConnected(state: ExecutionState, connected: boolean): ExecutionState {
  return createExecutionState({ ...state, connected });
}

export function reduceUpdateFromStatus(
  state: ExecutionState,
  data: Record<string, unknown>,
): ExecutionState {
  const model = typeof data.model === 'string' ? data.model : state.model;
  const qualityPreset =
    'qualityPreset' in data ? normalizeQualityPreset(data.qualityPreset) : state.qualityPreset;
  const mode = 'mode' in data ? normalizeMode(data.mode, state.mode) : state.mode;
  const activeSessions =
    typeof data.activeSessions === 'number' ? data.activeSessions : state.activeSessions;
  return createExecutionState({
    ...state,
    model,
    qualityPreset,
    mode,
    activeSessions,
  });
}
