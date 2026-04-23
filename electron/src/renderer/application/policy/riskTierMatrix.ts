import type { RiskTierMatrix, RiskTierMatrixSnapshot } from './matrixPort';

export type RiskTier = 'T0' | 'T1' | 'T2' | 'T3';

export const RISK_TIER_VALUES: readonly RiskTier[] = ['T0', 'T1', 'T2', 'T3'];

export interface RiskTierOption {
  value: RiskTier;
  label: string;
}

export const RISK_TIER_OPTIONS: readonly RiskTierOption[] = [
  { value: 'T0', label: 'T0' },
  { value: 'T1', label: 'T1' },
  { value: 'T2', label: 'T2' },
  { value: 'T3', label: 'T3' },
];

const RISK_TIER_ALIASES: Record<string, RiskTier> = {
  auto: 'T0',
  critical: 'T3',
  dual: 'T3',
  guarded: 'T1',
  approve: 'T2',
  ask: 'T1',
  routine: 'T0',
  sensitive: 'T2',
  t0: 'T0',
  t1: 'T1',
  t2: 'T2',
  t3: 'T3',
};

interface OrganizationLikeMember {
  userId?: string | null;
  role?: string | null;
  displayName?: string | null;
}

interface OrganizationLike {
  members?: ReadonlyArray<OrganizationLikeMember> | null;
}

function isRiskTier(value: unknown): value is RiskTier {
  return typeof value === 'string'
    && (RISK_TIER_VALUES as readonly string[]).includes(value.trim().toUpperCase() as RiskTier);
}

function normalizeRiskTierCode(value: string): RiskTier | null {
  const normalized = value.trim().toLowerCase();
  return RISK_TIER_ALIASES[normalized] ?? null;
}

export function coerceRiskTierValue(
  value: string | null | undefined,
  fallback: RiskTier = 'T0',
): RiskTier {
  if (value === null || value === undefined) {
    return fallback;
  }
  const normalized = normalizeRiskTierCode(value);
  if (normalized !== null) {
    return normalized;
  }
  const upper = value.trim().toUpperCase();
  return isRiskTier(upper) ? upper : fallback;
}

export function normalizeRiskTierMatrix(raw: unknown): RiskTierMatrix {
  if (!raw || typeof raw !== 'object') {
    return {};
  }

  const result: Record<string, Record<string, string>> = {};
  for (const [actionName, row] of Object.entries(raw as Record<string, unknown>)) {
    const actionKey = actionName.trim();
    if (!actionKey || !row || typeof row !== 'object') {
      continue;
    }

    const cells: Record<string, string> = {};
    for (const [authority, tier] of Object.entries(row as Record<string, unknown>)) {
      const authorityKey = authority.trim();
      const tierValue = typeof tier === 'string' ? tier.trim() : '';
      if (!authorityKey || !tierValue) {
        continue;
      }
      cells[authorityKey] = tierValue;
    }

    if (Object.keys(cells).length > 0) {
      result[actionKey] = cells;
    }
  }

  return result;
}

export function countRiskTierCellDiff(
  current: RiskTierMatrix,
  draft: RiskTierMatrix,
): number {
  const actionNames = new Set([
    ...Object.keys(current ?? {}),
    ...Object.keys(draft ?? {}),
  ]);
  let changed = 0;

  for (const actionName of actionNames) {
    const currentRow = current?.[actionName] ?? {};
    const draftRow = draft?.[actionName] ?? {};
    const authorityNames = new Set([
      ...Object.keys(currentRow),
      ...Object.keys(draftRow),
    ]);
    for (const authorityName of authorityNames) {
      if ((currentRow[authorityName] ?? null) !== (draftRow[authorityName] ?? null)) {
        changed += 1;
      }
    }
  }

  return changed;
}

export function countRiskTierRowDiff(
  current: RiskTierMatrix,
  draft: RiskTierMatrix,
): number {
  const actionNames = new Set([
    ...Object.keys(current ?? {}),
    ...Object.keys(draft ?? {}),
  ]);

  let changed = 0;
  for (const actionName of actionNames) {
    const currentRow = current?.[actionName] ?? {};
    const draftRow = draft?.[actionName] ?? {};
    const authorityNames = new Set([
      ...Object.keys(currentRow),
      ...Object.keys(draftRow),
    ]);
    let rowChanged = false;
    for (const authorityName of authorityNames) {
      if ((currentRow[authorityName] ?? null) !== (draftRow[authorityName] ?? null)) {
        rowChanged = true;
        break;
      }
    }
    if (rowChanged) {
      changed += 1;
    }
  }

  return changed;
}

export function formatRiskTierLabel(value: string | null | undefined): string {
  if (value === null || value === undefined || value.trim() === '') {
    return 'Unset';
  }
  const normalized = normalizeRiskTierCode(value);
  if (normalized !== null) {
    return normalized;
  }
  return value.trim();
}

export function resolveRiskTierSavedBy(
  organization: OrganizationLike | null | undefined,
): string | null {
  const members = organization?.members ?? [];
  if (members.length === 0) {
    return null;
  }

  const rolePriority: Record<string, number> = {
    admin: 0,
    editor: 1,
    viewer: 2,
  };
  const sorted = [...members].filter((member) => {
    const userId = member.userId?.trim() ?? '';
    return userId.length > 0;
  }).sort((left, right) => {
    const leftRole = rolePriority[(left.role ?? '').trim().toLowerCase()] ?? 99;
    const rightRole = rolePriority[(right.role ?? '').trim().toLowerCase()] ?? 99;
    if (leftRole !== rightRole) {
      return leftRole - rightRole;
    }
    const leftId = left.userId?.trim() ?? '';
    const rightId = right.userId?.trim() ?? '';
    return leftId.localeCompare(rightId);
  });

  return sorted[0]?.userId?.trim() || null;
}

export function formatRiskTierSnapshotLabel(
  snapshot: RiskTierMatrixSnapshot | null | undefined,
): string | null {
  if (!snapshot) {
    return null;
  }
  const savedAt = Number.isFinite(snapshot.savedAt) ? snapshot.savedAt : 0;
  if (savedAt <= 0) {
    return null;
  }
  const iso = new Date(savedAt * 1000).toISOString();
  if (snapshot.savedBy && snapshot.savedBy.trim()) {
    return `Last saved: ${iso} by ${snapshot.savedBy.trim()}`;
  }
  return `Last saved: ${iso}`;
}
