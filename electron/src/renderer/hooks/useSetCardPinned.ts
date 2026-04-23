/**
 * Composition hook that binds the SetCardPinned port to the HTTP adapter.
 *
 * Components in `components/` are forbidden from importing infrastructure
 * directly (lint:arch). They consume the port via this hook so the
 * adapter/port wiring lives in the renderer hooks layer, which is allowed
 * to bridge application <-> infrastructure.
 */

import type { SetCardPinnedPort } from '../application/cards/setCardPinnedPort';
import { setCardPinned } from '../infrastructure/api/cardApi';

const portInstance: SetCardPinnedPort = (cardId, pinned) => setCardPinned(cardId, pinned);

export function useSetCardPinned(): SetCardPinnedPort {
  return portInstance;
}
