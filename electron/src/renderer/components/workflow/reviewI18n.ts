import type { ReviewSkillName } from './decisionOsReviewModel';

export type ReviewTranslateFn = (
  key: string,
  vars?: Record<string, string | number | undefined | null>,
) => string;

export function translateReviewStatus(value: string, t: ReviewTranslateFn): string {
  const keyByStatus: Record<string, string> = {
    pass: 'workspace.workflow.review.status.pass',
    warn: 'workspace.workflow.review.status.warn',
    fail: 'workspace.workflow.review.status.fail',
    error: 'workspace.workflow.review.status.error',
    skipped: 'workspace.workflow.review.status.skipped',
    approved: 'workspace.workflow.review.status.approved',
    rejected: 'workspace.workflow.review.status.rejected',
    pending: 'workspace.workflow.review.status.pending',
    ok: 'workspace.workflow.review.status.ok',
    warning: 'workspace.workflow.review.status.warning',
    alert: 'workspace.workflow.review.status.alert',
  };
  const key = keyByStatus[value];
  if (key) {
    return t(key);
  }
  if (value.startsWith('pending')) {
    return t('workspace.workflow.review.status.pending');
  }
  return value;
}

export function translatePromotionStage(value: string, t: ReviewTranslateFn): string {
  const keyByStage: Record<string, string> = {
    staging: 'workspace.workflow.review.promotionGate.stage.staging',
    production: 'workspace.workflow.review.promotionGate.stage.production',
    canary: 'workspace.workflow.review.promotionGate.stage.canary',
  };
  const key = keyByStage[value];
  return key ? t(key) : value;
}

export function translateReviewSkillLabel(skill: ReviewSkillName, t: ReviewTranslateFn): string {
  return t(`workspace.workflow.review.sharedSkills.label.${skill}`);
}

export function translateReviewArtifactType(value: string, t: ReviewTranslateFn): string {
  const keyByType: Record<string, string> = {
    backtesting: 'workspace.workflow.review.sharedSkills.artifactType.backtesting',
    'causal-assumption-check': 'workspace.workflow.review.sharedSkills.artifactType.causal-assumption-check',
    'uncertainty-quantification': 'workspace.workflow.review.sharedSkills.artifactType.uncertainty-quantification',
    'retrain-vs-rollback': 'workspace.workflow.review.sharedSkills.artifactType.retrain-vs-rollback',
  };
  const key = keyByType[value];
  return key ? t(key) : value;
}
