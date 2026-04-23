export type MissionConnectionState = 'connected' | 'reconnecting' | 'disconnected';

export interface MissionGoal {
  readonly title: string;
  readonly successCriteria: readonly string[];
}

export interface MissionDataSource {
  readonly type: 'file' | 'database' | 'api';
  readonly label: string;
  readonly rowCount?: number;
}

export interface MissionConstraints {
  readonly language: string;
  readonly requiresApproval: boolean;
  readonly localOnlyModel: boolean;
}

export interface MissionStage {
  readonly current: number;
  readonly total: number;
  readonly label: string;
}

export interface MissionModel {
  readonly primary: string;
  readonly fallbacks: readonly string[];
  readonly capabilities: readonly string[];
}

export interface MissionBudget {
  readonly spentUsd: number;
  readonly limitUsd: number;
  readonly elapsedSec: number;
  readonly nearLimit: boolean;
}

export interface MissionConnection {
  readonly state: MissionConnectionState;
  readonly latencyMs?: number;
}

export interface MissionContext {
  readonly goal: MissionGoal;
  readonly dataSources: readonly MissionDataSource[];
  readonly deliverables: readonly string[];
  readonly constraints: MissionConstraints;
  readonly stage: MissionStage;
  readonly mode: string;
  readonly model: MissionModel;
  readonly budget: MissionBudget;
  readonly connection: MissionConnection;
}

export interface MissionContextPatch {
  readonly goal?: Partial<MissionGoal>;
  readonly dataSources?: readonly MissionDataSource[];
  readonly deliverables?: readonly string[];
  readonly constraints?: Partial<MissionConstraints>;
  readonly stage?: Partial<MissionStage>;
  readonly mode?: string;
  readonly model?: Partial<MissionModel>;
  readonly budget?: Partial<MissionBudget>;
  readonly connection?: Partial<MissionConnection>;
}

export function mergeMissionContext(
  current: MissionContext,
  patch: MissionContextPatch,
): MissionContext {
  return {
    goal: {
      ...current.goal,
      ...patch.goal,
      successCriteria: patch.goal?.successCriteria ?? current.goal.successCriteria,
    },
    dataSources: patch.dataSources ?? current.dataSources,
    deliverables: patch.deliverables ?? current.deliverables,
    constraints: {
      ...current.constraints,
      ...patch.constraints,
    },
    stage: {
      ...current.stage,
      ...patch.stage,
    },
    mode: patch.mode ?? current.mode,
    model: {
      ...current.model,
      ...patch.model,
      fallbacks: patch.model?.fallbacks ?? current.model.fallbacks,
      capabilities: patch.model?.capabilities ?? current.model.capabilities,
    },
    budget: {
      ...current.budget,
      ...patch.budget,
    },
    connection: {
      ...current.connection,
      ...patch.connection,
    },
  };
}

export function getMissionBudgetRatio(budget: MissionBudget): number {
  if (budget.limitUsd <= 0) {
    return 0;
  }
  return Math.max(0, Math.min(1, budget.spentUsd / budget.limitUsd));
}

export function getMissionBudgetState(
  budget: MissionBudget,
): 'default' | 'warning' | 'error' {
  const ratio = getMissionBudgetRatio(budget);
  if (ratio >= 1) {
    return 'error';
  }
  if (budget.nearLimit || ratio >= 0.8) {
    return 'warning';
  }
  return 'default';
}

export function getMissionConnectionStateFromWs(
  status: 'connecting' | 'connected' | 'disconnected',
): MissionConnectionState {
  if (status === 'connected') {
    return 'connected';
  }
  if (status === 'connecting') {
    return 'reconnecting';
  }
  return 'disconnected';
}

export function formatMissionMode(mode: string): string {
  switch (mode) {
    case 'auto':
      return 'Auto';
    case 'supervised':
      return 'Supervised';
    case 'step-by-step':
      return 'Step by Step';
    default:
      return mode
        .split(/[-_\\s]+/)
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
  }
}
