"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CAPABILITY_GROUP_DEFINITIONS = exports.ALL_CAPABILITY_BADGES = void 0;
exports.isCapabilityGroup = isCapabilityGroup;
exports.isCapabilityBadge = isCapabilityBadge;
exports.getCapabilityGroupDefinition = getCapabilityGroupDefinition;
exports.ALL_CAPABILITY_BADGES = [
    'fast',
    'cheap',
    'strong_coding',
    'strong_korean',
    'offline',
    'long_context',
    'strong_reasoning',
    'multimodal',
];
function isCapabilityGroup(value) {
    return (value === 'fast_start'
        || value === 'best_quality'
        || value === 'cost_optimized'
        || value === 'privacy_first'
        || value === 'offline_capable');
}
function isCapabilityBadge(value) {
    return typeof value === 'string' && exports.ALL_CAPABILITY_BADGES.includes(value);
}
exports.CAPABILITY_GROUP_DEFINITIONS = [
    {
        id: 'fast_start',
        order: 0,
        titleKey: 'llm.group.fast_start.title',
        descriptionKey: 'llm.group.fast_start.description',
        emptyTitleKey: 'llm.group.fast_start.emptyTitle',
        emptyDescriptionKey: 'llm.group.fast_start.emptyDescription',
    },
    {
        id: 'best_quality',
        order: 1,
        titleKey: 'llm.group.best_quality.title',
        descriptionKey: 'llm.group.best_quality.description',
        emptyTitleKey: 'llm.group.best_quality.emptyTitle',
        emptyDescriptionKey: 'llm.group.best_quality.emptyDescription',
    },
    {
        id: 'cost_optimized',
        order: 2,
        titleKey: 'llm.group.cost_optimized.title',
        descriptionKey: 'llm.group.cost_optimized.description',
        emptyTitleKey: 'llm.group.cost_optimized.emptyTitle',
        emptyDescriptionKey: 'llm.group.cost_optimized.emptyDescription',
    },
    {
        id: 'privacy_first',
        order: 3,
        titleKey: 'llm.group.privacy_first.title',
        descriptionKey: 'llm.group.privacy_first.description',
        emptyTitleKey: 'llm.group.privacy_first.emptyTitle',
        emptyDescriptionKey: 'llm.group.privacy_first.emptyDescription',
    },
    {
        id: 'offline_capable',
        order: 4,
        titleKey: 'llm.group.offline_capable.title',
        descriptionKey: 'llm.group.offline_capable.description',
        emptyTitleKey: 'llm.group.offline_capable.emptyTitle',
        emptyDescriptionKey: 'llm.group.offline_capable.emptyDescription',
    },
];
function getCapabilityGroupDefinition(group) {
    const match = exports.CAPABILITY_GROUP_DEFINITIONS.find((entry) => entry.id === group);
    if (match) {
        return match;
    }
    return exports.CAPABILITY_GROUP_DEFINITIONS[0];
}
