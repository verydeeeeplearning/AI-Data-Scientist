/**
 * Chat panel ??message list + tool activity + input.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Bot } from 'lucide-react';
import { buildNavigationHash } from '../../application/navigation/resolveNavigationState';
import { buildEvidenceWorkspacePath } from '../../application/workspace/workspaceRoute';
import { useSetCardPinned } from '../../hooks/useSetCardPinned';
import { useAuthStore, type ProviderFallbackEvent } from '../../stores/authStore';
import {
  normalizeResultCardPayload,
  useChatStore,
  type ResultCardRecord,
} from '../../stores/chatStore';
import { useConfigStore } from '../../stores/configStore';
import { useWorkspaceStore } from '../../stores/workspaceStore';
import { AlertBanner } from '../workflow/AlertBanner';
import { TrustStrip } from '../trust';
import type {
  ResultCardActionId,
  ResultCardTrustSlotProps,
} from '../cards/types';
import { ChatInput } from './ChatInput';
import { ChatMessage } from './ChatMessage';
import { ToolActivity } from './ToolActivity';
import { MissionHeader } from '../mission/MissionHeader';

interface Props {
  onSend: (message: string) => void;
  onAbort: () => void;
  disabled?: boolean;
  /**
   * Visual context this panel renders in.
   * - 'default' (or omitted): full chrome — MissionHeader, AlertBanner, etc.
   * - 'floating': narrow companion (FloatingChat). Drops MissionHeader and
   *   AlertBanner because MissionContextBar already surfaces that info.
   */
  layout?: 'default' | 'floating';
}

const FALLBACK_NOTICE_TTL_MS = 5 * 60 * 1000;

export function ChatPanel({ onSend, onAbort, disabled, layout = 'default' }: Props) {
  const setCardPinned = useSetCardPinned();
  const {
    messages,
    toolActivities,
    isStreaming,
    sessionId,
    cardsById,
    cardIdsByMessageId,
  } = useChatStore();
  const upsertCards = useChatStore((state) => state.upsertCards);
  const lastFallbackEvent = useAuthStore((state) => state.lastFallbackEvent);
  const missionHeaderEnabled = useConfigStore((state) => state.missionHeaderEnabled);
  const setPinnedCardCount = useWorkspaceStore((state) => state.setPinnedCardCount);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [now, setNow] = useState(() => Date.now());
  const fallbackNotice = getActiveFallbackNotice(lastFallbackEvent, sessionId, now);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  }, [messages, toolActivities, cardIdsByMessageId]);

  useEffect(() => {
    if (!lastFallbackEvent) {
      return;
    }

    const interval = window.setInterval(() => {
      setNow(Date.now());
    }, 30_000);

    return () => {
      window.clearInterval(interval);
    };
  }, [lastFallbackEvent]);

  useEffect(() => {
    setPinnedCardCount(countPinnedCards(cardsById));
  }, [cardsById, setPinnedCardCount]);

  const navigateToPath = useCallback((path: string) => {
    const nextHash = buildNavigationHash(path);
    if (window.location.hash === nextHash) {
      return;
    }
    window.location.hash = nextHash;
  }, []);

  const handleCardAction = useCallback(
    async (action: ResultCardActionId, card: ResultCardRecord) => {
      if (action === 'pin') {
        try {
          const response = await setCardPinned(card.cardId, !card.pinned);
          const normalized = normalizeResultCardPayload(response.card, {
            messageIdFallback: card.source.messageId,
          });
          if (normalized) {
            upsertCards([normalized]);
          }
        } catch (error) {
          window.alert((error as Error)?.message ?? 'Failed to update card pin state.');
        }
        return;
      }

      const prompt = buildCardActionPrompt(action, card);
      if (prompt) {
        if (disabled || isStreaming) {
          window.alert('Wait for the current run to finish before re-running this result.');
          return;
        }
        onSend(prompt);
        return;
      }

      const path = getCardActionPath(action, card);
      if (path) {
        navigateToPath(path);
      }
    },
    [disabled, isStreaming, navigateToPath, onSend, upsertCards],
  );

  const renderTrustStrip = useCallback(
    ({ card, resultId }: ResultCardTrustSlotProps) => (
      <TrustStrip
        resultId={resultId}
        initialData={card.trustStrip ?? undefined}
        compact
        maxBadges={3}
        onNavigate={(path) => navigateToPath(path)}
      />
    ),
    [navigateToPath],
  );

  return (
    <div className="flex flex-col h-full">
      {layout !== 'floating' && <AlertBanner />}

      {fallbackNotice && <ProviderFallbackNotice event={fallbackNotice} />}

      {layout !== 'floating' && missionHeaderEnabled && sessionId && (
        <MissionHeader sessionId={sessionId} isStreaming={isStreaming} onAbort={onAbort} />
      )}

      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="divide-y divide-ds-border/50">
            {messages.map((message, index) => (
              <ChatMessage
                key={message.id}
                message={message}
                cards={getCardsForMessage(message.id, cardsById, cardIdsByMessageId)}
                isStreaming={isStreaming && index === messages.length - 1 && message.role === 'assistant'}
                onCardAction={handleCardAction}
                renderTrustStrip={renderTrustStrip}
              />
            ))}
          </div>
        )}
      </div>

      <ToolActivity activities={toolActivities} />

      <ChatInput
        onSend={onSend}
        onAbort={onAbort}
        isStreaming={isStreaming}
        disabled={disabled}
      />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-ds-muted">
      <div className="w-16 h-16 rounded-2xl bg-ds-surface flex items-center justify-center mb-4">
        <Bot size={32} className="text-ds-accent" />
      </div>
      <h2 className="text-lg font-medium text-ds-text mb-1">DS Agent</h2>
      <p className="text-sm">AI Data Scientist ready to help.</p>
      <p className="text-xs mt-2">Send a message to start a data science session.</p>
    </div>
  );
}

