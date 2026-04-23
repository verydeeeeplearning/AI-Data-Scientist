/**
 * Renderer-side ports for the risk-tier matrix backend.
 *
 * Each port is a single async function so the composition hook
 * (`usePolicyMatrix`) can wire them to `rpc('policy.matrix.*')` while
 * keeping the application use cases (load/save/preview) pure and
 * trivially mockable in contract tests.
 */

export type RiskTierMatrix = Readonly<Record<string, Readonly<Record<string, string>>>>;

export interface RiskTierMatrixSnapshot {
  readonly savedAt: number;
  readonly matrix: RiskTierMatrix;
  readonly savedBy: string | null;
}

export interface LoadRiskTierMatrixResult {
  readonly matrix: RiskTierMatrix;
  readonly history: ReadonlyArray<RiskTierMatrixSnapshot>;
}

export interface SaveRiskTierMatrixInput {
  readonly matrix: RiskTierMatrix;
  readonly savedBy?: string | null;
}

export interface PreviewMatrixImpactInput {
  readonly candidateMatrix: RiskTierMatrix;
}

export interface PreviewMatrixImpactResult {
  readonly addedRows: ReadonlyArray<string>;
  readonly removedRows: ReadonlyArray<string>;
  readonly modifiedRows: ReadonlyArray<string>;
  readonly historicalCounts: Readonly<Record<string, number>>;
}

export interface LoadRiskTierMatrixPort {
  (): Promise<LoadRiskTierMatrixResult>;
}

export interface SaveRiskTierMatrixPort {
  (input: SaveRiskTierMatrixInput): Promise<RiskTierMatrixSnapshot>;
}

export interface PreviewMatrixImpactPort {
  (input: PreviewMatrixImpactInput): Promise<PreviewMatrixImpactResult>;
}
