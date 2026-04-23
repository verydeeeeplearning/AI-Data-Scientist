/**
 * Application-layer port for fetching trust metadata.
 *
 * Trust store consumers depend only on this port; infrastructure binds the
 * implementation (`infrastructure/api/trustApi.ts`) at the composition root.
 */

import type { TrustMetadata } from './trustTypes';

export type FetchTrustPort = (resultId: string) => Promise<TrustMetadata>;
