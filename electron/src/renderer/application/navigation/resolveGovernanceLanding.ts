import type { AreaSelection } from '../../domain/navigation/area';

export type GovernanceSectionId = 'review' | 'certification' | 'policy' | 'approvals';
export type GovernanceDetailKind =
  | 'verifier'
  | 'lineage'
  | 'fallback-log'
  | 'approval'
  | 'drift'
  | 'certification'
  | 'policy';

export interface GovernanceLandingDetail {
  readonly kind: GovernanceDetailKind;
  readonly id: string | null;
}

export interface GovernanceLandingState {
  readonly sectionId: GovernanceSectionId;
  readonly sectionPath: string;
  readonly detail: GovernanceLandingDetail | null;
}

const GOVERNANCE_SECTION_PATHS: Readonly<Record<GovernanceSectionId, string>> = Object.freeze({
  review: '/governance/review',
  certification: '/governance/certification',
  policy: '/governance/policy',
  approvals: '/governance/approvals',
});

export function buildGovernanceSectionPath(sectionId: GovernanceSectionId): string {
  return GOVERNANCE_SECTION_PATHS[sectionId];
}

function createLandingState(
  sectionId: GovernanceSectionId,
  detail: GovernanceLandingDetail | null = null,
): GovernanceLandingState {
  return {
    sectionId,
    sectionPath: buildGovernanceSectionPath(sectionId),
    detail,
  };
}

function joinDetailId(segments: readonly string[]): string | null {
  const value = segments.join('/').trim();
  return value.length > 0 ? value : null;
}

export function resolveGovernanceLanding(
  selection: Pick<AreaSelection, 'subPath'>,
): GovernanceLandingState {
  const [primary = 'review', ...rest] = selection.subPath?.split('/').filter(Boolean) ?? [];
  const detailId = joinDetailId(rest);

  switch (primary) {
    case 'review':
      return createLandingState('review');
    case 'verifier':
      return createLandingState('review', { kind: 'verifier', id: detailId });
    case 'lineage':
      return createLandingState('review', { kind: 'lineage', id: detailId });
    case 'fallback-log':
      return createLandingState('review', { kind: 'fallback-log', id: detailId });
    case 'drift':
      return createLandingState('review', { kind: 'drift', id: detailId });
    case 'certification':
      return createLandingState(
        'certification',
        detailId ? { kind: 'certification', id: detailId } : null,
      );
    case 'policy':
    case 'policies':
      return createLandingState('policy', detailId ? { kind: 'policy', id: detailId } : null);
    case 'approval':
    case 'approvals':
      return createLandingState(
        'approvals',
        detailId ? { kind: 'approval', id: detailId } : null,
      );
    default:
      return createLandingState('review');
  }
}
