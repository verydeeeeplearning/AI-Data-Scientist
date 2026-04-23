import type { AudienceRenderedCard } from '../../application/cards/renderCardForAudiencePort';

export type CardDisplayMode = 'expanded' | 'collapsed';

export function getNextUserExpandedOverride(
  currentUserExpanded: boolean | undefined,
  displayMode: CardDisplayMode,
): boolean {
  if (currentUserExpanded === undefined) {
    return displayMode !== 'expanded';
  }
  return !currentUserExpanded;
}

export function hasRenderedCardBodyContent(
  renderedCard: AudienceRenderedCard | null,
): renderedCard is AudienceRenderedCard {
  if (!renderedCard) {
    return false;
  }

  if (typeof renderedCard.body === 'string' && renderedCard.body.trim().length > 0) {
    return true;
  }

  return renderedCard.sections.length > 0;
}
