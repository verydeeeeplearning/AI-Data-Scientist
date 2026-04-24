import { useCallback, useEffect, useState } from 'react';
import { useChatStore } from '../stores/chatStore';
import { translateKey } from '../stores/i18nStore';
import { resolveMainIpcErrorMessage } from '../utils/mainIpcErrors';
import { useWs } from './WsProvider';
import type { WorkObjectDetailView, WorkObjectListItemView, WorkObjectPhase } from '../types/workObject';

const WORK_OBJECT_TOOL_NAMES = new Set([
  'create_work_object',
  'get_work_object',
  'list_work_objects',
  'link_external_resource',
  'advance_work_object_phase',
  'close_work_object',
  'post_to_slack',
  'create_jira_ticket',
  'publish_confluence_page',
  'publish_notion_page',
  'open_git_pr',
]);

export function useWorkObjects(
  phaseFilter: WorkObjectPhase | 'all',
  selectedWorkObjectId: string | null,
) {
  const { status, on } = useWs();
  const sessionId = useChatStore((s) => s.sessionId);
  const [items, setItems] = useState<WorkObjectListItemView[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<WorkObjectDetailView | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!sessionId || !window.electronAPI?.workObject) {
      setItems([]);
      setError(null);
      return;
    }
    setLoading(true);
    const result = await window.electronAPI.workObject.list({
      sessionId,
      phase: phaseFilter === 'all' ? undefined : [phaseFilter],
      limit: 50,
    });
    if (!result.ok) {
      setItems([]);
      setError(resolveMainIpcErrorMessage(result, 'common.mainIpc.workObject.listFailed'));
      setLoading(false);
      return;
    }
    setItems(result.workObjects);
    setError(null);
    setLoading(false);
  }, [phaseFilter, sessionId]);

  const refreshDetail = useCallback(async () => {
    if (!selectedWorkObjectId || !window.electronAPI?.workObject) {
      setDetail(null);
      setDetailError(null);
      setDetailLoading(false);
      return;
    }
    setDetailLoading(true);
    const result = await window.electronAPI.workObject.get({
      workObjectId: selectedWorkObjectId,
      timelineLimit: 25,
    });
    if (!result.ok) {
      setDetail(null);
      setDetailError(resolveMainIpcErrorMessage(result, 'common.mainIpc.workObject.getFailed'));
      setDetailLoading(false);
      return;
    }
    setDetail(result.detail);
    setDetailError(null);
    setDetailLoading(false);
  }, [selectedWorkObjectId]);

  useEffect(() => {
    if (status === 'connected') {
      void refresh();
      return;
    }
    setItems([]);
    setError(null);
    setLoading(false);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(false);
  }, [refresh, status]);

  useEffect(() => {
    void refreshDetail();
  }, [refreshDetail]);

  useEffect(
    () =>
      on('stream.done', () => {
        void refresh();
        void refreshDetail();
      }),
    [on, refresh, refreshDetail],
  );

  useEffect(
    () =>
      on('tool.end', (payload) => {
        const name = typeof payload.name === 'string' ? payload.name : '';
        if (WORK_OBJECT_TOOL_NAMES.has(name)) {
          void refresh();
          void refreshDetail();
        }
      }),
    [on, refresh, refreshDetail],
  );

  const intake = useCallback(async (params: {
    title: string;
    taskContractId?: string;
    requestSource?: string;
    originalText?: string;
    tags?: string[];
  }) => {
    if (!window.electronAPI?.workObject) {
      throw new Error(translateKey('common.workObject.apiUnavailable'));
    }
    const result = await window.electronAPI.workObject.intake({
      ...params,
      taskContractId: params.taskContractId ?? '',
    });
    if (!result.ok) {
      throw new Error(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.workObject.createFailed'),
      );
    }
    await refresh();
    return result.result;
  }, [refresh]);

  const advance = useCallback(async (workObjectId: string, toPhase: string, runId?: string) => {
    if (!window.electronAPI?.workObject) {
      throw new Error(translateKey('common.workObject.apiUnavailable'));
    }
    const result = await window.electronAPI.workObject.advance({ workObjectId, toPhase, runId });
    if (!result.ok) {
      throw new Error(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.workObject.advanceFailed'),
      );
    }
    await refresh();
    await refreshDetail();
  }, [refresh, refreshDetail]);

  const close = useCallback(async (workObjectId: string, reason: string) => {
    if (!window.electronAPI?.workObject) {
      throw new Error(translateKey('common.workObject.apiUnavailable'));
    }
    const result = await window.electronAPI.workObject.close({ workObjectId, reason });
    if (!result.ok) {
      throw new Error(
        resolveMainIpcErrorMessage(result, 'common.mainIpc.workObject.closeFailed'),
      );
    }
    await refresh();
    await refreshDetail();
  }, [refresh, refreshDetail]);

  return {
    sessionId,
    items,
    loading,
    error,
    detail,
    detailLoading,
    detailError,
    refresh,
    intake,
    advance,
    close,
  };
}
