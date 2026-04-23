/**
 * Application-layer port for toggling result card pin state.
 *
 * Components depend on the port; the composition root binds the HTTP
 * adapter (`infrastructure/api/cardApi.ts`) so the components layer never
 * imports from infrastructure (Clean Arch + lint:arch compliance).
 */

import type { ResultCardPayload } from '../../types/events';

export interface PinCardResult {
  readonly card: ResultCardPayload;
}

export type SetCardPinnedPort = (
  cardId: string,
  pinned: boolean,
) => Promise<PinCardResult>;
