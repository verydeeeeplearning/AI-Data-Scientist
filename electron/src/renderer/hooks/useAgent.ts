/**
 * Agent hook — sidebar data fetching and config mutations.
 *
 * Fetches files, status, and handles model/mode changes via WS RPC.
 * Subscribes to file.created events to keep sidebar up to date.
 */

import { useCallback, useEffect } from 'react';
import { useWs } from './WsProvider';
import type { ConnectionStatus } from './useWebSocket';
import { useAgentStore } from '../stores/agentStore';
import { useChatStore } from '../stores/chatStore';
import { useFilesStore } from '../stores/filesStore';
import type { FileEntry } from '../stores/filesStore';
import type { SimpleQualityPreset } from '../utils/qualityPreset';

export function useAgent() {
  const { status, rpc, on } = useWs();

  // Extract only the action functions via selectors (stable references)
  const currentModel = useAgentStore((s) => s.model);
  const currentQualityPreset = useAgentStore((s) => s.qualityPreset);
  const updateFromStatus = useAgentStore((s) => s.updateFromStatus);
  const setMode = useAgentStore((s) => s.setMode);
  const resetConversation = useChatStore((s) => s.resetConversation);

  const setFiles = useFilesStore((s) => s.setFiles);
  const setLoading = useFilesStore((s) => s.setLoading);
  const addFileFromEvent = useFilesStore((s) => s.addFileFromEvent);
  const removeFileByPath = useFilesStore((s) => s.removeFileByPath);

  // Fetch status on connect
  useEffect(() => {
    if (status !== 'connected') return;

    rpc('status.get')
      .then((data) => updateFromStatus(data))
      .catch((err) => console.warn('[useAgent] status.get failed:', err));
  }, [status, rpc, updateFromStatus]);

  // Fetch files on connect
  useEffect(() => {
    if (status !== 'connected') return;

    setLoading(true);
    rpc('files.list', {})
      .then((data) => {
        const entries = (data.files as FileEntry[]) ?? [];
        setFiles(entries);
      })
      .catch((err) => console.warn('[useAgent] files.list failed:', err))
      .finally(() => setLoading(false));
  }, [status, rpc, setFiles, setLoading]);

  // Subscribe to file.created events
  useEffect(() => {
    return on('file.created', (payload) => {
      addFileFromEvent(
        (payload.path as string) ?? '',
        (payload.type as string) ?? '',
        (payload.size as number) ?? 0,
      );
    });
  }, [on, addFileFromEvent]);

  // Remove file from sidebar immediately when backend confirms deletion.
  useEffect(() => {
    return on('file.deleted', (payload) => {
      removeFileByPath((payload.path as string) ?? '');
    });
  }, [on, removeFileByPath]);

  // Refresh from the source of truth whenever the backend says the workspace changed.
  useEffect(() => {
    return on('workspace.changed', () => {
      void rpc('files.list', {})
        .then((data) => {
          setFiles((data.files as FileEntry[]) ?? []);
        })
        .catch((err) => console.warn('[useAgent] workspace refresh failed:', err));
    });
  }, [on, rpc, setFiles]);

  // Refresh files manually
  const refreshFiles = useCallback(async () => {
    setLoading(true);
    try {
      const data = await rpc('files.list', {});
      setFiles((data.files as FileEntry[]) ?? []);
    } finally {
      setLoading(false);
    }
  }, [rpc, setFiles, setLoading]);

  // Change model
  const changeModel = useCallback(async (model: string) => {
    if (model === currentModel) return;

    try {
      await rpc('chat.abort');
    } catch (err) {
      console.warn('[useAgent] abort before model change failed:', err);
    }
    await rpc('config.set', { path: 'provider.default_model', value: model });
    resetConversation(true);
    updateFromStatus(await rpc('status.get'));
  }, [rpc, currentModel, resetConversation, updateFromStatus]);

  const changeQualityPreset = useCallback(async (preset: SimpleQualityPreset) => {
    if (preset === currentQualityPreset) {
      return;
    }

    try {
      await rpc('chat.abort');
    } catch (err) {
      console.warn('[useAgent] abort before preset change failed:', err);
    }

    await rpc('config.set', { path: 'provider.quality_preset', value: preset });
    resetConversation(true);
    updateFromStatus(await rpc('status.get'));
  }, [rpc, currentQualityPreset, resetConversation, updateFromStatus]);

  // Change mode
  const changeMode = useCallback(async (mode: 'auto' | 'supervised' | 'step-by-step') => {
    await rpc('config.set', { path: 'agent.mode', value: mode });
    setMode(mode);
  }, [rpc, setMode]);

  // Upload file (FE-03: client-side size validation before base64 conversion)
  const MAX_UPLOAD_SIZE = 100 * 1024 * 1024; // 100MB — matches server limit

  const uploadFile = useCallback(async (file: File): Promise<string | null> => {
    if (file.size > MAX_UPLOAD_SIZE) {
      throw new Error(`File exceeds the 100 MB upload limit (${file.size} bytes).`);
    }

    const buffer = await file.arrayBuffer();
    // 4.18 fix: Chunked encoding avoids O(n²) string concatenation from reduce().
    // The reduce pattern creates a new string every iteration — O(n²) memory for
    // a 100MB file peaks at 300MB+. Chunking keeps peak usage bounded.
    const bytes = new Uint8Array(buffer);
    const chunkSize = 8192;
    let binary = '';
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
    }
    const base64 = btoa(binary);
    try {
      const result = await rpc('files.upload', { name: file.name, data: base64 });
      await refreshFiles();
      const uploadedPath = typeof result.path === 'string' ? result.path : null;
      if (!uploadedPath) {
        throw new Error('Backend did not return an uploaded path.');
      }
      return uploadedPath;
    } catch (err) {
      console.error('[useAgent] upload failed:', err);
      throw err instanceof Error ? err : new Error(String(err));
    }
  }, [rpc, refreshFiles]);

  return {
    status: status as ConnectionStatus,
    rpc,
    refreshFiles,
    changeModel,
    changeQualityPreset,
    changeMode,
    uploadFile,
  };
}
