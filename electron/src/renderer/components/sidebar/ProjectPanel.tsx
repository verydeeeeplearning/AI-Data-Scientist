/**
 * Project list/create/select surface for non-developer operators.
 */

import { useCallback, useMemo, useState } from 'react';
import {
  FolderKanban,
  Plus,
  RefreshCw,
  CheckCircle2,
} from 'lucide-react';
import { Badge, Button, Card, Input, Select } from '../../design-system/primitives';
import { useWs } from '../../hooks/WsProvider';
import { fetchProjects } from '../../hooks/useProjects';
import { useProjectStore } from '../../stores/projectStore';
import { useI18n } from '../../stores/i18nStore';

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
  const { t } = useI18n();
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
  const [error, setError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  const selectedProject = useMemo(
    () => projects.find((project) => project.projectId === selectedProjectId) ?? null,
    [projects, selectedProjectId],
  );

  const refreshProjects = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextProjects = await fetchProjects(rpc);
      setProjects(nextProjects);
      if (!selectedProjectId || !nextProjects.some((project) => project.projectId === selectedProjectId)) {
        selectProject(nextProjects[0]?.projectId ?? null);
      }
    } catch (err) {
      console.error('[ProjectPanel] refresh failed:', err);
      const message = err instanceof Error ? err.message : String(err);
      setError(t('sidebar.projects.errors.refreshFailed', { message }));
    } finally {
      setLoading(false);
    }
  }, [rpc, selectProject, selectedProjectId, setLoading, setProjects, t]);

  const handleCreate = useCallback(async () => {
    const name = draftName.trim();
    if (!name) {
      return;
    }

    setCreating(true);
    setCreateError(null);
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
      const message = err instanceof Error ? err.message : String(err);
      setCreateError(t('sidebar.projects.errors.createFailed', { message }));
    } finally {
      setCreating(false);
    }
  }, [draftName, draftTaskType, refreshProjects, rpc, selectProject, setCreating, t]);

  return (
    <section aria-labelledby="project-panel-title" aria-busy={loading || creating}>
      <div className="flex items-center justify-between px-3 py-1.5">
        <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-ds-muted">
          <FolderKanban size={12} aria-hidden="true" />
          <h2 id="project-panel-title" className="text-inherit">
            {t('sidebar.projects.heading')}
          </h2>
          {projects.length > 0 && (
            <Badge
              compact
              tone="accent"
              className="ml-1 min-w-[1.25rem] justify-center px-ds-2 py-0.5 normal-case shadow-none"
            >
              {projects.length}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setComposerOpen((open) => !open)}
            leadingIcon={<Plus size={12} aria-hidden="true" />}
            aria-expanded={composerOpen}
            aria-controls="project-panel-composer"
            aria-label={composerOpen ? t('sidebar.projects.hideCreateForm') : t('sidebar.projects.createProject')}
            title={t('sidebar.projects.createProject')}
            className="h-7 min-h-7 w-7 rounded-ds-md px-0 shadow-none"
          >
            <span className="sr-only">{t('sidebar.projects.createProject')}</span>
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => void refreshProjects()}
            loading={loading}
            leadingIcon={<RefreshCw size={12} aria-hidden="true" />}
            aria-label={t('sidebar.projects.refreshProjects')}
            title={t('sidebar.projects.refreshProjects')}
            className="h-7 min-h-7 w-7 rounded-ds-md px-0 shadow-none"
          >
            <span className="sr-only">{t('sidebar.projects.refreshProjects')}</span>
          </Button>
        </div>
      </div>

      {selectedProject && (
        <Card tone="accent" className="mx-3 mb-2 space-y-ds-2 px-ds-3 py-ds-3 shadow-none">
          <Badge
            compact
            tone="accent"
            leadingIcon={<CheckCircle2 size={10} aria-hidden="true" />}
            className="max-w-fit px-ds-2 py-0.5 uppercase tracking-wider shadow-none"
          >
            Selected Project
          </Badge>
          <div className="text-xs font-medium text-ds-text truncate">
            {selectedProject.name}
          </div>
          <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-ds-muted">
            <Badge compact tone="neutral" className="px-ds-2 py-0.5 normal-case shadow-none">
              {selectedProject.taskType ?? 'general'}
            </Badge>
            <Badge compact tone="neutral" className="px-ds-2 py-0.5 normal-case shadow-none">
              {selectedProject.artifactCount} artifacts
            </Badge>
            <span>{formatRelative(selectedProject.updatedAt)}</span>
          </div>
        </Card>
      )}

      {composerOpen && (
        <Card
          id="project-panel-composer"
          className="mx-3 mb-2 space-y-ds-3 border-ds-border bg-ds-bg/80 px-ds-3 py-ds-3 shadow-none"
        >
          <Input
            type="text"
            value={draftName}
            onChange={(e) => setDraftName(e.target.value)}
            placeholder="Project name"
            autoFocus
            className="text-xs"
            containerClassName="min-h-9 rounded-ds-lg px-ds-3 py-ds-1.5"
            onKeyDown={(e) => e.key === 'Enter' && void handleCreate()}
          />
          <Select
            value={draftTaskType}
            onChange={(e) => setDraftTaskType(e.target.value)}
            options={TASK_TYPE_OPTIONS}
            aria-label="Task type"
            className="min-h-9 rounded-ds-lg px-ds-3 py-ds-1.5 text-xs"
          />
          {createError ? (
            <p
              role="alert"
              className="text-ds-xs text-ds-error"
              data-testid="project-panel-create-error"
            >
              {createError}
            </p>
          ) : null}
          <Button
            type="button"
            onClick={() => void handleCreate()}
            variant="primary"
            size="sm"
            loading={creating}
            disabled={!draftName.trim()}
            className="w-full min-h-9 text-xs shadow-none"
          >
            {creating ? 'Creating...' : 'Create Project'}
          </Button>
        </Card>
      )}

      {error ? (
        <p
          role="alert"
          className="mx-3 mb-2 text-ds-xs text-ds-error"
          data-testid="project-panel-refresh-error"
        >
          {error}
        </p>
      ) : null}

      <div className="px-1">
        {projects.length === 0 ? (
          <Card
            role="status"
            aria-live="polite"
            className="mx-2 bg-ds-bg/40 px-ds-3 py-ds-3 text-[11px] text-ds-muted shadow-none"
          >
            No projects yet
          </Card>
        ) : (
          projects.map((project) => {
            const selected = project.projectId === selectedProjectId;
            return (
              <Button
                type="button"
                key={project.projectId}
                onClick={() => selectProject(project.projectId)}
                variant="secondary"
                size="sm"
                aria-pressed={selected}
                className={[
                  'mx-2 mb-1 flex w-[calc(100%-1rem)] min-h-0 flex-col items-stretch justify-start rounded-ds-xl px-ds-3 py-ds-2 text-left shadow-none',
                  selected
                    ? 'border-ds-accent/50 bg-ds-accent/10 text-ds-text hover:bg-ds-accent/10'
                    : 'border-ds-border/40 bg-transparent text-ds-text hover:border-ds-accent/30 hover:bg-ds-bg/70',
                ].join(' ')}
              >
                <span className="flex w-full items-center justify-between gap-2">
                  <span className="text-xs font-medium text-ds-text truncate">
                    {project.name}
                  </span>
                  {selected && (
                    <CheckCircle2 size={12} className="text-ds-accent flex-shrink-0" aria-hidden="true" />
                  )}
                </span>
                <span className="mt-1 flex w-full flex-wrap items-center gap-1.5 text-[10px] text-ds-muted">
                  <Badge compact tone="neutral" className="px-ds-2 py-0.5 normal-case shadow-none">
                    {project.taskType ?? 'general'}
                  </Badge>
                  <Badge compact tone="neutral" className="px-ds-2 py-0.5 normal-case shadow-none">
                    {project.artifactCount} artifacts
                  </Badge>
                  <span>{formatRelative(project.updatedAt)}</span>
                </span>
              </Button>
            );
          })
        )}
      </div>
    </section>
  );
}
