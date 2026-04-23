import type {
  GovernanceDetailKind,
  GovernanceSectionId,
} from '../navigation/resolveGovernanceLanding';

export type TrustBadgeStatus = 'pass' | 'warn' | 'fail' | 'pending' | 'unknown';

export type TrustBadgeKind = GovernanceDetailKind | 'unknown';

export interface TrustNavigationTarget {
  readonly path: string;
  readonly sectionId: GovernanceSectionId;
  readonly detailKind: GovernanceDetailKind | null;
  readonly detailId: string | null;
}

export interface TrustBadgeViewModel {
  readonly key: string;
  readonly kind: TrustBadgeKind;
  readonly label: string;
  readonly status: TrustBadgeStatus;
  readonly detail: string | null;
  readonly href: string;
  readonly target: TrustNavigationTarget;
}

export interface TrustMetadata {
  readonly resultId: string;
  readonly badges: readonly TrustBadgeViewModel[];
  readonly fetchedAt: number;
  readonly updatedAt: string | null;
}
