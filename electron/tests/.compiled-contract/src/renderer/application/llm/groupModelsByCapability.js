"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.groupModelsByCapability = groupModelsByCapability;
const modelCapability_1 = require("../../domain/llm/modelCapability");
function compareModels(left, right) {
    if (left.legacy !== right.legacy) {
        return left.legacy ? 1 : -1;
    }
    if (left.maxContext !== right.maxContext) {
        return right.maxContext - left.maxContext;
    }
    return left.displayName.localeCompare(right.displayName);
}
function groupModelsByCapability(models, showLegacy) {
    const grouped = new Map(modelCapability_1.CAPABILITY_GROUP_DEFINITIONS.map((definition) => [definition.id, []]));
    for (const model of models) {
        if (!showLegacy && model.legacy) {
            continue;
        }
        grouped.get(model.capabilityGroup)?.push(model);
    }
    return modelCapability_1.CAPABILITY_GROUP_DEFINITIONS.map((definition) => ({
        ...definition,
        models: [...(grouped.get(definition.id) ?? [])].sort(compareModels),
    }));
}
