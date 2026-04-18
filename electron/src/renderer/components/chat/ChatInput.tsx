/**
 * Chat input field with send/abort controls.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Send, StopCircle } from 'lucide-react';
import { useConfigStore } from '../../stores/configStore';

interface Props {
  onSend: (message: string) => void;
  onAbort: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export function ChatInput({ onSend, onAbort, isStreaming, disabled }: Props) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const consumePendingStarterPrompt = useConfigStore((s) => s.consumePendingStarterPrompt);

  // One-shot pickup: when the onboarding wizard finishes it stages a starter
  // prompt; the very first ChatInput mount after that pulls it in and clears
  // the slot so it does not refire on remount or hot reload.
  useEffect(() => {
    const pending = consumePendingStarterPrompt();
    if (!pending) return;
    setText(pending);
    requestAnimationFrame(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
      el.focus();
      el.setSelectionRange(pending.length, pending.length);
    });
  }, [consumePendingStarterPrompt]);

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;

    onSend(trimmed);
    setText('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [text, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // Ctrl/Cmd + Enter to send
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        handleSend();
        return;
      }
      // Enter without shift to send (single line behavior)
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // Auto-resize textarea
  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  return (
    <div className="border-t border-ds-border bg-ds-surface px-4 py-3">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Send a message... (Enter to send, Shift+Enter for newline)"
          disabled={disabled}
          rows={1}
          aria-label="Chat message input"
          role="textbox"
          className="
            flex-1 bg-ds-bg border border-ds-border rounded-lg px-3 py-2
            text-sm text-ds-text placeholder:text-ds-muted
            focus:outline-none focus:border-ds-accent
            resize-none min-h-[38px] max-h-[200px]
            disabled:opacity-50
          "
        />

        {isStreaming ? (
          <button
            onClick={onAbort}
            className="
              flex-shrink-0 p-2 rounded-lg
              bg-ds-error/20 text-ds-error
              hover:bg-ds-error/30 transition-colors
            "
            title="Stop (Ctrl+C)"
          >
            <StopCircle size={18} />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!text.trim() || disabled}
            className="
              flex-shrink-0 p-2 rounded-lg
              bg-ds-accent text-white
              hover:bg-ds-accent-hover transition-colors
              disabled:opacity-30 disabled:cursor-not-allowed
            "
            title="Send (Enter)"
          >
            <Send size={18} />
          </button>
        )}
      </div>
    </div>
  );
}
