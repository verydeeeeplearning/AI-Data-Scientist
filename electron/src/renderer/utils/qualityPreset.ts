/**
 * Shared quality preset metadata for simple AI setup UX.
 */

export type QualityPreset = 'best_quality' | 'balanced' | 'fast' | 'local' | 'custom';
export type SimpleQualityPreset = Exclude<QualityPreset, 'custom'>;

export interface QualityPresetDefinition {
  id: QualityPreset;
  label: string;
  summary: string;
  description: string;
}

export const QUALITY_PRESET_MODEL_MAP: Record<
  SimpleQualityPreset,
  { primary: string; fallback: string[] }
> = {
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

export const SIMPLE_QUALITY_PRESETS: SimpleQualityPreset[] = [
  'best_quality',
  'balanced',
  'fast',
  'local',
];

const QUALITY_PRESET_DEFINITIONS: Record<QualityPreset, QualityPresetDefinition> = {
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

export function normalizeQualityPreset(value: unknown): QualityPreset {
  if (
    value === 'best_quality'
    || value === 'balanced'
    || value === 'fast'
    || value === 'local'
    || value === 'custom'
  ) {
    return value;
  }
  return 'custom';
}

export function getQualityPresetDefinition(preset: QualityPreset): QualityPresetDefinition {
  return QUALITY_PRESET_DEFINITIONS[preset];
}
