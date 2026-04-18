/**
 * Disconnect overlay shown when the shared WebSocket drops after a session has
 * already connected at least once.
 */

import { AlertTriangle, Loader2, WifiOff } from 'lucide-react';
import type { ConnectionStatus, DisconnectReason } from '../../hooks/useWebSocket';

interface Props {
  status: ConnectionStatus;
  reason: DisconnectReason;
}

interface DisconnectCopy {
  title: string;
  description: string;
  tone: 'muted' | 'warning' | 'error';
}

const REASON_COPY: Record<DisconnectReason, DisconnectCopy> = {
  unknown: {
    title: 'Connection lost',
    description: 'Trying to restore the session.',
    tone: 'muted',
  },
  reconnecting: {
    title: 'Reconnecting...',
    description: 'Trying to reach the backend again.',
    tone: 'muted',
  },
  ws_closed: {
    title: 'Session connection closed',
    description: 'The backend is still reachable, but the WebSocket session ended. Reconnecting now.',
    tone: 'warning',
  },
  backend_crashed: {
    title: 'AI engine stopped unexpectedly',
    description: 'The backend health check is failing. Waiting for it to restart.',
    tone: 'error',
  },
  network_error: {
    title: 'Network error',
    description: 'The app lost network connectivity while trying to reach the backend.',
    tone: 'warning',
  },
};

export function DisconnectOverlay({ status, reason }: Props) {
  if (status === 'connected') return null;

  const copy = REASON_COPY[reason];
  const icon =
    reason === 'backend_crashed'
      ? <AlertTriangle size={24} className="text-ds-error mx-auto mb-3" />
      : reason === 'network_error' || reason === 'ws_closed'
        ? <WifiOff size={24} className="text-amber-400 mx-auto mb-3" />
        : <Loader2 size={24} className="text-ds-accent animate-spin mx-auto mb-3" />;
  const reasonCode = reason === 'unknown' ? 'reconnecting' : reason;
  const toneClass =
    copy.tone === 'error'
      ? 'text-ds-error'
      : copy.tone === 'warning'
        ? 'text-amber-400'
        : 'text-ds-accent';

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="disconnect-title"
      aria-describedby="disconnect-desc"
      className="fixed inset-0 z-30 bg-black/50 flex items-center justify-center pointer-events-auto"
    >
      <div className="bg-ds-surface border border-ds-border rounded-xl shadow-2xl p-6 max-w-sm text-center">
        {icon}
        <p id="disconnect-title" className="text-sm text-ds-text font-medium">{copy.title}</p>
        <p id="disconnect-desc" className="text-xs text-ds-muted mt-2 leading-5">{copy.description}</p>
        <div className={`mt-4 text-[10px] uppercase tracking-[0.25em] ${toneClass}`}>
          {reasonCode}
        </div>
      </div>
    </div>
  );
}
