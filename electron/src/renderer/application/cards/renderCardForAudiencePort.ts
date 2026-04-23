import type { ResultCardType } from '../../types/events';
import type { AudienceView } from '../../domain/workspace/audienceView';

export type CardAudience = AudienceView;

export interface AudienceRenderedCardSection {
  readonly id: string;
  readonly title: string;
  readonly body: string;
}

export interface AudienceRenderedCard {
  readonly summary: string | null;
  readonly body: string | null;
  readonly sections: AudienceRenderedCardSection[];
}

export interface RenderCardForAudienceInput {
  readonly cardId: string;
  readonly audience: CardAudience;
  readonly cardType: ResultCardType;
}

export type RenderCardForAudiencePort = (
  input: RenderCardForAudienceInput,
) => Promise<AudienceRenderedCard>;
