/**
 * Splash / loading screen — shown while Python backend starts.
 */

import { Bot, Loader2, WifiOff, RefreshCw } from 'lucide-react';
import type { ConnectionStatus } from '../../hooks/useWebSocket';

interface Props {
  status: ConnectionStatus;
  onRetry?: () => void;
}

export function SplashScreen({ status, onRetry }: Props) {
  return (
    <div className="fixed inset-0 z-50 bg-ds-bg flex flex-col items-center justify-center">
      {/* Animated logo */}
      <div className="relative mb-8">
        <div className="w-20 h-20 rounded-2xl bg-ds-accent/10 flex items-center justify-center">
          <Bot size={40} className="text-ds-accent" />
        </div>
        {status === 'connecting' && (
          <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-ds-surface border-2 border-ds-bg flex items-center justify-center">
            <Loader2 size={12} className="text-ds-accent animate-spin" />
          </div>
        )}
        {status === 'disconnected' && (
          <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-ds-surface border-2 border-ds-bg flex items-center justify-center">
            <WifiOff size={12} className="text-ds-error" />
          </div>
        )}
      </div>

      {/* Title */}
      <h1 className="text-xl font-bold text-ds-text mb-1">DS Agent</h1>
      <p className="text-xs text-ds-muted mb-6">AI Data Scientist</p>

      {/* Status */}
      {status === 'connecting' && (
        <div className="flex items-center gap-2 text-sm text-ds-muted">
          <Loader2 size={14} className="animate-spin" />
          <span>Starting backend...</span>
        </div>
      )}

      {status === 'disconnected' && (
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm text-ds-error">Unable to connect to backend</p>
          <p className="text-xs text-ds-muted max-w-xs text-center">
            Make sure the Python backend is running, or wait for it to start automatically.
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="
                flex items-center gap-2 px-4 py-2 rounded-lg text-sm
                bg-ds-accent text-white hover:bg-ds-accent-hover transition-colors
              "
            >
              <RefreshCw size={14} />
              Retry
            </button>
          )}
        </div>
      )}

      {/* Version */}
      <div className="absolute bottom-4 text-[10px] text-ds-muted/40">
        v0.1.0
      </div>
    </div>
  );
}
