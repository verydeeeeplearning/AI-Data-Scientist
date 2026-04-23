import { Fragment, useEffect, type ReactElement, type ReactNode } from 'react';
import {
  type ConnectionStatus,
  type DisconnectReason,
} from '../renderer/hooks/useWebSocket';
import { useAgent } from '../renderer/hooks/useAgent';
import { useRuntime } from '../renderer/hooks/useRuntime';
import { WsProvider, useWs } from '../renderer/hooks/WsProvider';
import { useWorkflow } from '../renderer/hooks/useWorkflow';
import { flushQueuedMobileApprovals } from './approvals/approvalAdapter';

const DEFAULT_BACKEND_PORT = 18_790;

export interface MobileBootstrapParams {
  readonly port: number;
  readonly token?: string;
}

export interface MobileConnectionDescriptor {
  readonly tone: 'success' | 'warning' | 'danger';
  readonly labelKey: string;
  readonly detailKey: string;
}

export function parseMobileBootstrapParams(
  search: string,
  defaultPort: number = DEFAULT_BACKEND_PORT,
): MobileBootstrapParams {
  const params = new URLSearchParams(search);
  const parsedPort = Number.parseInt(params.get('port') ?? '', 10);
  const port = Number.isFinite(parsedPort) && parsedPort > 0 ? parsedPort : defaultPort;
  const token = params.get('token')?.trim() || undefined;
  return { port, token };
}

export function describeMobileConnection(
  status: ConnectionStatus,
  reason: DisconnectReason,
): MobileConnectionDescriptor {
  if (status === 'connected') {
    return {
      tone: 'success',
      labelKey: 'status.connected',
      detailKey: 'connection.detail.live',
    };
  }
  if (status === 'connecting') {
    return {
      tone: 'warning',
      labelKey: 'status.connecting',
      detailKey:
        reason === 'reconnecting'
          ? 'connection.detail.reconnecting'
          : 'connection.detail.waiting',
    };
  }
  return {
    tone: 'danger',
    labelKey: 'status.disconnected',
    detailKey:
      reason === 'network_error'
        ? 'connection.detail.network'
        : reason === 'backend_crashed'
          ? 'connection.detail.backend'
          : 'connection.detail.waiting',
  };
}

function MobileRuntimeBootstrap({
  children,
}: {
  children: ReactNode;
}): ReactElement {
  const { status, rpc, on } = useWs();

  useAgent();
  useRuntime(on, rpc, status === 'connected');
  useWorkflow(on, rpc, status === 'connected');

  useEffect(() => {
    if (status !== 'connected') {
      return;
    }
    void flushQueuedMobileApprovals(rpc).catch(() => undefined);
  }, [rpc, status]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const handleOnline = (): void => {
      if (status !== 'connected') {
        return;
      }
      void flushQueuedMobileApprovals(rpc).catch(() => undefined);
    };

    const handleServiceWorkerMessage = (event: MessageEvent): void => {
      const payload = event.data;
      if (!payload || typeof payload !== 'object') {
        return;
      }
      if ((payload as { type?: string }).type !== 'ds-agent-outbox-flush') {
        return;
      }
      if (status !== 'connected') {
        return;
      }
      void flushQueuedMobileApprovals(rpc).catch(() => undefined);
    };

    window.addEventListener('online', handleOnline);
    navigator.serviceWorker?.addEventListener('message', handleServiceWorkerMessage as EventListener);
    return () => {
      window.removeEventListener('online', handleOnline);
      navigator.serviceWorker?.removeEventListener(
        'message',
        handleServiceWorkerMessage as EventListener,
      );
    };
  }, [rpc, status]);

  return <Fragment>{children}</Fragment>;
}

export function MobileRuntimeProvider({
  children,
  search,
}: {
  children: ReactNode;
  search?: string;
}): ReactElement {
  const params = parseMobileBootstrapParams(
    search ?? (typeof window === 'undefined' ? '' : window.location.search),
  );

  return (
    <WsProvider port={params.port} token={params.token}>
      <MobileRuntimeBootstrap>{children}</MobileRuntimeBootstrap>
    </WsProvider>
  );
}

export const __test = {
  describeMobileConnection,
  parseMobileBootstrapParams,
};
