/**
 * Synchronizes project list/create surfaces with backend project RPCs.
 */

import { useCallback, useEffect, useRef } from 'react';
import { useProjectStore, type ProjectEntry } from '../stores/projectStore';
import { useVisiblePolling } from './useVisiblePolling';

type RpcFn = (
  method: string,
  params?: Record<string, unknown>
) => Promise<Record<string, unknown>>;

function normalizeProject(project: unknown): ProjectEntry | null {
  if (!project || typeof project !== 'object') {
    return null;
  }

  const raw = project as Record<string, unknown>;
  const projectId = typeof raw.id === 'string' ? raw.id : '';
  const name = typeof raw.name === 'string' ? raw.name : 'Untitled';
  if (!projectId) {
    return null;
  }

  const artifacts = Array.isArray(raw.artifacts) ? raw.artifacts : [];
  const createdAtSeconds = typeof raw.created_at === 'number' ? raw.created_at : 0;
  const updatedAtSeconds = typeof raw.updated_at === 'number' ? raw.updated_at : createdAtSeconds;

  return {
    projectId,
    name,
    description: typeof raw.description === 'string' ? raw.description : '',
    taskType: typeof raw.task_type === 'string' ? raw.task_type : null,
    artifactCount: artifacts.length,
    createdAt: createdAtSeconds * 1000,
    updatedAt: updatedAtSeconds * 1000,
  };
}

export async function fetchProjects(rpc: RpcFn): Promise<ProjectEntry[]> {
  const result = await rpc('project.list');
  const projects = Array.isArray(result.projects)
    ? result.projects.map(normalizeProject).filter((entry): entry is ProjectEntry => entry !== null)
    : [];

  return projects.sort((a, b) => {
    if (b.updatedAt !== a.updatedAt) {
      return b.updatedAt - a.updatedAt;
    }
    return a.name.localeCompare(b.name);
  });
}

export function useProjects(rpc: RpcFn, connected: boolean) {
  const setProjects = useProjectStore((s) => s.setProjects);
  const setLoading = useProjectStore((s) => s.setLoading);
  const selectProject = useProjectStore((s) => s.selectProject);
  const resetProjects = useProjectStore((s) => s.resetProjects);
  const refreshGenerationRef = useRef(0);

  const refreshProjects = useCallback(async () => {
    setLoading(true);
    try {
      const projects = await fetchProjects(rpc);
      setProjects(projects);

      const selectedProjectId = useProjectStore.getState().selectedProjectId;
      const nextSelected = selectedProjectId
        && projects.some((project) => project.projectId === selectedProjectId)
        ? selectedProjectId
        : (projects[0]?.projectId ?? null);
      selectProject(nextSelected);
    } finally {
      setLoading(false);
    }
  }, [rpc, selectProject, setLoading, setProjects]);

  useEffect(() => {
    refreshGenerationRef.current += 1;
    if (!connected) {
      resetProjects();
    }

    return () => {
      refreshGenerationRef.current += 1;
    };
  }, [connected, refreshProjects, resetProjects]);

  const guardedRefresh = useCallback(async () => {
    const generation = refreshGenerationRef.current;
    try {
      await refreshProjects();
    } catch (err) {
      if (refreshGenerationRef.current === generation) {
        console.warn('[useProjects] refresh failed:', err);
      }
    }
  }, [refreshProjects]);

  useVisiblePolling(() => {
    void guardedRefresh();
  }, { intervalMs: 15_000, enabled: connected });
}
