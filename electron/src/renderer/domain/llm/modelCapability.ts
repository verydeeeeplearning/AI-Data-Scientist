export type ModelAuthType = 'api_key' | 'oauth' | 'free_api_key' | 'local';

export type CapabilityGroup =
  | 'fast_start'
  | 'best_quality'
  | 'cost_optimized'
  | 'privacy_first'
  | 'offline_capable';

export type CapabilityBadge =
  | 'fast'
  | 'cheap'
  | 'strong_coding'
  | 'strong_korean'
  | 'offline'
  | 'long_context'
  | 'strong_reasoning'
  | 'multimodal';

export interface ModelCatalogEntry {
  id: string;
  provider: string;
  displayName: string;
  maxContext: number;
  maxOutput: number;
  authType: ModelAuthType;
  legacy: boolean;
  capabilityGroup?: CapabilityGroup;
  capabilityBadges?: readonly CapabilityBadge[];
  recommendedFor?: readonly string[];
  providerLabelLegacy?: string;
}

export interface ModelProfile extends ModelCatalogEntry {
  providerCategory: ModelAuthType;
  capabilityGroup: CapabilityGroup;
  badges: CapabilityBadge[];
  recommendedFor: readonly string[];
  providerLabelLegacy?: string;
}

export const ALL_CAPABILITY_BADGES: readonly CapabilityBadge[] = [
  'fast',
  'cheap',
  'strong_coding',
  'strong_korean',
  'offline',
  'long_context',
  'strong_reasoning',
  'multimodal',
] as const;

export function isCapabilityGroup(value: unknown): value is CapabilityGroup {
  return (
    value === 'fast_start'
    || value === 'best_quality'
    || value === 'cost_optimized'
    || value === 'privacy_first'
    || value === 'offline_capable'
  );
}

export function isCapabilityBadge(value: unknown): value is CapabilityBadge {
  return typeof value === 'string' && (ALL_CAPABILITY_BADGES as readonly string[]).includes(value);
}

export interface CapabilityGroupDefinition {
  id: CapabilityGroup;
  order: number;
  titleKey: string;
  descriptionKey: string;
  emptyTitleKey: string;
  emptyDescriptionKey: string;
}

export interface ModelCapabilityGroup extends CapabilityGroupDefinition {
  models: ModelProfile[];
}

export const CAPABILITY_GROUP_DEFINITIONS: readonly CapabilityGroupDefinition[] = [
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
] as const;

export function getCapabilityGroupDefinition(group: CapabilityGroup): CapabilityGroupDefinition {
  const match = CAPABILITY_GROUP_DEFINITIONS.find((entry) => entry.id === group);
  if (match) {
    return match;
  }

  return CAPABILITY_GROUP_DEFINITIONS[0];
}
