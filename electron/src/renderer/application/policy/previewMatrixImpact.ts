import type {
  PreviewMatrixImpactInput,
  PreviewMatrixImpactPort,
  PreviewMatrixImpactResult,
  RiskTierMatrix,
  RiskTierMatrixSnapshot,
} from './matrixPort';

/**
 * Application use case: build a history-backed impact preview for a
 * candidate matrix.
 *
 * The use case forwards the request to the backend port and exposes
 * pure helpers (`mergeImpactPreview`, `formatLastSavedLabel`) the
 * renderer reuses to overlay the heuristic preview on top of the
 * backend-derived counts.
 */
export async function previewMatrixImpact(
  port: PreviewMatrixImpactPort,
  input: PreviewMatrixImpactInput,
): Promise<PreviewMatrixImpactResult> {
  if (!input.candidateMatrix || typeof input.candidateMatrix !== 'object') {
    throw new Error('candidateMatrix is required');
  }
  return port(input);
}

export interface MergedImpactPreview {
  readonly addedRows: ReadonlyArray<string>;
  readonly removedRows: ReadonlyArray<string>;
  readonly modifiedRows: ReadonlyArray<string>;
  readonly historicalCounts: Readonly<Record<string, number>>;
  readonly heuristicChangedCells: number;
}

/**
 * Combine the backend-derived preview with the renderer's local
 * heuristic count of changed cells.
 *
 * The renderer keeps its own quick "how many cells differ" tally so the
 * preview stays responsive while the RPC is still in-flight; this
 * helper merges that local tally with the authoritative backend result.
 */
export function mergeImpactPreview(
  backend: PreviewMatrixImpactResult,
  heuristicChangedCells: number,
): MergedImpactPreview {
  const safeChangedCells = Math.max(0, Math.floor(heuristicChangedCells || 0));
  return {
    addedRows: backend.addedRows,
    removedRows: backend.removedRows,
    modifiedRows: backend.modifiedRows,
    historicalCounts: backend.historicalCounts,
    heuristicChangedCells: safeChangedCells,
  };
}

/**
 * Format the "Last saved: <ISO date> by <savedBy>" label shown above
 * the matrix editor.
 *
 * Returns `null` when no snapshot is available so callers can hide the
 * label entirely instead of rendering placeholder text.
 */
export function formatLastSavedLabel(
  snapshot: RiskTierMatrixSnapshot | null | undefined,
): string | null {
  if (!snapshot) {
    return null;
  }
  const safeSavedAt = Number.isFinite(snapshot.savedAt) ? snapshot.savedAt : 0;
  if (safeSavedAt <= 0) {
    return null;
  }
  const iso = new Date(safeSavedAt * 1000).toISOString();
  if (snapshot.savedBy && snapshot.savedBy.trim()) {
    return `Last saved: ${iso} by ${snapshot.savedBy.trim()}`;
  }
  return `Last saved: ${iso}`;
}

/**
 * Count cells that differ between the persisted matrix and the
 * candidate draft. Used as the renderer's instant heuristic before the
 * backend preview comes back.
 */
export function countMatrixCellDiff(
  current: RiskTierMatrix,
  candidate: RiskTierMatrix,
): number {
  const actionNames = new Set([
    ...Object.keys(current ?? {}),
    ...Object.keys(candidate ?? {}),
  ]);
  let changed = 0;
  for (const action of actionNames) {
    const currentRow = current?.[action] ?? {};
    const candidateRow = candidate?.[action] ?? {};
    const cellNames = new Set([
      ...Object.keys(currentRow),
      ...Object.keys(candidateRow),
    ]);
    for (const cell of cellNames) {
      if ((currentRow[cell] ?? null) !== (candidateRow[cell] ?? null)) {
        changed += 1;
      }
    }
  }
  return changed;
}
