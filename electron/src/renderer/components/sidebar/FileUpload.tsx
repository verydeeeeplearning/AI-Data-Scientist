/**
 * File upload drag-and-drop with format guidance and explicit validation states.
 */

import {
  useCallback,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { AlertCircle, Loader2, Upload } from 'lucide-react';
import { announce } from '../../application/a11y/ariaLive';
import { classifyUploadError } from '../../application/workspace/classifyUploadError';
import { Badge, Card, cn } from '../../design-system/primitives';
import type { UploadErrorInfo } from '../../domain/workspace/globalDropOverlay';
import type { UploadedFileResult, UploadedFileSchemaPreview } from '../../domain/workspace/uploadedFile';
import { useI18n } from '../../stores/i18nStore';
import { SchemaPreviewCard } from '../workspace/SchemaPreviewCard';
import { UploadErrorState } from '../workspace/UploadErrorState';

interface Props {
  onUpload: (file: File) => Promise<UploadedFileResult>;
}

type ValidationError =
  | { key: 'sidebar.exceedsLimit'; vars: { size: string } }
  | { key: 'sidebar.unsupportedType'; vars: { ext: string } };

const MAX_UPLOAD_SIZE = 100 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [
  '.csv',
  '.tsv',
  '.xlsx',
  '.xls',
  '.parquet',
  '.pq',
  '.json',
  '.txt',
  '.md',
  '.py',
  '.yaml',
  '.yml',
  '.toml',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.svg',
  '.webp',
].join(',');
const SUPPORTED_FORMATS = ['CSV', 'TSV', 'Excel', 'Parquet', 'JSON'];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFile(file: File): ValidationError | null {
  if (file.size > MAX_UPLOAD_SIZE) {
    return { key: 'sidebar.exceedsLimit', vars: { size: formatSize(file.size) } };
  }

  const ext = file.name.includes('.') ? `.${file.name.split('.').pop()?.toLowerCase() ?? ''}` : '';
  if (!ACCEPTED_EXTENSIONS.split(',').includes(ext)) {
    return { key: 'sidebar.unsupportedType', vars: { ext: ext || 'unknown' } };
  }

  return null;
}

export function FileUpload({ onUpload }: Props) {
  const { t } = useI18n();
  const cardId = useId().replace(/:/g, '');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ tone: 'error' | 'success'; text: string } | null>(null);
  const [oversizedFile, setOversizedFile] = useState<{ name: string; size: number } | null>(null);
  const [preview, setPreview] = useState<UploadedFileSchemaPreview | null>(null);
  const [richError, setRichError] = useState<UploadErrorInfo | null>(null);
  const [lastFiles, setLastFiles] = useState<File[] | null>(null);

  const processFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) {
        return;
      }

      setMessage(null);
      setOversizedFile(null);
      setPreview(null);
      setRichError(null);
      setLastFiles(files);

      const validFiles: File[] = [];
      const errors: string[] = [];
      let firstValidationError: UploadErrorInfo | null = null;

      for (const file of files) {
        const error = validateFile(file);
        if (error) {
          errors.push(`${file.name}: ${t(error.key, error.vars)}`);
          if (file.size > MAX_UPLOAD_SIZE) {
            setOversizedFile({ name: file.name, size: file.size });
            firstValidationError ??= {
              kind: 'tooLarge',
              message: t(error.key, error.vars),
              fileName: file.name,
            };
          } else {
            firstValidationError ??= {
              kind: 'unsupported',
              message: t(error.key, error.vars),
              fileName: file.name,
            };
          }
          continue;
        }
        validFiles.push(file);
      }

      if (validFiles.length === 0) {
        setMessage({ tone: 'error', text: errors[0] ?? t('sidebar.uploadFailed') });
        if (firstValidationError) {
          setRichError(firstValidationError);
          announce(firstValidationError.message, { politeness: 'assertive' });
        }
        return;
      }

      setUploading(true);
      const uploaded: string[] = [];
      const uploadErrors: string[] = [...errors];
      let firstRuntimeError: UploadErrorInfo | null = firstValidationError;
      try {
        for (const file of validFiles) {
          try {
            const result = await onUpload(file);
            uploaded.push(file.name);
            if (result.preview) {
              setPreview(result.preview);
              announce(
                t('workspace.upload.preview.announced', {
                  name: result.preview.fileName,
                }),
              );
            }
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            uploadErrors.push(`${file.name}: ${message}`);
            firstRuntimeError ??= classifyUploadError(error, { fileName: file.name });
          }
        }
      } finally {
        setUploading(false);
      }

      if (uploaded.length > 0 && uploadErrors.length === 0) {
        setMessage({
          tone: 'success',
          text:
            uploaded.length === 1
              ? t('sidebar.uploaded', { name: uploaded[0] })
              : t('sidebar.uploadedCount', { count: uploaded.length }),
        });
        return;
      }

      if (uploaded.length > 0) {
        setMessage({
          tone: 'error',
          text: t('sidebar.partialUpload', {
            count: uploaded.length,
            message: uploadErrors[0] ?? '',
          }),
        });
        if (firstRuntimeError) {
          setRichError(firstRuntimeError);
        }
        return;
      }

      setMessage({ tone: 'error', text: uploadErrors[0] ?? t('sidebar.uploadFailed') });
      if (firstRuntimeError) {
        setRichError(firstRuntimeError);
        announce(firstRuntimeError.message, { politeness: 'assertive' });
      }
    },
    [onUpload, t],
  );

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      await processFiles(Array.from(e.dataTransfer.files));
    },
    [processFiles],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragging(false);
  }, []);

  const handleBrowse = useCallback(() => {
    if (uploading) {
      return;
    }
    fileInputRef.current?.click();
  }, [uploading]);

  const handleInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      void processFiles(Array.from(event.target.files ?? []));
      event.target.value = '';
    },
    [processFiles],
  );

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        handleBrowse();
      }
    },
    [handleBrowse],
  );

  return (
    <div className="space-y-2 px-3 py-1.5">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ACCEPTED_EXTENSIONS}
        onChange={handleInputChange}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
      />

      <Card
        role="button"
        tabIndex={uploading ? -1 : 0}
        aria-busy={uploading}
        aria-disabled={uploading}
        aria-label={dragging ? t('sidebar.dropToImport') : t('sidebar.importFiles')}
        aria-describedby={`${cardId}-hint`}
        onDrop={(e) => void handleDrop(e)}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleBrowse}
        onKeyDown={handleKeyDown}
        className={cn(
          'cursor-pointer border-dashed px-ds-4 py-ds-4 text-center shadow-none transition-colors',
          dragging
            ? 'border-ds-accent bg-ds-accent/10'
            : 'border-ds-border bg-ds-bg/40 hover:border-ds-muted hover:bg-ds-bg/70',
          uploading && 'pointer-events-none opacity-60',
        )}
      >
        <div className="flex flex-col items-center justify-center gap-1">
          {uploading ? (
            <Loader2 size={16} className="animate-spin text-ds-accent" aria-hidden="true" />
          ) : (
            <Upload size={16} className="text-ds-muted" aria-hidden="true" />
          )}
          <span className="text-center text-[11px] font-medium text-ds-text">
            {dragging ? t('sidebar.dropToImport') : t('sidebar.importFiles')}
          </span>
          <span id={`${cardId}-hint`} className="text-center text-[10px] text-ds-muted">
            {t('sidebar.supportsUpTo')}
          </span>
        </div>
      </Card>

      <div className="flex flex-wrap gap-1">
        {SUPPORTED_FORMATS.map((format) => (
          <Badge
            key={format}
            compact
            tone="neutral"
            className="px-ds-2 py-0.5 text-[10px] shadow-none"
          >
            {format}
          </Badge>
        ))}
      </div>

      {message && (
        <Card
          tone={message.tone === 'error' ? 'danger' : 'default'}
          role="status"
          aria-live={message.tone === 'error' ? 'assertive' : 'polite'}
          className={cn(
            'px-ds-3 py-ds-2 text-[11px] shadow-none',
            message.tone === 'success' && 'border-ds-success/40 bg-ds-success/10',
          )}
        >
          {message.text}
        </Card>
      )}

      {oversizedFile && (
        <Card className="border-amber-400/30 bg-amber-400/10 px-ds-3 py-ds-2 text-[11px] text-ds-text shadow-none">
          <div className="flex items-start gap-2">
            <AlertCircle size={14} className="mt-0.5 flex-shrink-0 text-amber-300" aria-hidden="true" />
            <div>
              <div className="font-medium">
                {t('sidebar.oversize', {
                  name: oversizedFile.name,
                  size: formatSize(oversizedFile.size),
                })}
              </div>
              <div className="mt-1 text-ds-muted">{t('sidebar.oversizeHint')}</div>
            </div>
          </div>
        </Card>
      )}

      {richError && (
        <UploadErrorState
          error={richError}
          onRetry={
            lastFiles && lastFiles.length > 0
              ? () => {
                  void processFiles(lastFiles);
                }
              : null
          }
          onDismiss={() => setRichError(null)}
        />
      )}

      {preview && <SchemaPreviewCard preview={preview} />}
    </div>
  );
}
