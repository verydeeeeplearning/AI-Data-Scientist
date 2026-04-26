import type {
  CardLifecycleEvent,
  PlanCreatedEvent,
  PlanNode,
  PlanNodePatch,
  PlanReplannedEvent,
  PlanUpdatedEvent,
  ReasoningEmittedEvent,
  ReplanDiff,
  StreamDoneEvent,
} from '../../types/events';

export interface EventSchema<T = unknown> {
  type: string;
  version: string;
  validate(payload: unknown): payload is T;
}

export type ValidationResult<T> =
  | { ok: true; payload: T }
  | { ok: false; reason: 'unknown-type' | 'invalid-shape'; type: string };

export const EVENT_SCHEMA_REGISTRY = new Map<string, EventSchema>();

export function registerEventSchema<T>(schema: EventSchema<T>): void {
  EVENT_SCHEMA_REGISTRY.set(schema.type, schema as EventSchema);
}

export function getEventSchema(type: string): EventSchema | undefined {
  return EVENT_SCHEMA_REGISTRY.get(type);
}

export function knownEventTypes(): string[] {
  return Array.from(EVENT_SCHEMA_REGISTRY.keys()).sort();
}

export function validateEventPayload<T = unknown>(
  type: string,
  payload: unknown,
): ValidationResult<T> {
  const schema = EVENT_SCHEMA_REGISTRY.get(type) as EventSchema<T> | undefined;
  if (!schema) {
    return { ok: false, reason: 'unknown-type', type };
  }
  if (!schema.validate(payload)) {
    return { ok: false, reason: 'invalid-shape', type };
  }
  return { ok: true, payload: payload as T };
}

// ---------------------------------------------------------------------------
// Pre-seeded schemas for known DS Agent event types (Phase 1+ surface).
//
// New events MUST be registered here OR via registerEventSchema() at module
// init. Unknown events flow through with `unknown-type` and the renderer
// logs+skips per ADR-0004.
// ---------------------------------------------------------------------------

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => isNonEmptyString(entry));
}

const PLAN_NODE_STATUSES = new Set(['pending', 'running', 'completed', 'failed', 'skipped']);

function isPlanNodeStatus(value: unknown): value is PlanNode['status'] {
  return isNonEmptyString(value) && PLAN_NODE_STATUSES.has(value);
}

function resolveCompatCardId(payload: Record<string, unknown>): string | null {
  if (isNonEmptyString(payload.cardId)) {
    return payload.cardId;
  }
  if (isNonEmptyString(payload.id)) {
    return payload.id;
  }
  return null;
}

function resolveCompatResultId(payload: Record<string, unknown>, cardId: string): string {
  return isNonEmptyString(payload.resultId) ? payload.resultId : cardId;
}

function isResultCardPayload(
  payload: unknown,
  messageIdFallback?: string | null,
): payload is Record<string, unknown> {
  if (!isRecord(payload)) {
    return false;
  }

  const cardId = resolveCompatCardId(payload);
  if (cardId === null) {
    return false;
  }

  const source = payload.source;
  if (!isRecord(source) || !isNonEmptyString(source.runId)) {
    return false;
  }

  const messageId = isNonEmptyString(source.messageId)
    ? source.messageId
    : (isNonEmptyString(messageIdFallback) ? messageIdFallback : null);
  if (!messageId) {
    return false;
  }

  if (!isNonEmptyString(payload.type)) {
    return false;
  }

  const createdAt = payload.createdAt;
  if (
    createdAt !== undefined
    && typeof createdAt !== 'number'
    && !isNonEmptyString(createdAt)
  ) {
    return false;
  }

  if (payload.pinned !== undefined && typeof payload.pinned !== 'boolean') {
    return false;
  }

  if (payload.archived !== undefined && typeof payload.archived !== 'boolean') {
    return false;
  }

  resolveCompatResultId(payload, cardId);
  return true;
}

interface MissionContextUpdatedPayload {
  goal?: unknown;
  dataSources?: unknown;
  deliverables?: unknown;
  constraints?: unknown;
  stage?: unknown;
  mode?: unknown;
  model?: unknown;
  budget?: unknown;
  connection?: unknown;
  delta?: {
    dataSources?: unknown;
    deliverables?: unknown;
    constraints?: unknown;
  };
}

interface StreamErrorEvent {
  message?: string;
  code?: string;
  messageId?: string | null;
}

registerEventSchema<MissionContextUpdatedPayload>({
  type: 'mission.context.updated',
  version: '1.0',
  validate(p): p is MissionContextUpdatedPayload {
    if (typeof p !== 'object' || p === null) return false;
    const candidate = p as { delta?: unknown };
    if (candidate.delta !== undefined) {
      if (typeof candidate.delta !== 'object' || candidate.delta === null) {
        return false;
      }
    }
    return true;
  },
});

registerEventSchema<StreamDoneEvent>({
  type: 'stream.done',
  version: '1.0',
  validate(p): p is StreamDoneEvent {
    if (!isRecord(p) || typeof p.content !== 'string') {
      return false;
    }

    if (p.cost !== undefined && (typeof p.cost !== 'number' || !Number.isFinite(p.cost))) {
      return false;
    }

    if (p.messageId !== undefined && p.messageId !== null && !isNonEmptyString(p.messageId)) {
      return false;
    }

    if (p.cards !== undefined) {
      if (!Array.isArray(p.cards)) {
        return false;
      }
      for (const card of p.cards) {
        if (!isResultCardPayload(card, p.messageId ?? null)) {
          return false;
        }
      }
    }

    return true;
  },
});

