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
registerEventSchema({
    type: 'mission.context.updated',
    version: '1.0',
    validate(p) {
        if (typeof p !== 'object' || p === null)
            return false;
        const o = p;
        return (typeof o.goal === 'string'
            && typeof o.stage === 'object'
            && o.stage !== null
            && typeof o.budget === 'object'
            && o.budget !== null);
    },
});
const cardSchema = {
    type: 'card.created',
    version: '1.0',
    validate(p) {
        return (typeof p === 'object'
            && p !== null
            && typeof p.id === 'string');
    },
};
registerEventSchema(cardSchema);
registerEventSchema({ ...cardSchema, type: 'card.updated' });
registerEventSchema({ ...cardSchema, type: 'card.pinned' });
const planSchema = {
    type: 'plan.created',
    version: '1.0',
    validate(p) {
        return typeof p === 'object' && p !== null;
    },
};
registerEventSchema(planSchema);
registerEventSchema({ ...planSchema, type: 'plan.updated' });
registerEventSchema({ ...planSchema, type: 'plan.replanned' });
registerEventSchema({
    type: 'reasoning.emitted',
    version: '1.0',
    validate(p) {
        return typeof p === 'object' && p !== null;
    },
});
