import type { ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import { useFilesStore } from '../../renderer/stores/filesStore';

export function ArtifactsPage(): ReactElement {
  const { t } = useTranslation('mobile');
  const fileGroups = useFilesStore((state) => state.fileGroups);
  const plotGroups = useFilesStore((state) => state.plotGroups);
  const flattenedFiles = fileGroups.flatMap((group) => group.entries).slice(0, 6);
  const flattenedPlots = plotGroups.flatMap((group) => group.entries).slice(0, 4);

  return (
    <div className="flex flex-col gap-3 p-4">
      <h1 className="text-lg font-semibold text-ds-text">
        {t('nav.artifacts')}
      </h1>
      <span className="text-xs text-ds-muted">{t('status.readOnly')}</span>
      <p className="text-sm text-ds-muted">
        {t('artifacts.description')}
      </p>

      <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ds-text">{t('artifacts.files.title')}</h2>
            <p className="mt-1 text-xs leading-5 text-ds-muted">
              {t('artifacts.files.description')}
            </p>
          </div>
          <span className="rounded-full bg-ds-surface px-2 py-1 text-[11px] text-ds-muted">
            {flattenedFiles.length}
          </span>
        </div>
        <div className="mt-4 space-y-3">
          {flattenedFiles.length === 0 ? (
            <div className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3 text-sm text-ds-muted">
              {t('artifacts.files.empty')}
            </div>
          ) : (
            flattenedFiles.map((file) => (
              <article
                key={file.path}
                className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3"
              >
                <div className="text-sm font-medium text-ds-text">{file.name}</div>
                <div className="mt-1 break-all text-xs text-ds-muted">{file.path}</div>
              </article>
            ))
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-ds-border bg-ds-surface/70 p-4">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-sm font-semibold text-ds-text">{t('artifacts.plots.title')}</h2>
          <span className="rounded-full bg-ds-surface px-2 py-1 text-[11px] text-ds-muted">
            {flattenedPlots.length}
          </span>
        </div>
        <div className="mt-4 space-y-3">
          {flattenedPlots.length === 0 ? (
            <div className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3 text-sm text-ds-muted">
              {t('artifacts.plots.empty')}
            </div>
          ) : (
            flattenedPlots.map((plot) => (
              <article
                key={plot.path}
                className="rounded-xl border border-ds-border/70 bg-ds-bg/50 p-3"
              >
                <div className="text-sm font-medium text-ds-text">{plot.name}</div>
                <div className="mt-1 break-all text-xs text-ds-muted">{plot.path}</div>
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
