import type { CapabilityBadge, ModelProfile } from '../../domain/llm/modelCapability';

export interface RecommendModelContext {
  locale: string;
  taskType?: string | null;
  qualityPreset?: string | null;
  readyModelIds?: ReadonlySet<string>;
}

export type RecommendationReason =
  | 'ready'
  | 'korean'
  | 'quality'
  | 'cost'
  | 'speed'
  | 'privacy'
  | 'offline'
  | 'coding'
  | 'reasoning';

export interface ModelRecommendation {
  model: ModelProfile;
  reasons: RecommendationReason[];
  score: number;
}

function hasBadge(model: ModelProfile, badge: CapabilityBadge): boolean {
  return model.badges.includes(badge);
}

function appendReason(
  reasons: RecommendationReason[],
  reason: RecommendationReason,
  condition: boolean,
  score: number,
): number {
  if (!condition) {
    return 0;
  }
  if (!reasons.includes(reason)) {
    reasons.push(reason);
  }
  return score;
}

function normalizeTaskType(taskType?: string | null): string {
  return (taskType ?? '').trim().toLowerCase();
}

export function recommendModel(
  models: readonly ModelProfile[],
  context: RecommendModelContext,
): ModelRecommendation | undefined {
  const taskType = normalizeTaskType(context.taskType);
  const qualityPreset = (context.qualityPreset ?? 'balanced').trim().toLowerCase();
  const readyModelIds = context.readyModelIds;

  const ranked = models.map((model) => {
    const reasons: RecommendationReason[] = [];
    let score = model.legacy ? -3 : 1;

    score += appendReason(reasons, 'ready', readyModelIds?.has(model.id) === true, 4);
    score += appendReason(reasons, 'korean', context.locale === 'ko' && hasBadge(model, 'strong_korean'), 3);
    score += appendReason(
      reasons,
      'reasoning',
      (taskType === 'prediction'
        || taskType === 'data_analysis'
        || taskType === 'sql_exploration')
        && hasBadge(model, 'strong_reasoning'),
      3,
    );
    score += appendReason(
      reasons,
      'coding',
      taskType.includes('coding') && hasBadge(model, 'strong_coding'),
      3,
    );
    score += appendReason(
      reasons,
      'speed',
      (qualityPreset === 'fast' || taskType === 'general' || taskType === 'dashboard')
        && hasBadge(model, 'fast'),
      2,
    );
    score += appendReason(
      reasons,
      'cost',
      (qualityPreset === 'fast' || qualityPreset === 'balanced') && hasBadge(model, 'cheap'),
      2,
    );
    score += appendReason(
      reasons,
      'quality',
      qualityPreset === 'best_quality' && model.capabilityGroup === 'best_quality',
      3,
    );
    score += appendReason(
      reasons,
      'offline',
      qualityPreset === 'local' && model.capabilityGroup === 'offline_capable',
      5,
    );
    score += appendReason(
      reasons,
      'privacy',
      qualityPreset === 'custom' && model.capabilityGroup === 'privacy_first',
      2,
    );

    if (hasBadge(model, 'long_context')) {
      score += 1;
    }

    return { model, reasons, score };
  });

  ranked.sort((left, right) => {
    if (left.score !== right.score) {
      return right.score - left.score;
    }
    if (left.model.maxContext !== right.model.maxContext) {
      return right.model.maxContext - left.model.maxContext;
    }
    return left.model.displayName.localeCompare(right.model.displayName);
  });

  const top = ranked[0];
  if (!top) {
    return undefined;
  }

  return {
    ...top,
    reasons: top.reasons.slice(0, 2),
  };
}
