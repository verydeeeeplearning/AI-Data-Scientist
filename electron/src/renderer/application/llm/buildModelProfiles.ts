import {
  isCapabilityBadge,
  isCapabilityGroup,
  type CapabilityBadge,
  type CapabilityGroup,
  type ModelCatalogEntry,
  type ModelProfile,
} from '../../domain/llm/modelCapability';

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

function buildText(entry: ModelCatalogEntry): string {
  return `${entry.id} ${entry.displayName}`.toLowerCase();
}

function hasLongContext(entry: ModelCatalogEntry): boolean {
  return entry.maxContext >= 500_000;
}

function inferCapabilityGroup(entry: ModelCatalogEntry): CapabilityGroup {
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

function pushBadge(target: CapabilityBadge[], badge: CapabilityBadge, predicate: boolean): void {
  if (!predicate || target.includes(badge)) {
    return;
  }
  target.push(badge);
}

function inferBadges(entry: ModelCatalogEntry, group: CapabilityGroup): CapabilityBadge[] {
  const text = buildText(entry);
  const badges: CapabilityBadge[] = [];

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

function inferRecommendedFor(group: CapabilityGroup, badges: CapabilityBadge[]): readonly string[] {
  const recommendations = new Set<string>();

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

function compareProfiles(left: ModelProfile, right: ModelProfile): number {
  if (left.legacy !== right.legacy) {
    return left.legacy ? 1 : -1;
  }
  if (left.maxContext !== right.maxContext) {
    return right.maxContext - left.maxContext;
  }
  return left.displayName.localeCompare(right.displayName);
}

function pickBackendBadges(
  entry: ModelCatalogEntry,
): readonly CapabilityBadge[] | undefined {
  if (!entry.capabilityBadges || entry.capabilityBadges.length === 0) {
    return undefined;
  }
  const filtered = entry.capabilityBadges.filter(isCapabilityBadge);
  return filtered.length > 0 ? filtered : undefined;
}

function pickBackendRecommendedFor(
  entry: ModelCatalogEntry,
): readonly string[] | undefined {
  if (!entry.recommendedFor || entry.recommendedFor.length === 0) {
    return undefined;
  }
  return entry.recommendedFor;
}

export function buildModelProfile(entry: ModelCatalogEntry): ModelProfile {
  const backendGroup = isCapabilityGroup(entry.capabilityGroup) ? entry.capabilityGroup : undefined;
  const capabilityGroup = backendGroup ?? inferCapabilityGroup(entry);

  const backendBadges = pickBackendBadges(entry);
  const badges: CapabilityBadge[] = backendBadges
    ? [...backendBadges].slice(0, 4)
    : inferBadges(entry, capabilityGroup);

  const backendRecommendations = pickBackendRecommendedFor(entry);
  const recommendedFor: readonly string[] = backendRecommendations
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

export function buildModelProfiles(entries: readonly ModelCatalogEntry[]): ModelProfile[] {
  return [...entries].map(buildModelProfile).sort(compareProfiles);
}
