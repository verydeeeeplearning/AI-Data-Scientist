/**
 * Chat panel — message list + tool activity + input.
 */

import { useEffect, useRef, useState } from 'react';
import { useAuthStore, type ProviderFallbackEvent } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { ChatMessage } from './ChatMessage';
import { ToolActivity } from './ToolActivity';
import { ChatInput } from './ChatInput';
import { AlertBanner } from '../workflow/AlertBanner';
import { Bot } from 'lucide-react';
import { useRuntimeStore } from '../../stores/runtimeStore';

interface Props {
  onSend: (message: string) => void;
  onAbort: () => void;
  disabled?: boolean;
}

const FALLBACK_NOTICE_TTL_MS = 5 * 60 * 1000;

export function ChatPanel({ onSend, onAbort, disabled }: Props) {
  const { messages, toolActivities, isStreaming, sessionId } = useChatStore();
  const lastFallbackEvent = useAuthStore((s) => s.lastFallbackEvent);
  const runs = useRuntimeStore((s) => s.runs);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [now, setNow] = useState(() => Date.now());
  const runningForSession = sessionId
    ? runs.some((run) => run.sessionId === sessionId && run.status === 'running')
    : false;
  const fallbackNotice = getActiveFallbackNotice(lastFallbackEvent, sessionId, now);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, toolActivities]);

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

  return (
    <div className="flex flex-col h-full">
      {/* Harness warnings */}
      <AlertBanner />

      {fallbackNotice && <ProviderFallbackNotice event={fallbackNotice} />}

      {sessionId && (
        <div className="flex items-center gap-2 border-b border-ds-border/50 bg-ds-surface/40 px-4 py-2">
          <div className="text-[10px] uppercase tracking-wider text-ds-muted">Current Session</div>
          <div className="text-xs font-mono text-ds-text truncate">{sessionId}</div>
          <span
            className={`ml-auto text-[10px] uppercase ${
              runningForSession ? 'text-ds-accent' : 'text-ds-muted'
            }`}
          >
            {runningForSession ? 'live' : 'bound'}
          </span>
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="divide-y divide-ds-border/50">
            {messages.map((msg, i) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                isStreaming={isStreaming && i === messages.length - 1 && msg.role === 'assistant'}
              />
            ))}
          </div>
        )}
      </div>

      {/* Tool Activity */}
      <ToolActivity activities={toolActivities} />

      {/* Input */}
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
