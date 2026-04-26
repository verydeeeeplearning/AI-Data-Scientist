/**
 * Agent hook — sidebar data fetching and config mutations.
 *
 * Fetches files, status, and handles model/mode changes via WS RPC.
 * Subscribes to file.created events to keep sidebar up to date.
 */

import { useCallback, useEffect } from 'react';
import { useWs } from './WsProvider';
import { uploadFileWithPreview } from '../application/workspace/uploadFile';
import type { UploadedFileResult } from '../domain/workspace/uploadedFile';
import { uploadWorkspaceFile } from '../infrastructure/workspace/uploadApi';
import type { ConnectionStatus } from './useWebSocket';
import { useAgentStore } from '../stores/agentStore';
import { useChatStore } from '../stores/chatStore';
import { useConfigStore } from '../stores/configStore';
import { useFilesStore } from '../stores/filesStore';
import type { FileEntry } from '../stores/filesStore';
import { getCurrentLocale, setLocale, type Locale } from '../stores/i18nStore';
import type { SimpleQualityPreset } from '../utils/qualityPreset';

export function useAgent() {
  const { status, rpc, on } = useWs();

  // Extract only the action functions via selectors (stable references)
  const currentModel = useAgentStore((s) => s.model);
  const currentQualityPreset = useAgentStore((s) => s.qualityPreset);
  const updateFromStatus = useAgentStore((s) => s.updateFromStatus);
  const setMode = useAgentStore((s) => s.setMode);
  const setMaxBudget = useConfigStore((s) => s.setMaxBudget);
  const resetConversation = useChatStore((s) => s.resetConversation);

  const setFiles = useFilesStore((s) => s.setFiles);
  const setLoading = useFilesStore((s) => s.setLoading);
  const addFileFromEvent = useFilesStore((s) => s.addFileFromEvent);
  const removeFileByPath = useFilesStore((s) => s.removeFileByPath);

  // Fetch status on connect
  useEffect(() => {
    if (status !== 'connected') return;

    let cancelled = false;
    rpc('status.get')
      .then((data) => {
        if (!cancelled) {
          updateFromStatus(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn('[useAgent] status.get failed:', err);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [status, rpc, updateFromStatus]);

  // Fetch files on connect
  useEffect(() => {
    if (status !== 'connected') return;

    let cancelled = false;
    setLoading(true);
    rpc('files.list', {})
      .then((data) => {
        if (cancelled) {
          return;
        }
        const entries = (data.files as FileEntry[]) ?? [];
        setFiles(entries);
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn('[useAgent] files.list failed:', err);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
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
    let cancelled = false;
    const unsubscribe = on('workspace.changed', () => {
      void rpc('files.list', {})
        .then((data) => {
          if (!cancelled) {
            setFiles((data.files as FileEntry[]) ?? []);
          }
        })
        .catch((err) => {
          if (!cancelled) {
            console.warn('[useAgent] workspace refresh failed:', err);
          }
        });
    });
    return () => {
      cancelled = true;
      unsubscribe();
    };
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

  const changeMaxBudget = useCallback(async (value: number, previousValue?: number) => {
    const previous = previousValue ?? useConfigStore.getState().maxBudgetUsd;
    setMaxBudget(value);
    try {
      await rpc('config.set', { path: 'provider.max_budget_usd', value });
    } catch (err) {
      setMaxBudget(previous);
      throw err;
    }
  }, [rpc, setMaxBudget]);

  const changeLanguage = useCallback(async (next: Locale) => {
    const previous = getCurrentLocale();
    setLocale(next);
    try {
      await rpc('config.set', { path: 'agent.language', value: next });
    } catch (err) {
      console.warn('[useAgent] failed to sync agent.language:', err);
      setLocale(previous);
      throw err;
    }
  }, [rpc]);

  // Upload file (FE-03: client-side size validation before base64 conversion)
  const MAX_UPLOAD_SIZE = 100 * 1024 * 1024; // 100MB — matches server limit

  const uploadFile = useCallback(async (file: File): Promise<UploadedFileResult> => {
    if (file.size > MAX_UPLOAD_SIZE) {
      throw new Error(`File exceeds the 100 MB upload limit (${file.size} bytes).`);
    }

    try {
      const result = await uploadFileWithPreview(file, uploadWorkspaceFile);
      await refreshFiles();
      if (!result.workspacePath) {
        throw new Error('Backend did not return an uploaded path.');
      }
      return result;
    } catch (err) {
      console.error('[useAgent] upload failed:', err);
      throw err instanceof Error ? err : new Error(String(err));
    }
  }, [refreshFiles]);

  return {
    status: status as ConnectionStatus,
    rpc,
    refreshFiles,
    changeModel,
    changeQualityPreset,
    changeMode,
    changeMaxBudget,
    changeLanguage,
    uploadFile,
  };
}
