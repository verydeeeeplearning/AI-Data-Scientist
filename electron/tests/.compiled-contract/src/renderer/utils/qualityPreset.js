"use strict";
/**
 * Shared quality preset metadata for simple AI setup UX.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SIMPLE_QUALITY_PRESETS = exports.QUALITY_PRESET_MODEL_MAP = void 0;
exports.normalizeQualityPreset = normalizeQualityPreset;
exports.getQualityPresetDefinition = getQualityPresetDefinition;
exports.QUALITY_PRESET_MODEL_MAP = {
    best_quality: {
        primary: 'anthropic/claude-opus-4-6',
        fallback: ['openai/gpt-4.1'],
    },
    balanced: {
        primary: 'anthropic/claude-sonnet-4-6',
        fallback: ['openai/gpt-4.1-mini'],
    },
    fast: {
        primary: 'anthropic/claude-haiku-4-5',
        fallback: ['openai/gpt-4.1-mini'],
    },
    local: {
        primary: 'ollama/llama3.2',
        fallback: [],
    },
};
exports.SIMPLE_QUALITY_PRESETS = [
    'best_quality',
    'balanced',
    'fast',
    'local',
];
const QUALITY_PRESET_DEFINITIONS = {
    best_quality: {
        id: 'best_quality',
        label: 'Best quality',
        summary: 'Best for deeper analysis and richer reports.',
        description: 'Complex analysis, long-form summaries, and higher-quality outputs.',
    },
    balanced: {
        id: 'balanced',
        label: 'Balanced',
        summary: 'Recommended for most data science work.',
        description: 'A strong default for exploration, reporting, and iterative analysis.',
    },
    fast: {
        id: 'fast',
        label: 'Fast',
        summary: 'Best for lighter questions and quick checks.',
        description: 'Lower-cost, faster responses for routine questions.',
    },
    local: {
        id: 'local',
        label: 'Local',
        summary: 'Runs on this computer without a cloud account.',
        description: 'Best when you want offline or local-first usage.',
    },
    custom: {
        id: 'custom',
        label: 'Custom',
        summary: 'Using a manually selected model configuration.',
        description: 'Advanced mode with a direct model selection.',
    },
};
function normalizeQualityPreset(value) {
    if (value === 'best_quality'
        || value === 'balanced'
        || value === 'fast'
        || value === 'local'
        || value === 'custom') {
        return value;
    }
    return 'custom';
}
function getQualityPresetDefinition(preset) {
    return QUALITY_PRESET_DEFINITIONS[preset];
}
