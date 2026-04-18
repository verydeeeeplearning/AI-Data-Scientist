/**
 * Project list and selection state for operator-facing Electron surfaces.
 */

import { create } from 'zustand';

export interface ProjectEntry {
  projectId: string;
  name: string;
  description: string;
  taskType?: string | null;
  artifactCount: number;
  createdAt: number;
  updatedAt: number;
}

const STORAGE_KEY = 'ds-agent-selected-project';

function loadSelectedProjectId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistSelectedProjectId(projectId: string | null): void {
  try {
    if (projectId) {
      localStorage.setItem(STORAGE_KEY, projectId);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {}
}

interface ProjectState {
  projects: ProjectEntry[];
  selectedProjectId: string | null;
  loading: boolean;
  creating: boolean;
  lastUpdatedAt: number | null;

  setProjects: (projects: ProjectEntry[]) => void;
  selectProject: (projectId: string | null) => void;
  setLoading: (loading: boolean) => void;
  setCreating: (creating: boolean) => void;
  resetProjects: () => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  projects: [],
  selectedProjectId: loadSelectedProjectId(),
  loading: false,
  creating: false,
  lastUpdatedAt: null,

  setProjects: (projects) => set({ projects, lastUpdatedAt: Date.now() }),
  selectProject: (projectId) => {
    persistSelectedProjectId(projectId);
    set({ selectedProjectId: projectId });
  },
  setLoading: (loading) => set({ loading }),
  setCreating: (creating) => set({ creating }),
  resetProjects: () => {
    set({
      projects: [],
      selectedProjectId: loadSelectedProjectId(),
      loading: false,
      creating: false,
      lastUpdatedAt: null,
    });
  },
}));
