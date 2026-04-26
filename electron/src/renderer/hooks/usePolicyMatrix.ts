/**
 * Composition hook: bind risk-tier matrix application use cases to the
 * `policy.matrix.*` RPC family.
 *
 * The hook is the single composition seam — it wires the renderer's
 * `useWs` rpc into the application-layer ports defined in
 * `application/policy/matrixPort`. Components only see the ports +
 * use-case helpers, which keeps the renderer free of transport details.
 */

import { useCallback, useMemo } from 'react';
import { useWs } from './WsProvider';
import { loadRiskTierMatrix } from '../application/policy/loadRiskTierMatrix';
import { normalizeRiskTierMatrix } from '../application/policy/riskTierMatrix';
import { previewMatrixImpact } from '../application/policy/previewMatrixImpact';
import { saveRiskTierMatrix } from '../application/policy/saveRiskTierMatrix';
import type {
  LoadRiskTierMatrixPort,
  LoadRiskTierMatrixResult,
  PreviewMatrixImpactInput,
  PreviewMatrixImpactPort,
  PreviewMatrixImpactResult,
  RiskTierMatrix,
  RiskTierMatrixSnapshot,
  SaveRiskTierMatrixInput,
  SaveRiskTierMatrixPort,
} from '../application/policy/matrixPort';

function normalizeMatrix(raw: unknown): RiskTierMatrix {
  return normalizeRiskTierMatrix(raw);
}

function normalizeSnapshot(raw: unknown): RiskTierMatrixSnapshot {
  const obj = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
  const savedAt = typeof obj.savedAt === 'number' ? obj.savedAt : 0;
  const matrix = normalizeMatrix(obj.matrix);
  const savedByRaw = obj.savedBy;
  const savedBy = typeof savedByRaw === 'string' && savedByRaw.trim()
    ? savedByRaw
    : null;
  return { savedAt, matrix, savedBy };
}

function normalizeStringList(raw: unknown): string[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.filter((item): item is string => typeof item === 'string');
}

function normalizeCounts(raw: unknown): Record<string, number> {
  if (!raw || typeof raw !== 'object') {
    return {};
  }
  const result: Record<string, number> = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      result[key] = value;
    }
  }
  return result;
}

export interface UsePolicyMatrixApi {
  readonly load: () => Promise<LoadRiskTierMatrixResult>;
  readonly save: (input: SaveRiskTierMatrixInput) => Promise<RiskTierMatrixSnapshot>;
  readonly preview: (
    input: PreviewMatrixImpactInput,
  ) => Promise<PreviewMatrixImpactResult>;
}

export function usePolicyMatrix(): UsePolicyMatrixApi {
  const { rpc } = useWs();

  const loadPort = useMemo<LoadRiskTierMatrixPort>(
    () => async () => {
      const response = await rpc('policy.matrix.get');
      const matrix = normalizeMatrix(response?.matrix);
      const historyRaw = Array.isArray(response?.history) ? response.history : [];
      const history = historyRaw.map(normalizeSnapshot);
      return { matrix, history };
    },
    [rpc],
  );

  const savePort = useMemo<SaveRiskTierMatrixPort>(
    () => async (input) => {
      const params: Record<string, unknown> = { matrix: input.matrix };
      if (input.savedBy !== undefined && input.savedBy !== null) {
        params.savedBy = input.savedBy;
      }
      const response = await rpc('policy.matrix.save', params);
      return normalizeSnapshot(response?.snapshot);
    },
    [rpc],
  );

  const previewPort = useMemo<PreviewMatrixImpactPort>(
    () => async (input) => {
      const response = await rpc('policy.matrix.preview', {
        candidateMatrix: input.candidateMatrix,
      });
      return {
        addedRows: normalizeStringList(response?.addedRows),
        removedRows: normalizeStringList(response?.removedRows),
        modifiedRows: normalizeStringList(response?.modifiedRows),
        historicalCounts: normalizeCounts(response?.historicalCounts),
      };
    },
    [rpc],
  );

  const load = useCallback(() => loadRiskTierMatrix(loadPort), [loadPort]);
  const save = useCallback(
    (input: SaveRiskTierMatrixInput) => saveRiskTierMatrix(savePort, input),
    [savePort],
  );
  const preview = useCallback(
    (input: PreviewMatrixImpactInput) => previewMatrixImpact(previewPort, input),
    [previewPort],
  );

  return useMemo(() => ({ load, save, preview }), [load, save, preview]);
}
