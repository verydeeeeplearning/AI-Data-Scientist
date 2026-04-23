import {
  createExecutionToolEvent,
  createStage,
  getStageMetadata,
  STAGE_ORDER,
  type ExecutionToolEvent,
  type Stage,
  type StageKey,
  type StageStatus,
} from '../../domain/execution/stage';
import { inferToolCategory, isAgentControlTool, mapToolToStage } from '../../domain/execution/stageMapper';
import { inferOutcome } from './inferOutcome';

export interface ToolActivityLike {
  readonly name: string;
  readonly status: 'running' | 'done' | 'error';
  readonly args?: Readonly<Record<string, unknown>>;
  readonly result?: string;
  readonly elapsed?: number;
  readonly startedAt: number;
}

function toExecutionToolEvent(activity: ToolActivityLike): ExecutionToolEvent {
  return createExecutionToolEvent({
    toolName: activity.name,
    category: inferToolCategory(activity.name),
    status:
      activity.status === 'done'
        ? 'completed'
        : activity.status === 'error'
          ? 'failed'
          : 'running',
    args: activity.args,
    outputPreview: activity.result,
    elapsedMs: activity.elapsed,
    startedAt: activity.startedAt,
    completedAt:
      activity.status === 'running'
        ? undefined
        : activity.elapsed !== undefined
          ? activity.startedAt + activity.elapsed
          : activity.startedAt,
  });
}

function deriveStageStatus(events: readonly ExecutionToolEvent[]): StageStatus {
  if (events.length === 0) {
    return 'pending';
  }
  if (events.some((event) => event.status === 'failed')) {
    return 'failed';
  }
  if (events.some((event) => event.status === 'running')) {
    return 'running';
  }
  if (events.every((event) => event.status === 'completed')) {
    return 'completed';
  }
  return 'pending';
}

function minTimestamp(values: readonly (number | undefined)[]): number | undefined {
  const filtered = values.filter((value): value is number => typeof value === 'number');
  if (filtered.length === 0) {
    return undefined;
  }
  return Math.min(...filtered);
}

function maxTimestamp(values: readonly (number | undefined)[]): number | undefined {
  const filtered = values.filter((value): value is number => typeof value === 'number');
  if (filtered.length === 0) {
    return undefined;
  }
  return Math.max(...filtered);
}

export function aggregateStages(activities: readonly ToolActivityLike[]): Stage[] {
  const grouped = new Map<StageKey, ExecutionToolEvent[]>();

  for (const activity of activities) {
    if (isAgentControlTool(activity.name)) {
      continue;
    }
    const toolEvent = toExecutionToolEvent(activity);
    const stageKey = mapToolToStage(toolEvent.toolName) ?? 'eda';
    if (!grouped.has(stageKey)) {
      grouped.set(stageKey, []);
    }
    grouped.get(stageKey)?.push(toolEvent);
  }

  return STAGE_ORDER
    .filter((stageKey) => grouped.has(stageKey))
    .map((stageKey) => {
      const toolEvents = grouped.get(stageKey) ?? [];
      const metadata = getStageMetadata(stageKey);
      const status = deriveStageStatus(toolEvents);

      return createStage({
        key: stageKey,
        label: metadata.label,
        labelKey: metadata.labelKey,
        status,
        toolEvents,
        startedAt: minTimestamp(toolEvents.map((event) => event.startedAt)),
        completedAt:
          status === 'completed' || status === 'failed'
            ? maxTimestamp(toolEvents.map((event) => event.completedAt))
            : undefined,
        outcome: inferOutcome({ key: stageKey, toolEvents }),
      });
    });
}
