/**
 * Composition root for the trust store singleton.
 *
 * `application/trust/trustStore.ts` exposes a pure factory that requires the
 * `FetchTrustPort`. This module binds the HTTP adapter and exports the React
 * hook + singleton handle so that the application layer never imports from
 * infrastructure (Clean Arch + lint:arch compliance).
 */

import {
  bindTrustStoreHook,
  createTrustStore,
  type TrustState,
} from '../application/trust/trustStore';
import { fetchTrustByResultId } from '../infrastructure/api/trustApi';

export const trustStore = createTrustStore(fetchTrustByResultId);

export const useTrustStore = bindTrustStoreHook(trustStore);

export type { TrustState };
