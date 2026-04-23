import { useId } from 'react';
import { AlertCircle, RotateCw, X } from 'lucide-react';
import { Badge, Button, Card } from '../../design-system/primitives';
import { joinIds } from '../../design-system/primitives/utils';
import type { UploadErrorInfo } from '../../domain/workspace/globalDropOverlay';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  error: UploadErrorInfo;
  supportedFormats?: readonly string[];
  uploadLimit?: string;
  onRetry?: (() => void) | null;
  onDismiss?: () => void;
}

const DEFAULT_FORMATS = ['CSV', 'TSV', 'Excel', 'Parquet', 'JSON', 'JSONL'];

export function UploadErrorState({
  error,
  supportedFormats = DEFAULT_FORMATS,
  uploadLimit = '100 MB',
  onRetry,
  onDismiss,
}: Props) {
  const { t } = useI18n();
  const titleId = useId();
  const descriptionId = `${titleId}-description`;
  const detailId = `${titleId}-detail`;
  const formatsId = `${titleId}-formats`;
  const titleKey =
    error.kind === 'network'
      ? 'workspace.uploadError.network.title'
      : error.kind === 'tooLarge'
        ? 'workspace.uploadError.tooLarge.title'
        : error.kind === 'unsupported'
          ? 'workspace.uploadError.unsupported.title'
          : error.kind === 'malformed'
            ? 'workspace.uploadError.malformed.title'
            : 'workspace.uploadError.unknown.title';

  const descriptionKey =
    error.kind === 'network'
      ? 'workspace.uploadError.network.description'
      : error.kind === 'tooLarge'
        ? 'workspace.uploadError.tooLarge.description'
        : error.kind === 'unsupported'
          ? 'workspace.uploadError.unsupported.description'
          : error.kind === 'malformed'
            ? 'workspace.uploadError.malformed.description'
            : null;

  const description = descriptionKey
    ? t(descriptionKey, { limit: uploadLimit })
    : error.message;
  const describedBy = joinIds(
    descriptionId,
    descriptionKey && error.message ? detailId : undefined,
    error.kind === 'unsupported' ? formatsId : undefined,
  );

  return (
    <Card
      tone="danger"
      role="alert"
      aria-live="assertive"
      aria-labelledby={titleId}
      aria-describedby={describedBy}
      className="bg-ds-error/10 p-ds-4"
    >
      <div className="flex items-start gap-ds-3">
        <div className="mt-0.5 rounded-ds-pill bg-ds-error/10 p-ds-2 text-ds-error">
          <AlertCircle size={16} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1 space-y-ds-2">
          <div className="flex flex-wrap items-center gap-ds-2">
            <h3 id={titleId} className="text-ds-sm font-semibold text-ds-text">
              {t(titleKey)}
            </h3>
            {error.fileName && (
              <Badge compact title={error.fileName}>
                {error.fileName}
              </Badge>
            )}
          </div>
          <div id={descriptionId} className="text-ds-xs leading-5 text-ds-muted">
            {description}
          </div>
          {descriptionKey && error.message && (
            <div id={detailId} className="text-[10px] text-ds-muted opacity-80">
              {error.message}
            </div>
          )}
          {error.kind === 'unsupported' && (
            <div id={formatsId} className="pt-ds-1 text-[10px] text-ds-muted">
              {t('workspace.uploadError.supportedFormats', {
                formats: supportedFormats.join(', '),
              })}
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-ds-1">
          {onRetry && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onRetry}
              aria-label={t('workspace.uploadError.retry')}
              leadingIcon={<RotateCw size={12} aria-hidden="true" />}
              className="shadow-none"
            >
              <span>{t('workspace.uploadError.retry')}</span>
            </Button>
          )}
          {onDismiss && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onDismiss}
              aria-label={t('workspace.uploadError.dismiss')}
              leadingIcon={<X size={12} aria-hidden="true" />}
              className="min-h-8 w-8 px-0 shadow-none"
            >
              <span className="sr-only">{t('workspace.uploadError.dismiss')}</span>
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
