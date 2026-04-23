import { useEffect, useRef } from 'react';

import { matchesShortcut } from '../utils/keyboardShortcut';

export function useKeyboardShortcut(
  shortcut: string,
  handler: () => void,
  enabled = true,
): void {
  const handlerRef = useRef(handler);

  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!matchesShortcut(event, shortcut)) {
        return;
      }

      event.preventDefault();
      handlerRef.current();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [enabled, shortcut]);
}
