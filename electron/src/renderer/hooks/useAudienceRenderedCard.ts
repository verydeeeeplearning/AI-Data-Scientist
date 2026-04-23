import { useEffect, useMemo, useRef, useState } from 'react';
import {
  hasAudienceRenderedCardContent,
  renderCardForAudience,
  normalizeRenderedCard,
} from '../infrastructure/api/cardApi';
import { getCardEmphasisProfile } from '../components/cards/cardPresentation';
import { useAudienceView } from './useAudienceView';
import type { AudienceRenderedCard } from '../application/cards/renderCardForAudiencePort';
import type { ResultCardRecord } from '../stores/chatStore';

export interface UseAudienceRenderedCardResult {
  readonly renderedCard: AudienceRenderedCard | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly usesBackendRendering: boolean;
  readonly status: AudienceRenderedCardStatus;
}

export type AudienceRenderedCardStatus =
  | 'original'
  | 'loading-fallback'
  | 'rendered'
  | 'error-fallback';

export interface AudienceRenderedCardStatusInput {
  readonly renderedCard: AudienceRenderedCard | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly usesBackendRendering: boolean;
}

const renderedCardCache = new Map<string, AudienceRenderedCard>();

export function useAudienceRenderedCard(card: ResultCardRecord): UseAudienceRenderedCardResult {
  const { view: audienceView } = useAudienceView();
  const profile = getCardEmphasisProfile(card.type, audienceView);
  const usesBackendRendering = profile.summarySource === 'rendered' || profile.bodySource === 'rendered';
  const cacheKey = useMemo(() => buildCacheKey(card, audienceView), [card, audienceView]);
  const [renderedCard, setRenderedCard] = useState<AudienceRenderedCard | null>(() => {
    if (!usesBackendRendering) {
      return null;
    }
    return renderedCardCache.get(cacheKey) ?? null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(() => usesBackendRendering && !renderedCardCache.has(cacheKey));
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);

  useEffect(() => {
    if (!usesBackendRendering) {
      setRenderedCard(null);
      setIsLoading(false);
      setError(null);
      return;
    }

    const cached = renderedCardCache.get(cacheKey);
    if (cached) {
      setRenderedCard(cached);
      setIsLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    const currentVersion = ++requestVersion.current;
    setRenderedCard(null);
    setIsLoading(true);
    setError(null);

    void renderCardForAudience({
      cardId: card.cardId,
      audience: audienceView,
      cardType: card.type,
    })
      .then((result) => {
        if (cancelled || requestVersion.current !== currentVersion) {
          return;
        }
        const normalized = normalizeRenderedCard(result);
        renderedCardCache.set(cacheKey, normalized);
        setRenderedCard(normalized);
        setIsLoading(false);
      })
      .catch((err) => {
        if (cancelled || requestVersion.current !== currentVersion) {
          return;
        }
        setRenderedCard(null);
        setIsLoading(false);
        setError(err instanceof Error ? err.message : String(err));
      });

    return () => {
      cancelled = true;
    };
  }, [audienceView, cacheKey, card.cardId, card.type, usesBackendRendering]);

  const status = resolveAudienceRenderedCardStatus({
    renderedCard,
    isLoading,
    error,
    usesBackendRendering,
  });

  return {
    renderedCard,
    isLoading,
    error,
    usesBackendRendering,
    status,
  };
}

export function resolveAudienceRenderedCardStatus(
  input: AudienceRenderedCardStatusInput,
): AudienceRenderedCardStatus {
  if (!input.usesBackendRendering) {
    return 'original';
  }

  if (hasAudienceRenderedCardContent(input.renderedCard)) {
    return 'rendered';
  }

  if (input.isLoading) {
    return 'loading-fallback';
  }

  if (typeof input.error === 'string' && input.error.trim().length > 0) {
    return 'error-fallback';
  }

  return 'loading-fallback';
}

function buildCacheKey(card: ResultCardRecord, audienceView: string): string {
  return [
    card.cardId,
    card.resultId,
    card.type,
    card.createdAt,
    card.pinned ? 'pinned' : 'unpinned',
    card.archived ? 'archived' : 'active',
    card.title ?? '',
    card.body ?? '',
    JSON.stringify(card.keyMetric ?? null),
    JSON.stringify(card.primaryMetric ?? null),
    JSON.stringify(card.artifactRefs ?? null),
    getField(card, 'severity'),
    getField(card, 'category'),
    getField(card, 'target'),
    getField(card, 'impact'),
    getField(card, 'recommendation'),
    getField(card, 'artifactKind'),
    getField(card, 'fileRef'),
    getField(card, 'generatedByTool'),
    getField(card, 'sourceExperimentRunId'),
    audienceView,
  ].join('|');
}

function getField(card: ResultCardRecord, key: string): string {
  const value = card[key];
  return typeof value === 'string' ? value : '';
}