registerEventSchema<StreamErrorEvent>({
  type: 'stream.error',
  version: '1.0',
  validate(p): p is StreamErrorEvent {
    if (!isRecord(p)) {
      return false;
    }
    if (p.message !== undefined && typeof p.message !== 'string') {
      return false;
    }
    if (p.code !== undefined && typeof p.code !== 'string') {
      return false;
    }
    return p.messageId === undefined || p.messageId === null || isNonEmptyString(p.messageId);
  },
});

interface CardEventPayload extends CardLifecycleEvent {
  cardId: string;
  resultId: string;
}

const cardSchema: EventSchema<CardEventPayload> = {
  type: 'card.created',
  version: '1.0',
  validate(p): p is CardEventPayload {
    if (!isRecord(p)) {
      return false;
    }

    const cardId = resolveCompatCardId(p);
    if (cardId === null) {
      return false;
    }

    const resultId = resolveCompatResultId(p, cardId);
    if (!isNonEmptyString(resultId)) {
      return false;
    }

    return p.messageId === undefined || p.messageId === null || isNonEmptyString(p.messageId);
  },
};
registerEventSchema(cardSchema);
registerEventSchema({ ...cardSchema, type: 'card.updated' });
registerEventSchema({ ...cardSchema, type: 'card.pinned' });

function isPlanNode(value: unknown): value is PlanNode {
  if (!isRecord(value)) {
    return false;
  }
  if (!isNonEmptyString(value.id) || !isNonEmptyString(value.label) || !isPlanNodeStatus(value.status)) {
    return false;
  }
  if (value.parentId !== undefined && value.parentId !== null && !isNonEmptyString(value.parentId)) {
    return false;
  }
  if (value.description !== undefined && !isNonEmptyString(value.description)) {
    return false;
  }
  if (value.estimatedDurationSec !== undefined && !isFiniteNumber(value.estimatedDurationSec)) {
    return false;
  }
  if (value.startedAt !== undefined && !isFiniteNumber(value.startedAt)) {
    return false;
  }
  if (value.completedAt !== undefined && !isFiniteNumber(value.completedAt)) {
    return false;
  }
  if (!isStringArray(value.reasoningRefs) || !isStringArray(value.toolEventRefs)) {
    return false;
  }
  return Array.isArray(value.children) && value.children.every((child) => isPlanNode(child));
}

function isPlanNodePatch(value: unknown): value is PlanNodePatch {
  if (!isRecord(value)) {
    return false;
  }
  if (value.parentId !== undefined && value.parentId !== null && !isNonEmptyString(value.parentId)) {
    return false;
  }
  if (value.label !== undefined && !isNonEmptyString(value.label)) {
    return false;
  }
  if (value.description !== undefined && !isNonEmptyString(value.description)) {
    return false;
  }
  if (value.status !== undefined && !isPlanNodeStatus(value.status)) {
    return false;
  }
  if (value.estimatedDurationSec !== undefined && !isFiniteNumber(value.estimatedDurationSec)) {
    return false;
  }
  if (value.startedAt !== undefined && !isFiniteNumber(value.startedAt)) {
    return false;
  }
  if (value.completedAt !== undefined && !isFiniteNumber(value.completedAt)) {
    return false;
  }
  if (value.reasoningRefs !== undefined && !isStringArray(value.reasoningRefs)) {
    return false;
  }
  if (value.toolEventRefs !== undefined && !isStringArray(value.toolEventRefs)) {
    return false;
  }
  if (value.children !== undefined) {
    if (!Array.isArray(value.children)) {
      return false;
    }
    for (const child of value.children) {
      if (!isPlanNode(child)) {
        return false;
      }
    }
  }
  return true;
}

function isReplanDiff(value: unknown): value is ReplanDiff {
  if (!isRecord(value)) {
    return false;
  }
  if (!Array.isArray(value.oldNodes) || !value.oldNodes.every((node) => isPlanNode(node))) {
    return false;
  }
  if (!Array.isArray(value.newNodes) || !value.newNodes.every((node) => isPlanNode(node))) {
    return false;
  }
  if (!isStringArray(value.added) || !isStringArray(value.removed) || !isStringArray(value.modified)) {
    return false;
  }
  return isNonEmptyString(value.reason);
}

registerEventSchema<PlanCreatedEvent>({
  type: 'plan.created',
  version: '1.0',
  validate(p): p is PlanCreatedEvent {
    return isRecord(p) && isPlanNode(p.planTree);
  },
});

registerEventSchema<PlanUpdatedEvent>({
  type: 'plan.updated',
  version: '1.0',
  validate(p): p is PlanUpdatedEvent {
    return isRecord(p) && isNonEmptyString(p.nodeId) && isPlanNodePatch(p.updates);
  },
});

registerEventSchema<PlanReplannedEvent>({
  type: 'plan.replanned',
  version: '1.0',
  validate(p): p is PlanReplannedEvent {
    return isRecord(p) && isReplanDiff(p.diff);
  },
});

registerEventSchema<ReasoningEmittedEvent>({
  type: 'reasoning.emitted',
  version: '1.0',
  validate(p): p is ReasoningEmittedEvent {
    if (!isRecord(p)) {
      return false;
    }
    if (!isFiniteNumber(p.emittedAt)) {
      return false;
    }
    if (p.id !== undefined && !isNonEmptyString(p.id)) {
      return false;
    }
    if (p.planNodeId !== undefined && !isNonEmptyString(p.planNodeId)) {
      return false;
    }

    const textFields = ['thinking', 'hypothesis', 'action', 'observation', 'decision'] as const;
    let hasReasoningText = false;
    for (const field of textFields) {
      const value = p[field];
      if (value === undefined) {
        continue;
      }
      if (!isNonEmptyString(value)) {
        return false;
      }
      hasReasoningText = true;
    }

    return hasReasoningText;
  },
});
