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

interface MissionContextUpdatedPayload {
  goal: string;
  stage: { current: number; total: number; label: string };
  budget: { limit: number; spent: number; currency: string };
}

registerEventSchema<MissionContextUpdatedPayload>({
  type: 'mission.context.updated',
  version: '1.0',
  validate(p): p is MissionContextUpdatedPayload {
    if (typeof p !== 'object' || p === null) return false;
    const o = p as Record<string, unknown>;
    return (
      typeof o.goal === 'string'
      && typeof o.stage === 'object'
      && o.stage !== null
      && typeof o.budget === 'object'
      && o.budget !== null
    );
  },
});

interface CardEventPayload {
  id: string;
}

const cardSchema: EventSchema<CardEventPayload> = {
  type: 'card.created',
  version: '1.0',
  validate(p): p is CardEventPayload {
    return (
      typeof p === 'object'
      && p !== null
      && typeof (p as Record<string, unknown>).id === 'string'
    );
  },
};
registerEventSchema(cardSchema);
registerEventSchema({ ...cardSchema, type: 'card.updated' });
registerEventSchema({ ...cardSchema, type: 'card.pinned' });

interface PlanEventPayload {
  id?: string;
  nodes?: unknown[];
}

const planSchema: EventSchema<PlanEventPayload> = {
  type: 'plan.created',
  version: '1.0',
  validate(p): p is PlanEventPayload {
    return typeof p === 'object' && p !== null;
  },
};
registerEventSchema(planSchema);
registerEventSchema({ ...planSchema, type: 'plan.updated' });
registerEventSchema({ ...planSchema, type: 'plan.replanned' });

interface ReasoningEmittedPayload {
  hypothesis?: string;
  action?: string;
  observation?: string;
  decision?: string;
}

registerEventSchema<ReasoningEmittedPayload>({
  type: 'reasoning.emitted',
  version: '1.0',
  validate(p): p is ReasoningEmittedPayload {
    return typeof p === 'object' && p !== null;
  },
});