function getActiveFallbackNotice(
  event: ProviderFallbackEvent | null,
  sessionId: string | null,
  now: number,
): ProviderFallbackEvent | null {
  if (!event) {
    return null;
  }
  if (event.sessionId && event.sessionId !== sessionId) {
    return null;
  }
  if (now - event.occurredAt > FALLBACK_NOTICE_TTL_MS) {
    return null;
  }
  return event;
}

function ProviderFallbackNotice({ event }: { event: ProviderFallbackEvent }) {
  return (
    <div className="border-l-4 border-l-ds-accent bg-ds-accent/10 px-4 py-2">
      <div className="text-xs font-medium text-ds-text">
        Switched to a backup model for this session.
      </div>
      <div className="mt-0.5 text-[11px] text-ds-muted">
        {event.message}
      </div>
    </div>
  );
}

function getCardsForMessage(
  messageId: string,
  cardsById: Record<string, ResultCardRecord>,
  cardIdsByMessageId: Record<string, string[]>,
): ResultCardRecord[] {
  return (cardIdsByMessageId[messageId] ?? [])
    .map((cardId) => cardsById[cardId])
    .filter((card): card is ResultCardRecord => card !== undefined);
}

function countPinnedCards(cardsById: Record<string, ResultCardRecord>): number {
  return Object.values(cardsById).filter((card) => card.pinned && !card.archived).length;
}

function getCardActionPath(
  action: ResultCardActionId,
  card: ResultCardRecord,
): string | null {
  switch (action) {
    case 'export_report':
      return buildEvidenceWorkspacePath('export', {
        mode: 'detail',
        target: 'result',
        value: card.resultId,
      });
    case 'compare_run':
      return '/runs';
    case 'request_review':
      return `/governance/verifier/${encodeURIComponent(card.resultId)}`;
    case 'open_artifact':
      return buildEvidenceWorkspacePath('overview', {
        mode: 'detail',
        target: 'card',
        value: card.cardId,
      });
    default:
      return null;
  }
}

function buildCardActionPrompt(
  action: ResultCardActionId,
  card: ResultCardRecord,
): string | null {
  if (action !== 'rerun') {
    return null;
  }

  const title =
    typeof card.title === 'string' && card.title.trim().length > 0
      ? card.title.trim()
      : 'this result';

  return [
    `Re-run the analysis for ${title}.`,
    `Use run ${card.source.runId} and result ${card.resultId} as the starting reference.`,
    'Revisit the relevant data, refresh the reasoning, and emit an updated result card.',
  ].join(' ');
}
