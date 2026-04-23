import type { ResultCardPayload } from '../../types/events';
import type {
  AudienceRenderedCard,
  AudienceRenderedCardSection,
  CardAudience,
  RenderCardForAudienceInput,
} from '../../application/cards/renderCardForAudiencePort';
import { getBackendBase } from '../../utils/backendUrl';

export interface PinCardResponse {
  readonly card: ResultCardPayload;
}

export interface RenderCardForAudienceResponse {
  readonly renderedCard: AudienceRenderedCard;
}

export interface AudienceSwitchBeaconInput {
  readonly fromAudience?: CardAudience | null;
  readonly toAudience: CardAudience;
  readonly sessionId?: string | null;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }

  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail;
  }

  return fallback;
}

export async function setCardPinned(
  cardId: string,
  pinned: boolean,
): Promise<PinCardResponse> {
  const encodedCardId = encodeURIComponent(cardId);
  const response = await fetch(`${getBackendBase()}/api/cards/${encodedCardId}/pin`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ pinned }),
  });

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Ignore non-JSON error bodies.
    }

    throw new Error(
      extractErrorMessage(payload, `Card pin request failed with status ${response.status}`),
    );
  }

  return response.json() as Promise<PinCardResponse>;
}

export async function renderCardForAudience(
  input: RenderCardForAudienceInput,
): Promise<AudienceRenderedCard> {
  const response = await fetch(`${getBackendBase()}/api/cards/render-for-audience`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      cardId: input.cardId,
      audience: input.audience,
    }),
  });

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Ignore non-JSON error bodies.
    }

    throw new Error(
      extractErrorMessage(payload, `Audience render request failed with status ${response.status}`),
    );
  }

  const payload = (await response.json()) as RenderCardForAudienceResponse;
  const renderedCard = normalizeRenderedCard(payload.renderedCard);
  if (!hasAudienceRenderedCardContent(renderedCard)) {
    throw new Error('Audience render response did not include usable content');
  }
  return renderedCard;
}

export async function reportAudienceSwitch(
  input: AudienceSwitchBeaconInput,
): Promise<void> {
  const response = await fetch(`${getBackendBase()}/api/cards/audience-switch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      fromAudience: input.fromAudience ?? null,
      toAudience: input.toAudience,
      sessionId: input.sessionId ?? null,
    }),
  });

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Ignore non-JSON error bodies.
    }

    throw new Error(
      extractErrorMessage(payload, `Audience telemetry request failed with status ${response.status}`),
    );
  }
}

export function normalizeRenderedCard(payload: unknown): AudienceRenderedCard {
  if (!payload || typeof payload !== 'object') {
    return { summary: null, body: null, sections: [] };
  }

  const raw = payload as Record<string, unknown>;
  const sections = Array.isArray(raw.sections)
    ? raw.sections
        .map((section) => normalizeSection(section))
        .filter((section): section is AudienceRenderedCardSection => section !== null)
    : [];

  return {
    summary: typeof raw.summary === 'string' && raw.summary.trim().length > 0 ? raw.summary : null,
    body: typeof raw.body === 'string' && raw.body.trim().length > 0 ? raw.body : null,
    sections,
  };
}

export function hasAudienceRenderedCardContent(
  payload: AudienceRenderedCard | null | undefined,
): payload is AudienceRenderedCard {
  if (!payload) {
    return false;
  }

  if (typeof payload.summary === 'string' && payload.summary.trim().length > 0) {
    return true;
  }

  if (typeof payload.body === 'string' && payload.body.trim().length > 0) {
    return true;
  }

  return payload.sections.length > 0;
}

function normalizeSection(payload: unknown): AudienceRenderedCardSection | null {
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  const raw = payload as Record<string, unknown>;
  const id = typeof raw.id === 'string' && raw.id.trim().length > 0 ? raw.id : null;
  const title = typeof raw.title === 'string' && raw.title.trim().length > 0 ? raw.title : null;
  const body = typeof raw.body === 'string' && raw.body.trim().length > 0 ? raw.body : null;
  if (!id || !title || !body) {
    return null;
  }
  return { id, title, body };
}
