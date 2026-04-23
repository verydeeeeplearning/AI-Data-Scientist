import {
  getMissionBudgetState,
  getMissionConnectionStateFromWs,
  mergeMissionContext,
  type MissionContext,
  type MissionContextPatch,
} from '../../domain/mission';

export type MissionDetailKey =
  | 'goal'
  | 'dataSources'
  | 'deliverables'
  | 'constraints'
  | 'stage'
  | 'mode'
  | 'model'
  | 'budget'
  | 'connection';

export type MissionBudgetState = 'default' | 'warning' | 'error';
export type MissionWsStatus = 'connecting' | 'connected' | 'disconnected';

export const COLLAPSED_SLOT_KEYS: ReadonlyArray<MissionDetailKey> = [
  'goal',
  'stage',
  'budget',
];

export const ALL_SLOT_KEYS: ReadonlyArray<MissionDetailKey> = [
  'goal',
  'dataSources',
  'deliverables',
  'constraints',
  'stage',
  'mode',
  'model',
  'budget',
  'connection',
];

export function listVisibleSlotKeys(
  collapsed: boolean,
): ReadonlyArray<MissionDetailKey> {
  return collapsed ? COLLAPSED_SLOT_KEYS : ALL_SLOT_KEYS;
}

export function applyMissionPatch(
  current: MissionContext | null,
  patch: MissionContextPatch,
): MissionContext | null {
  if (!current) {
    return current;
  }
  return mergeMissionContext(current, patch);
}

export function projectConnection(
  mission: MissionContext,
  status: MissionWsStatus,
): MissionContext {
  return {
    ...mission,
    connection: {
      ...mission.connection,
      state: getMissionConnectionStateFromWs(status),
    },
  };
}

export interface BudgetWarningTransition {
  readonly previous: MissionBudgetState;
  readonly next: MissionBudgetState;
  readonly streaming: boolean;
}

export function shouldShowBudgetWarning(
  transition: BudgetWarningTransition,
): boolean {
  if (!transition.streaming) {
    return false;
  }
  if (transition.next === 'warning' && transition.previous === 'default') {
    return true;
  }
  if (transition.next === 'error' && transition.previous !== 'error') {
    return true;
  }
  return false;
}

export function deriveMissionBudgetState(mission: MissionContext): MissionBudgetState {
  return getMissionBudgetState(mission.budget);
}

export interface MissionSnoozeState {
  readonly until: number | null;
}

export const MISSION_BUDGET_SNOOZE_KEY = 'ds-agent-budget-snooze-until';

const SNOOZE_DURATIONS_MS: Record<'5m' | '30m' | '1h', number> = {
  '5m': 5 * 60 * 1000,
  '30m': 30 * 60 * 1000,
  '1h': 60 * 60 * 1000,
};

export type MissionSnoozeOption = keyof typeof SNOOZE_DURATIONS_MS;

export function snoozeUntil(now: number, option: MissionSnoozeOption): number {
  return now + SNOOZE_DURATIONS_MS[option];
}

export function isSnoozeActive(state: MissionSnoozeState, now: number): boolean {
  if (state.until === null) {
    return false;
  }
  return state.until > now;
}

export function parseSnoozeStorage(value: string | null): MissionSnoozeState {
  if (value === null) {
    return { until: null };
  }
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return { until: null };
  }
  return { until: parsed };
}

export function serializeSnoozeStorage(state: MissionSnoozeState): string | null {
  if (state.until === null || state.until <= 0) {
    return null;
  }
  return String(state.until);
}

export function nextBudgetWarningVisibility(input: {
  readonly previous: MissionBudgetState;
  readonly next: MissionBudgetState;
  readonly streaming: boolean;
  readonly snoozedUntil: number | null;
  readonly now: number;
}): boolean {
  if (
    input.snoozedUntil !== null
    && input.snoozedUntil > input.now
  ) {
    return false;
  }
  return shouldShowBudgetWarning({
    previous: input.previous,
    next: input.next,
    streaming: input.streaming,
  });
}
