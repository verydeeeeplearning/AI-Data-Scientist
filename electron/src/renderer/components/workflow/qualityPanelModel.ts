import type { ReviewVerdictView, ShadowComparisonView } from '../../types/taskContract';

export interface QualityPanelBlockingIssueView {
  scope: string;
  message: string;
}

export interface QualityPanelVerifierModel {
  verdict: ReviewVerdictView;
  blockingCount: number;
  blockingIssues: QualityPanelBlockingIssueView[];
  confidenceGrade: string;
  confidencePercent: number | null;
  judgeMode: string | null;
  shadowMatchRate: number | null;
  shadowMismatchCount: number | null;
  shadowMismatchPreview: {
    comparisonKey: string;
    mismatchKind: string;
    stateSummary: string;
    note: string;
  }[];
}

export function pickEffectiveReviewVerdict(
  reviewVerdicts: ReviewVerdictView[]
): ReviewVerdictView | null {
  if (reviewVerdicts.length === 0) return null;
  const orchestratorVerdicts = reviewVerdicts.filter((item) => item.category === 'orchestrator');
  const candidates = orchestratorVerdicts.length > 0 ? orchestratorVerdicts : reviewVerdicts;
  return candidates.reduce((latest, current) => {
    const currentKey = `${current.created_at}:${current.verdict_id}`;
    const latestKey = `${latest.created_at}:${latest.verdict_id}`;
    return currentKey > latestKey ? current : latest;
  });
}

export function buildQualityPanelVerifierModel(
  latestVerdict: ReviewVerdictView | null,
  shadowComparison?: ShadowComparisonView | null
): QualityPanelVerifierModel | null {
  if (!latestVerdict) return null;

  const blockingIssues =
    latestVerdict.blocking_issues
      ?.filter((item) => item.blocking)
      .map((item) => ({
        scope: item.layer ?? item.check_id ?? 'general',
        message: item.message,
      })) ?? [];

  const judgeMode =
    typeof latestVerdict.metadata?.judge_mode === 'string'
      ? latestVerdict.metadata.judge_mode
      : null;
  const shadowMatchRate =
    typeof latestVerdict.metadata?.shadow_match_rate === 'number'
      ? latestVerdict.metadata.shadow_match_rate
      : null;
  const shadowMismatchCount =
    typeof latestVerdict.metadata?.shadow_mismatch_count === 'number'
      ? latestVerdict.metadata.shadow_mismatch_count
      : null;
  const shadowMismatchPreview =
    shadowComparison?.items
      ?.filter((item) => item.applicable && !item.matches)
      .slice(0, 2)
      .map((item) => ({
        comparisonKey: item.comparison_key,
        mismatchKind: item.mismatch_kind,
        stateSummary: `${item.legacy_state} -> ${item.verifier_state}`,
        note: item.note ?? 'Shadow mismatch recorded.',
      })) ?? [];

  return {
    verdict: latestVerdict,
    blockingCount: blockingIssues.length,
    blockingIssues,
    confidenceGrade: latestVerdict.confidence?.grade ?? 'unknown',
    confidencePercent:
      typeof latestVerdict.confidence?.score === 'number'
        ? Math.round(latestVerdict.confidence.score * 100)
        : null,
    judgeMode,
    shadowMatchRate,
    shadowMismatchCount,
    shadowMismatchPreview,
  };
}
