"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildModelProfile = buildModelProfile;
exports.buildModelProfiles = buildModelProfiles;
const modelCapability_1 = require("../../domain/llm/modelCapability");
const HIGH_END_MODEL_RE = /(claude-opus|claude-sonnet|gpt-5\.4(?!-(mini|nano))|gpt-4\.1$|gemini-.*pro|glm-5|kimi-k2\.5)/;
const FAST_MODEL_RE = /(flash|haiku|mini|nano|spark|scout)/;
const CHEAP_MODEL_RE = /(haiku|mini|nano|flash-lite|deepseek-chat|scout)/;
const REASONING_MODEL_RE = /(opus|sonnet|reasoner|r1|gpt-5|gpt-4\.1|pro|glm-5|kimi-k2\.5)/;
const CODING_MODEL_RE = /(codex|claude|gpt|qwen|deepseek)/;
const KOREAN_MODEL_PROVIDERS = new Set([
    'anthropic',
    'openai',
    'codex',
    'gemini',
    'deepseek',
    'qwen',
    'zhipu',
    'moonshot',
]);
const MULTIMODAL_PROVIDERS = new Set(['anthropic', 'openai', 'codex', 'gemini']);
function buildText(entry) {
    return `${entry.id} ${entry.displayName}`.toLowerCase();
}
function hasLongContext(entry) {
    return entry.maxContext >= 500000;
}
function inferCapabilityGroup(entry) {
    const text = buildText(entry);
    if (entry.authType === 'local' || entry.provider === 'ollama') {
        return 'offline_capable';
    }
    if (entry.provider === 'codex' || (entry.authType === 'oauth' && text.includes('flash'))) {
        return 'fast_start';
    }
    if (HIGH_END_MODEL_RE.test(text)) {
        return 'best_quality';
    }
    if (entry.authType === 'free_api_key' || CHEAP_MODEL_RE.test(text)) {
        return 'cost_optimized';
    }
    if (entry.authType === 'api_key') {
        return 'privacy_first';
    }
    return 'fast_start';
}
function pushBadge(target, badge, predicate) {
    if (!predicate || target.includes(badge)) {
        return;
    }
    target.push(badge);
}
function inferBadges(entry, group) {
    const text = buildText(entry);
    const badges = [];
    pushBadge(badges, 'offline', group === 'offline_capable');
    pushBadge(badges, 'fast', entry.authType === 'oauth' || FAST_MODEL_RE.test(text));
    pushBadge(badges, 'cheap', entry.authType === 'free_api_key' || CHEAP_MODEL_RE.test(text));
    pushBadge(badges, 'strong_coding', CODING_MODEL_RE.test(text));
    pushBadge(badges, 'strong_korean', KOREAN_MODEL_PROVIDERS.has(entry.provider));
    pushBadge(badges, 'long_context', hasLongContext(entry));
    pushBadge(badges, 'strong_reasoning', REASONING_MODEL_RE.test(text));
    pushBadge(badges, 'multimodal', MULTIMODAL_PROVIDERS.has(entry.provider));
    return badges.slice(0, 4);
}
function inferRecommendedFor(group, badges) {
    const recommendations = new Set();
    if (group === 'fast_start') {
        recommendations.add('first_run');
        recommendations.add('quick_checks');
    }
    if (group === 'best_quality') {
        recommendations.add('deep_analysis');
        recommendations.add('decision_ready_reports');
    }
    if (group === 'cost_optimized') {
        recommendations.add('iteration');
        recommendations.add('budget_sensitive');
    }
    if (group === 'privacy_first') {
        recommendations.add('byo_credentials');
        recommendations.add('controlled_access');
    }
    if (group === 'offline_capable') {
        recommendations.add('offline');
        recommendations.add('local_only');
    }
    if (badges.includes('strong_korean')) {
        recommendations.add('korean');
    }
    if (badges.includes('strong_coding')) {
        recommendations.add('coding');
    }
    if (badges.includes('strong_reasoning')) {
        recommendations.add('reasoning');
    }
    return Array.from(recommendations);
}
function compareProfiles(left, right) {
    if (left.legacy !== right.legacy) {
        return left.legacy ? 1 : -1;
    }
    if (left.maxContext !== right.maxContext) {
        return right.maxContext - left.maxContext;
    }
    return left.displayName.localeCompare(right.displayName);
}
function pickBackendBadges(entry) {
    if (!entry.capabilityBadges || entry.capabilityBadges.length === 0) {
        return undefined;
    }
    const filtered = entry.capabilityBadges.filter(modelCapability_1.isCapabilityBadge);
    return filtered.length > 0 ? filtered : undefined;
}
function pickBackendRecommendedFor(entry) {
    if (!entry.recommendedFor || entry.recommendedFor.length === 0) {
        return undefined;
    }
    return entry.recommendedFor;
}
function buildModelProfile(entry) {
    const backendGroup = (0, modelCapability_1.isCapabilityGroup)(entry.capabilityGroup) ? entry.capabilityGroup : undefined;
    const capabilityGroup = backendGroup ?? inferCapabilityGroup(entry);
    const backendBadges = pickBackendBadges(entry);
    const badges = backendBadges
        ? [...backendBadges].slice(0, 4)
        : inferBadges(entry, capabilityGroup);
    const backendRecommendations = pickBackendRecommendedFor(entry);
    const recommendedFor = backendRecommendations
        ? [...backendRecommendations]
        : inferRecommendedFor(capabilityGroup, badges);
    return {
        ...entry,
        providerCategory: entry.authType,
        capabilityGroup,
        badges,
        recommendedFor,
        providerLabelLegacy: entry.providerLabelLegacy,
    };
}
function buildModelProfiles(entries) {
    return [...entries].map(buildModelProfile).sort(compareProfiles);
}
