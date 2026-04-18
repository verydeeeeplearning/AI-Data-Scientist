/**
 * Project list/create/select surface for non-developer operators.
 */

import { useCallback, useMemo, useState } from 'react';
import {
  FolderKanban,
  Plus,
  RefreshCw,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { useWs } from '../../hooks/WsProvider';
import { fetchProjects } from '../../hooks/useProjects';
import { useProjectStore } from '../../stores/projectStore';

const TASK_TYPE_OPTIONS = [
  { value: '', label: 'General' },
  { value: 'classification', label: 'Classification' },
  { value: 'regression', label: 'Regression' },
  { value: 'forecasting', label: 'Forecasting' },
  { value: 'analysis', label: 'Analysis' },
];

function formatRelative(ms: number): string {
  const diff = Date.now() - ms;
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

export function ProjectPanel() {
  const { rpc } = useWs();
  const projects = useProjectStore((s) => s.projects);
  const selectedProjectId = useProjectStore((s) => s.selectedProjectId);
  const selectProject = useProjectStore((s) => s.selectProject);
  const loading = useProjectStore((s) => s.loading);
  const creating = useProjectStore((s) => s.creating);
  const setProjects = useProjectStore((s) => s.setProjects);
  const setLoading = useProjectStore((s) => s.setLoading);
  const setCreating = useProjectStore((s) => s.setCreating);
  const [draftName, setDraftName] = useState('');
  const [draftTaskType, setDraftTaskType] = useState('');
  const [composerOpen, setComposerOpen] = useState(false);

  const selectedProject = useMemo(
    () => projects.find((project) => project.projectId === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  const refreshProjects = useCallback(async () => {
    setLoading(true);
    try {
      const nextProjects = await fetchProjects(rpc);
      setProjects(nextProjects);
      if (!selectedProjectId || !nextProjects.some((project) => project.projectId === selectedProjectId)) {
        selectProject(nextProjects[0]?.projectId ?? null);
      }
    } finally {
      setLoading(false);
    }
  }, [rpc, selectProject, selectedProjectId, setLoading, setProjects]);

  const handleCreate = useCallback(async () => {
    const name = draftName.trim();
    if (!name) {
      return;
    }

    setCreating(true);
    try {
      const result = await rpc('project.create', {
        name,
        taskType: draftTaskType || undefined,
      });
      await refreshProjects();
      selectProject((result.projectId as string) ?? null);
      setDraftName('');
      setDraftTaskType('');
      setComposerOpen(false);
    } catch (err) {
      console.error('[ProjectPanel] create failed:', err);
    } finally {
      setCreating(false);
    }
  }, [draftName, draftTaskType, refreshProjects, rpc, selectProject, setCreating]);

  return (
    <div>
      <div className="flex items-center justify-between px-3 py-1.5">
        <div className="flex items-center gap-1.5 text-xs font-medium text-ds-muted uppercase tracking-wider">
          <FolderKanban size={12} />
          Projects
          {projects.length > 0 && (
            <span className="ml-1 bg-ds-accent/20 text-ds-accent text-[10px] px-1.5 rounded-full">
              {projects.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setComposerOpen((open) => !open)}
            className="p-0.5 rounded hover:bg-ds-bg text-ds-muted hover:text-ds-text transition-colors"
            title="Create project"
          >
            <Plus size={12} />
          </button>
          <button
            onClick={() => void refreshProjects()}
            disabled={loading}
            className="p-0.5 rounded hover:bg-ds-bg text-ds-muted hover:text-ds-text transition-colors"
            title="Refresh projects"
          >
            {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          </button>
        </div>
      </div>

      {selectedProject && (
        <div className="mx-3 mb-2 rounded-lg border border-ds-accent/30 bg-ds-accent/5 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-ds-accent">
            <CheckCircle2 size={11} />
            Selected Project
          </div>
          <div className="mt-1 text-xs font-medium text-ds-text truncate">
            {selectedProject.name}
          </div>
          <div className="mt-1 flex items-center gap-2 text-[10px] text-ds-muted">
            <span>{selectedProject.taskType ?? 'general'}</span>
            <span>{selectedProject.artifactCount} artifacts</span>
            <span>{formatRelative(selectedProject.updatedAt)}</span>
          </div>
        </div>
      )}

      {composerOpen && (
        <div className="mx-3 mb-2 rounded-lg border border-ds-border bg-ds-bg px-3 py-3 space-y-2">
          <input
            type="text"
            value={draftName}
            onChange={(e) => setDraftName(e.target.value)}
            placeholder="Project name"
            className="
              w-full bg-ds-surface border border-ds-border rounded px-3 py-1.5
              text-xs text-ds-text
              focus:outline-none focus:border-ds-accent
            "
            onKeyDown={(e) => e.key === 'Enter' && void handleCreate()}
          />
          <select
            value={draftTaskType}
            onChange={(e) => setDraftTaskType(e.target.value)}
            className="
              w-full bg-ds-surface border border-ds-border rounded px-3 py-1.5
              text-xs text-ds-text
              focus:outline-none focus:border-ds-accent
            "
          >
            {TASK_TYPE_OPTIONS.map((option) => (
              <option key={option.label} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            onClick={() => void handleCreate()}
            disabled={!draftName.trim() || creating}
            className="
              w-full px-3 py-1.5 rounded text-xs font-medium
              bg-ds-accent text-white hover:bg-ds-accent-hover
              disabled:opacity-40 transition-colors
            "
          >
            {creating ? 'Creating...' : 'Create Project'}
          </button>
        </div>
      )}

      <div className="px-1">
        {projects.length === 0 ? (
          <div className="px-3 py-2 text-[11px] text-ds-muted/60">
            No projects yet
          </div>
        ) : (
          projects.map((project) => {
            const selected = project.projectId === selectedProjectId;
            return (
              <button
                key={project.projectId}
                onClick={() => selectProject(project.projectId)}
                className={`
                  w-full text-left mx-2 mb-1 rounded-lg border px-3 py-2 transition-colors
                  ${selected
                    ? 'border-ds-accent/50 bg-ds-accent/10'
                    : 'border-ds-border/40 hover:border-ds-accent/30 hover:bg-ds-bg'}
                `}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-ds-text truncate">
                    {project.name}
                  </span>
                  {selected && <CheckCircle2 size={12} className="text-ds-accent flex-shrink-0" />}
                </div>
                <div className="mt-1 flex items-center gap-2 text-[10px] text-ds-muted">
                  <span>{project.taskType ?? 'general'}</span>
                  <span>{project.artifactCount} artifacts</span>
                  <span>{formatRelative(project.updatedAt)}</span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
