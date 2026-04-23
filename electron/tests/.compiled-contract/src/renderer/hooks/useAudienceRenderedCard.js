"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.useAudienceRenderedCard = useAudienceRenderedCard;
exports.resolveAudienceRenderedCardStatus = resolveAudienceRenderedCardStatus;
const react_1 = require("react");
const cardApi_1 = require("../infrastructure/api/cardApi");
const cardPresentation_1 = require("../components/cards/cardPresentation");
const useAudienceView_1 = require("./useAudienceView");
const renderedCardCache = new Map();
function useAudienceRenderedCard(card) {
    const { view: audienceView } = (0, useAudienceView_1.useAudienceView)();
    const profile = (0, cardPresentation_1.getCardEmphasisProfile)(card.type, audienceView);
    const usesBackendRendering = profile.summarySource === 'rendered' || profile.bodySource === 'rendered';
    const cacheKey = (0, react_1.useMemo)(() => buildCacheKey(card, audienceView), [card, audienceView]);
    const [renderedCard, setRenderedCard] = (0, react_1.useState)(() => {
        if (!usesBackendRendering) {
            return null;
        }
        return renderedCardCache.get(cacheKey) ?? null;
    });
    const [isLoading, setIsLoading] = (0, react_1.useState)(() => usesBackendRendering && !renderedCardCache.has(cacheKey));
    const [error, setError] = (0, react_1.useState)(null);
    const requestVersion = (0, react_1.useRef)(0);
    (0, react_1.useEffect)(() => {
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
        void (0, cardApi_1.renderCardForAudience)({
            cardId: card.cardId,
            audience: audienceView,
            cardType: card.type,
        })
            .then((result) => {
            if (cancelled || requestVersion.current !== currentVersion) {
                return;
            }
            const normalized = (0, cardApi_1.normalizeRenderedCard)(result);
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
function resolveAudienceRenderedCardStatus(input) {
    if (!input.usesBackendRendering) {
        return 'original';
    }
    if ((0, cardApi_1.hasAudienceRenderedCardContent)(input.renderedCard)) {
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
function buildCacheKey(card, audienceView) {
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
function getField(card, key) {
    const value = card[key];
    return typeof value === 'string' ? value : '';
}
