/**
 * Splash / loading screen — shown while Python backend starts.
 */

import { Bot, Loader2, WifiOff, RefreshCw } from 'lucide-react';
import type { ConnectionStatus } from '../../hooks/useWebSocket';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  status: ConnectionStatus;
  onRetry?: () => void;
}

export function SplashScreen({ status, onRetry }: Props) {
  const { t } = useI18n();

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
      <h1 className="text-xl font-bold text-ds-text mb-1">{t('common.splash.title')}</h1>
      <p className="text-xs text-ds-muted mb-6">{t('common.splash.subtitle')}</p>

      {/* Status */}
      {status === 'connecting' && (
        <div className="flex items-center gap-2 text-sm text-ds-muted">
          <Loader2 size={14} className="animate-spin" />
          <span>{t('common.splash.starting')}</span>
        </div>
      )}

      {status === 'disconnected' && (
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm text-ds-error">{t('common.splash.disconnected')}</p>
          <p className="text-xs text-ds-muted max-w-xs text-center">
            {t('common.splash.waiting')}
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
              {t('common.splash.retry')}
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
