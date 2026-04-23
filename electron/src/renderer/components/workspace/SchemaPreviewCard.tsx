import { useId } from 'react';
import { Badge, Card } from '../../design-system/primitives';
import type { UploadedFileSchemaPreview } from '../../domain/workspace/uploadedFile';
import { useI18n } from '../../stores/i18nStore';
import { SuggestedActions } from './SuggestedActions';

interface Props {
  preview: UploadedFileSchemaPreview;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value?: number | null): string {
  if (typeof value !== 'number') {
    return '--';
  }
  return value.toLocaleString();
}

export function SchemaPreviewCard({ preview }: Props) {
  const { t } = useI18n();
  const titleId = useId();
  const columnsTitleId = `${titleId}-columns`;
  const sampleRowsTitleId = `${titleId}-sample-rows`;
  const sampleColumns = preview.columns.slice(0, 4);
  const sampleRowColumns = Object.keys(preview.sampleRows[0] ?? {});
  const outlierSummary =
    preview.dataQuality.outlierColumns.length > 0
      ? preview.dataQuality.outlierColumns.join(', ')
      : t('workspace.upload.preview.none');
  const metrics: ReadonlyArray<{
    label: string;
    value: string;
    valueClassName?: string;
  }> = [
    {
      label: t('workspace.upload.preview.missingRatio'),
      value: formatPercent(preview.dataQuality.missingRatio),
    },
    {
      label: t('workspace.upload.preview.duplicateRatio'),
      value: formatPercent(preview.dataQuality.duplicateRowRatio),
    },
    {
      label: t('workspace.upload.preview.outliers'),
      value: outlierSummary,
      valueClassName: 'line-clamp-2',
    },
  ];

  return (
    <Card className="space-y-ds-4 bg-ds-bg/70" aria-labelledby={titleId}>
      <div className="flex items-start justify-between gap-ds-3">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
            {t('workspace.upload.preview.title')}
          </p>
          <h3 id={titleId} className="mt-ds-1 truncate text-ds-sm font-semibold text-ds-text">
            {preview.fileName}
          </h3>
          <div className="mt-ds-2 flex flex-wrap items-center gap-ds-2 text-ds-xs text-ds-muted">
            <Badge compact>{preview.format.toUpperCase()}</Badge>
            <span>
              {formatNumber(preview.rowCountEstimate)} {t('workspace.upload.preview.rows')}
            </span>
          </div>
        </div>
        {preview.suggestedTarget && (
          <Badge
            tone="accent"
            compact
            className="max-w-full shrink-0"
            title={`${t('workspace.upload.preview.target')}: ${preview.suggestedTarget.columnName}`}
          >
            {t('workspace.upload.preview.target')}: {preview.suggestedTarget.columnName}
          </Badge>
        )}
      </div>

      <dl className="grid gap-ds-2 text-ds-xs sm:grid-cols-3">
        {metrics.map((metric) => (
          <Card
            key={metric.label}
            className="border-ds-border/80 bg-ds-surface px-ds-3 py-ds-3 shadow-none"
          >
            <dt className="text-ds-muted">{metric.label}</dt>
            <dd className={`mt-ds-1 font-medium text-ds-text ${metric.valueClassName ?? ''}`}>
              {metric.value}
            </dd>
          </Card>
        ))}
      </dl>

      <section aria-labelledby={columnsTitleId}>
        <h4
          id={columnsTitleId}
          className="mb-ds-2 text-[10px] uppercase tracking-[0.18em] text-ds-muted"
        >
          {t('workspace.upload.preview.columns')}
        </h4>
        <div className="space-y-ds-2">
          {sampleColumns.map((column) => (
            <Card
              key={column.name}
              className="border-ds-border/80 bg-ds-surface px-ds-3 py-ds-3 text-ds-xs shadow-none"
            >
              <div className="flex items-center justify-between gap-ds-2">
                <span className="truncate font-medium text-ds-text">{column.name}</span>
                <Badge compact>{column.dtype}</Badge>
              </div>
              <p className="mt-ds-1 text-ds-muted">
                {t('workspace.upload.preview.nullCount')}: {formatNumber(column.nullCount)} /{' '}
                {t('workspace.upload.preview.uniqueCount')}: {formatNumber(column.uniqueCount)}
              </p>
            </Card>
          ))}
        </div>
      </section>

      {preview.sampleRows.length > 0 && (
        <section aria-labelledby={sampleRowsTitleId}>
          <h4
            id={sampleRowsTitleId}
            className="mb-ds-2 text-[10px] uppercase tracking-[0.18em] text-ds-muted"
          >
            {t('workspace.upload.preview.sampleRows')}
          </h4>
          <div className="overflow-hidden rounded-ds-xl border border-ds-border/80 bg-ds-surface">
            <div className="overflow-x-auto">
              <table className="min-w-full text-ds-xs">
                <caption className="sr-only">
                  {t('workspace.upload.preview.sampleRows')}: {preview.fileName}
                </caption>
                <thead className="bg-ds-surface-elevated/70 text-ds-muted">
                  <tr>
                    {sampleRowColumns.map((column) => (
                      <th key={column} className="px-ds-3 py-ds-2 text-left font-medium">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.sampleRows.map((row, index) => (
                    <tr
                      key={`${preview.fileId}-row-${index}`}
                      className="border-t border-ds-border/70 bg-ds-bg/20"
                    >
                      {sampleRowColumns.map((column) => (
                        <td
                          key={`${column}-${index}`}
                          className="max-w-40 truncate px-ds-3 py-ds-2 text-ds-text"
                        >
                          {String(row[column] ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      <SuggestedActions preview={preview} />
    </Card>
  );
}
