/**
 * FloatingChat — chat as a companion, not an area.
 *
 * Wraps the existing <ChatPanel> rather than re-implementing it. The panel
 * follows the user across every area:
 *
 *   - Collapsed: dock button bottom-right (pulses while streaming, badge for unread)
 *   - Expanded: right-anchored 420px panel
 *   - Fullscreen: edge-padded modal
 *   - Pinned: persists across area switches; Esc no longer collapses
 *
 * Hotkey: ⌘J / Ctrl+J toggles. Esc collapses (unless pinned).
 *
 * Persistence: state + pinned saved to localStorage; fullscreen never persisted.
 *
 * Unread badge: chatStore must expose `unreadCount` and `markAllRead` — see
 * chatStore.ts.patch.md for the additive change. If the patch isn't applied,
 * unread defaults to 0 (no badge).
 */

import { Maximize2, MessageSquare, Minimize2, Pin, PinOff, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ChatPanel } from './ChatPanel';
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut';
import { useChatStore } from '../../stores/chatStore';
import { useConfigStore } from '../../stores/configStore';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  onSend: (message: string) => void;
  onAbort: () => void;
  disabled?: boolean;
}

type PanelState = 'collapsed' | 'expanded' | 'fullscreen';

const LS_KEY = 'ds-agent-floating-chat-v1';

interface Persisted {
  state: Exclude<PanelState, 'fullscreen'>;
  pinned: boolean;
}

function loadPersisted(): Persisted {
  try {
    const raw = typeof window !== 'undefined' ? window.localStorage.getItem(LS_KEY) : null;
    if (!raw) return { state: 'collapsed', pinned: false };
    const parsed = JSON.parse(raw) as Partial<Persisted>;
    return {
      state: parsed.state === 'expanded' ? 'expanded' : 'collapsed',
      pinned: parsed.pinned === true,
    };
  } catch {
    return { state: 'collapsed', pinned: false };
  }
}

function savePersisted(value: Persisted) {
  try {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LS_KEY, JSON.stringify(value));
    }
  } catch {
    /* ignore */
  }
}

export function FloatingChat({ onSend, onAbort, disabled }: Props) {
  const { t } = useI18n();
  const initial = useRef<Persisted>(loadPersisted());
  const [state, setState] = useState<PanelState>(initial.current.state);
  const [pinned, setPinned] = useState<boolean>(initial.current.pinned);

  const isStreaming = useChatStore((s) => s.isStreaming);
  const unreadCount = useChatStore((s) => s.unreadCount);
  const markRead = useChatStore((s) => s.markAllRead);

  const pendingStarterPrompt = useConfigStore((s) => s.pendingStarterPrompt);

  useEffect(() => {
    if (state === 'fullscreen') return;
    savePersisted({ state, pinned });
  }, [state, pinned]);

  // Clear unread whenever the panel is visible — including the case where a
  // new assistant message lands while the user already has the panel open.
  useEffect(() => {
    if (state !== 'collapsed' && unreadCount > 0) markRead();
  }, [state, unreadCount, markRead]);

  const toggle = useCallback(() => {
    setState((s) => (s === 'collapsed' ? 'expanded' : 'collapsed'));
  }, []);
  useKeyboardShortcut('ctrl+j', toggle);
  useKeyboardShortcut('meta+j', toggle);

  // Esc collapses unless pinned (and never closes from fullscreen — that just
  // returns to expanded).
  useEffect(() => {
    if (state === 'collapsed') return;
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (state === 'fullscreen') {
        setState('expanded');
        return;
      }
      if (pinned) return;
      setState('collapsed');
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [state, pinned]);

  // Auto-open when onboarding produced a starter prompt — gives the user a
  // chance to edit before sending.
  useEffect(() => {
    if (pendingStarterPrompt && state === 'collapsed') {
      setState('expanded');
    }
  }, [pendingStarterPrompt, state]);

  if (state === 'collapsed') {
    return (
      <button
        type="button"
        aria-label={t('chat.floating.open')}
        title={`${t('chat.floating.open')} (⌘J)`}
        onClick={() => setState('expanded')}
        className="fixed bottom-4 right-4 z-40 flex h-12 w-12 items-center justify-center rounded-full border border-ds-border bg-ds-surface text-ds-text shadow-lg transition-colors hover:bg-ds-bg focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50"
      >
        <MessageSquare
          size={20}
          className={isStreaming ? 'animate-pulse text-ds-accent' : ''}
        />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-ds-accent px-1 text-[10px] font-semibold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
    );
  }

  const fullscreen = state === 'fullscreen';

  return (
    <>
      {fullscreen && (
        <div
          className="fixed inset-0 z-40 bg-black/40"
          onClick={() => setState('expanded')}
          aria-hidden
        />
      )}

      <aside
        role="complementary"
        aria-label={t('chat.floating.label')}
        className={
          fullscreen
            ? 'fixed inset-6 z-50 flex flex-col overflow-hidden rounded-xl border border-ds-border bg-ds-surface shadow-2xl'
            : 'fixed bottom-4 right-4 top-16 z-40 flex w-[420px] flex-col overflow-hidden rounded-xl border border-ds-border bg-ds-surface shadow-2xl'
        }
      >
        <div className="flex h-10 shrink-0 items-center justify-between gap-2 border-b border-ds-border px-3">
          <div className="flex items-center gap-2 text-xs font-medium text-ds-text">
            <MessageSquare
              size={14}
              className={isStreaming ? 'animate-pulse text-ds-accent' : 'text-ds-muted'}
            />
            <span>{t('chat.floating.title')}</span>
            {isStreaming && (
              <span className="rounded bg-ds-accent/10 px-1.5 py-0.5 font-mono text-[10px] text-ds-accent">
                {t('chat.floating.streaming')}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 text-ds-muted">
            <button
              type="button"
              aria-label={pinned ? t('chat.floating.unpin') : t('chat.floating.pin')}
              title={pinned ? t('chat.floating.unpin') : t('chat.floating.pin')}
              onClick={() => setPinned((v) => !v)}
              className={`rounded p-1 transition-colors hover:bg-ds-bg hover:text-ds-text focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50 ${
                pinned ? 'text-ds-accent' : ''
              }`}
            >
              {pinned ? <Pin size={14} /> : <PinOff size={14} />}
            </button>
            <button
              type="button"
              aria-label={
                fullscreen ? t('chat.floating.exitFullscreen') : t('chat.floating.fullscreen')
              }
              title={
                fullscreen ? t('chat.floating.exitFullscreen') : t('chat.floating.fullscreen')
              }
              onClick={() => setState(fullscreen ? 'expanded' : 'fullscreen')}
              className="rounded p-1 transition-colors hover:bg-ds-bg hover:text-ds-text focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50"
            >
              {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
            <button
              type="button"
              aria-label={t('chat.floating.close')}
              title={`${t('chat.floating.close')} (Esc)`}
              onClick={() => setState('collapsed')}
              className="rounded p-1 transition-colors hover:bg-ds-bg hover:text-ds-text focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/50"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-hidden">
          <ChatPanel
            onSend={onSend}
            onAbort={onAbort}
            disabled={disabled}
            // `layout` prop is added by the IA v3 patch to ChatPanel.
            // When present and === 'floating', ChatPanel drops MissionHeader
            // and the fallback banner so the narrow panel stays clean.
            layout="floating"
          />
        </div>
      </aside>
    </>
  );
}
