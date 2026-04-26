"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.EVENT_SCHEMA_REGISTRY = void 0;
exports.registerEventSchema = registerEventSchema;
exports.getEventSchema = getEventSchema;
exports.knownEventTypes = knownEventTypes;
exports.validateEventPayload = validateEventPayload;
exports.EVENT_SCHEMA_REGISTRY = new Map();
function registerEventSchema(schema) {
    exports.EVENT_SCHEMA_REGISTRY.set(schema.type, schema);
}
function getEventSchema(type) {
    return exports.EVENT_SCHEMA_REGISTRY.get(type);
}
function knownEventTypes() {
    return Array.from(exports.EVENT_SCHEMA_REGISTRY.keys()).sort();
}
function validateEventPayload(type, payload) {
    const schema = exports.EVENT_SCHEMA_REGISTRY.get(type);
    if (!schema) {
        return { ok: false, reason: 'unknown-type', type };
    }
    if (!schema.validate(payload)) {
        return { ok: false, reason: 'invalid-shape', type };
    }
    return { ok: true, payload: payload };
}
// ---------------------------------------------------------------------------
// Pre-seeded schemas for known DS Agent event types (Phase 1+ surface).
//
// New events MUST be registered here OR via registerEventSchema() at module
// init. Unknown events flow through with `unknown-type` and the renderer
// logs+skips per ADR-0004.
// ---------------------------------------------------------------------------
function isRecord(value) {
    return typeof value === 'object' && value !== null;
}
function isNonEmptyString(value) {
    return typeof value === 'string' && value.trim().length > 0;
}
function isFiniteNumber(value) {
    return typeof value === 'number' && Number.isFinite(value);
}
function isStringArray(value) {
    return Array.isArray(value) && value.every((entry) => isNonEmptyString(entry));
}
const PLAN_NODE_STATUSES = new Set(['pending', 'running', 'completed', 'failed', 'skipped']);
function isPlanNodeStatus(value) {
    return isNonEmptyString(value) && PLAN_NODE_STATUSES.has(value);
}
function resolveCompatCardId(payload) {
    if (isNonEmptyString(payload.cardId)) {
        return payload.cardId;
    }
    if (isNonEmptyString(payload.id)) {
        return payload.id;
    }
    return null;
}
function resolveCompatResultId(payload, cardId) {
    return isNonEmptyString(payload.resultId) ? payload.resultId : cardId;
}
function isResultCardPayload(payload, messageIdFallback) {
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
    if (createdAt !== undefined
        && typeof createdAt !== 'number'
        && !isNonEmptyString(createdAt)) {
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
registerEventSchema({
    type: 'mission.context.updated',
    version: '1.0',
    validate(p) {
        if (typeof p !== 'object' || p === null)
            return false;
        const candidate = p;
        if (candidate.delta !== undefined) {
            if (typeof candidate.delta !== 'object' || candidate.delta === null) {
                return false;
            }
        }
        return true;
    },
});
registerEventSchema({
    type: 'stream.done',
    version: '1.0',
    validate(p) {
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
registerEventSchema({
    type: 'stream.error',
    version: '1.0',
    validate(p) {
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
const cardSchema = {
    type: 'card.created',
    version: '1.0',
    validate(p) {
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
function isPlanNode(value) {
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
function isPlanNodePatch(value) {
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
function isReplanDiff(value) {
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
registerEventSchema({
    type: 'plan.created',
    version: '1.0',
    validate(p) {
        return isRecord(p) && isPlanNode(p.planTree);
    },
});
registerEventSchema({
    type: 'plan.updated',
    version: '1.0',
    validate(p) {
        return isRecord(p) && isNonEmptyString(p.nodeId) && isPlanNodePatch(p.updates);
    },
});
registerEventSchema({
    type: 'plan.replanned',
    version: '1.0',
    validate(p) {
        return isRecord(p) && isReplanDiff(p.diff);
    },
});
registerEventSchema({
    type: 'reasoning.emitted',
    version: '1.0',
    validate(p) {
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
        const textFields = ['thinking', 'hypothesis', 'action', 'observation', 'decision'];
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
