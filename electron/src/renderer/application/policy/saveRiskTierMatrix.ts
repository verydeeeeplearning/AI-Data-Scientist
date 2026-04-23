import type {
  RiskTierMatrixSnapshot,
  SaveRiskTierMatrixInput,
  SaveRiskTierMatrixPort,
} from './matrixPort';

/**
 * Application use case: persist a risk-tier matrix draft.
 *
 * The use case validates the matrix shape at the application boundary
 * so the renderer can show a friendly error before paying the cost of
 * an RPC round-trip. The backend re-validates with `JsonPolicyStore`.
 */
export async function saveRiskTierMatrix(
  port: SaveRiskTierMatrixPort,
  input: SaveRiskTierMatrixInput,
): Promise<RiskTierMatrixSnapshot> {
  if (!input.matrix || typeof input.matrix !== 'object') {
    throw new Error('matrix is required');
  }
  for (const [actionName, row] of Object.entries(input.matrix)) {
    if (!actionName.trim()) {
      throw new Error('matrix keys must be non-empty');
    }
    if (!row || typeof row !== 'object') {
      throw new Error(`matrix entry for ${actionName} must be an object`);
    }
    for (const [authority, tier] of Object.entries(row)) {
      if (!authority.trim() || typeof tier !== 'string' || !tier.trim()) {
        throw new Error(`matrix entry for ${actionName} has invalid cell`);
      }
    }
  }
  return port(input);
}
