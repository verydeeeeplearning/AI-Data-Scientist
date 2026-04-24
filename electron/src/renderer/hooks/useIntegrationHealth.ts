import { useCallback, useState } from 'react';
import { useWs } from './WsProvider';
import { getBackendBase } from '../utils/backendUrl';

export interface ConnectorHealthView {
  system: string;
  healthy: boolean;
  message: string;
  latency_ms: number | null;
}

export interface IntegrationHealthState {
  connectors: ConnectorHealthView[];
  allHealthy: boolean | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useIntegrationHealth(): IntegrationHealthState {
  const { status } = useWs();
  const [connectors, setConnectors] = useState<ConnectorHealthView[]>([]);
  const [allHealthy, setAllHealthy] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (status !== 'connected') {
      setConnectors([]);
      setAllHealthy(null);
      setError('Not connected to backend.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${getBackendBase()}/api/integrations/health`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setConnectors(data.connectors ?? []);
      setAllHealthy(data.all_healthy ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setConnectors([]);
      setAllHealthy(null);
    } finally {
      setLoading(false);
    }
  }, [status]);

  return { connectors, allHealthy, loading, error, refresh };
}
