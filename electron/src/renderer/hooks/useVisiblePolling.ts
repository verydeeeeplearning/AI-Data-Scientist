import { useEffect, useRef } from 'react';

export interface VisiblePollingOptions {
  intervalMs: number;
  enabled: boolean;
  fireOnVisible?: boolean;
}

export function useVisiblePolling(
  callback: () => void,
  options: VisiblePollingOptions,
): void {
  const { intervalMs, enabled, fireOnVisible = true } = options;
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let timer: number | null = null;

    const stop = () => {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    };

    const start = () => {
      if (timer !== null) {
        return;
      }
      if (fireOnVisible) {
        callbackRef.current();
      }
      timer = window.setInterval(() => {
        callbackRef.current();
      }, intervalMs);
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        stop();
        return;
      }
      start();
    };

    if (!document.hidden) {
      start();
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      stop();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [enabled, fireOnVisible, intervalMs]);
}
