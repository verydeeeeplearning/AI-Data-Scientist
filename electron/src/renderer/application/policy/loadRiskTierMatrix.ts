import type {
  LoadRiskTierMatrixPort,
  LoadRiskTierMatrixResult,
} from './matrixPort';

/**
 * Application use case: fetch the persisted risk-tier matrix and the
 * recent history slice through an injected port.
 *
 * The use case is intentionally thin — the backend already returns the
 * normalized payload — but routing through this function keeps the
 * renderer hook free of validation drift and gives contract tests a
 * single seam to stub.
 */
export async function loadRiskTierMatrix(
  port: LoadRiskTierMatrixPort,
): Promise<LoadRiskTierMatrixResult> {
  return port();
}
