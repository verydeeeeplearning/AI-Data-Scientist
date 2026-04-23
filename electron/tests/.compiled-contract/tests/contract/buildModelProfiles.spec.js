"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const buildModelProfiles_1 = require("../../src/renderer/application/llm/buildModelProfiles");
function baseEntry(overrides = {}) {
    return {
        id: 'anthropic/claude-sonnet-4-6',
        provider: 'anthropic',
        displayName: 'Claude Sonnet 4.6',
        maxContext: 1000000,
        maxOutput: 64000,
        authType: 'api_key',
        legacy: false,
        ...overrides,
    };
}
function run() {
    // === backend metadata overrides heuristic when present ===
    {
        const entry = baseEntry({
            capabilityGroup: 'cost_optimized',
            capabilityBadges: ['cheap', 'fast'],
            recommendedFor: ['budget_sensitive'],
            providerLabelLegacy: 'Previously: Anthropic Claude Sonnet 4.6 (anthropic/claude-sonnet-4-6)',
        });
        const profile = (0, buildModelProfiles_1.buildModelProfile)(entry);
        strict_1.default.equal(profile.capabilityGroup, 'cost_optimized');
        strict_1.default.deepEqual(profile.badges, ['cheap', 'fast']);
        strict_1.default.deepEqual(profile.recommendedFor, ['budget_sensitive']);
        strict_1.default.equal(profile.providerLabelLegacy, 'Previously: Anthropic Claude Sonnet 4.6 (anthropic/claude-sonnet-4-6)');
    }
    // === heuristic fallback when backend metadata absent ===
    {
        const entry = baseEntry();
        const profile = (0, buildModelProfiles_1.buildModelProfile)(entry);
        strict_1.default.ok(profile.capabilityGroup, 'capabilityGroup must be set by heuristic');
        strict_1.default.ok(profile.badges.length >= 1, 'badges must be inferred when missing');
        strict_1.default.ok(profile.recommendedFor.length >= 1, 'recommendedFor must be inferred when missing');
    }
    // === heuristic anthropic opus -> best_quality ===
    {
        const entry = baseEntry({
            id: 'anthropic/claude-opus-4-6',
            displayName: 'Claude Opus 4.6',
        });
        const profile = (0, buildModelProfiles_1.buildModelProfile)(entry);
        strict_1.default.equal(profile.capabilityGroup, 'best_quality');
    }
    // === heuristic local provider -> offline_capable ===
    {
        const entry = baseEntry({
            id: 'ollama/llama3-8b',
            provider: 'ollama',
            displayName: 'Llama 3 8B',
            maxContext: 8000,
            maxOutput: 4000,
            authType: 'local',
        });
        const profile = (0, buildModelProfiles_1.buildModelProfile)(entry);
        strict_1.default.equal(profile.capabilityGroup, 'offline_capable');
        strict_1.default.ok(profile.badges.includes('offline'));
    }
    // === backend metadata partially present -> still uses backend group, heuristic badges only if missing ===
    {
        const entry = baseEntry({
            id: 'anthropic/claude-haiku-4-5',
            displayName: 'Claude Haiku 4.5',
            capabilityGroup: 'fast_start',
            // intentionally omit capabilityBadges + recommendedFor + providerLabelLegacy
        });
        const profile = (0, buildModelProfiles_1.buildModelProfile)(entry);
        strict_1.default.equal(profile.capabilityGroup, 'fast_start');
        strict_1.default.ok(profile.badges.length >= 1, 'heuristic must fill missing badges');
    }
    // === buildModelProfiles preserves backend metadata for entire batch ===
    {
        const entries = [
            baseEntry({
                id: 'anthropic/claude-opus-4-6',
                displayName: 'Claude Opus 4.6',
                capabilityGroup: 'best_quality',
                capabilityBadges: ['strong_reasoning', 'multimodal'],
                recommendedFor: ['deep_analysis'],
            }),
            baseEntry({
                id: 'codex/gpt-5.4',
                provider: 'codex',
                displayName: 'GPT-5.4 (Codex)',
                authType: 'oauth',
                capabilityGroup: 'fast_start',
                capabilityBadges: ['fast', 'strong_reasoning'],
                recommendedFor: ['first_run'],
            }),
        ];
        const profiles = (0, buildModelProfiles_1.buildModelProfiles)(entries);
        strict_1.default.equal(profiles.length, 2);
        const opus = profiles.find((p) => p.id === 'anthropic/claude-opus-4-6');
        const codex = profiles.find((p) => p.id === 'codex/gpt-5.4');
        strict_1.default.ok(opus);
        strict_1.default.ok(codex);
        strict_1.default.equal(opus.capabilityGroup, 'best_quality');
        strict_1.default.equal(codex.capabilityGroup, 'fast_start');
    }
    // === providerLabelLegacy survives untouched when supplied by backend ===
    {
        const entry = baseEntry({
            providerLabelLegacy: 'Previously: Anthropic Claude Sonnet 4.6 (anthropic/claude-sonnet-4-6)',
        });
        const profile = (0, buildModelProfiles_1.buildModelProfile)(entry);
        strict_1.default.equal(profile.providerLabelLegacy, 'Previously: Anthropic Claude Sonnet 4.6 (anthropic/claude-sonnet-4-6)');
    }
    // === invalid backend group falls back to heuristic ===
    {
        const entry = baseEntry({
            id: 'anthropic/claude-opus-4-6',
            displayName: 'Claude Opus 4.6',
            capabilityGroup: 'not_a_real_group',
        });
        const profile = (0, buildModelProfiles_1.buildModelProfile)(entry);
        strict_1.default.equal(profile.capabilityGroup, 'best_quality');
    }
    console.log('buildModelProfiles.spec.ts: all assertions passed');
}
run();
