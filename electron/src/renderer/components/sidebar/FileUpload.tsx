/**
 * File upload drag-and-drop with format guidance and explicit validation states.
 */

import { useCallback, useState } from 'react';
import { AlertCircle, Loader2, Upload } from 'lucide-react';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  onUpload: (file: File) => Promise<string | null>;
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
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ tone: 'error' | 'success'; text: string } | null>(null);
  const [oversizedFile, setOversizedFile] = useState<{ name: string; size: number } | null>(null);

  const processFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) {
        return;
      }

      setMessage(null);
      setOversizedFile(null);

      const validFiles: File[] = [];
      const errors: string[] = [];

      for (const file of files) {
        const error = validateFile(file);
        if (error) {
          errors.push(`${file.name}: ${t(error.key, error.vars)}`);
          if (file.size > MAX_UPLOAD_SIZE) {
            setOversizedFile({ name: file.name, size: file.size });
          }
          continue;
        }
        validFiles.push(file);
      }

      if (validFiles.length === 0) {
        setMessage({ tone: 'error', text: errors[0] ?? t('sidebar.uploadFailed') });
        return;
      }

      setUploading(true);
      const uploaded: string[] = [];
      const uploadErrors: string[] = [...errors];
      try {
        for (const file of validFiles) {
          try {
            await onUpload(file);
            uploaded.push(file.name);
          } catch (error) {
            uploadErrors.push(
              `${file.name}: ${error instanceof Error ? error.message : String(error)}`,
            );
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
        return;
      }

      setMessage({ tone: 'error', text: uploadErrors[0] ?? t('sidebar.uploadFailed') });
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

  const handleClick = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.accept = ACCEPTED_EXTENSIONS;

    input.onchange = () => {
      void processFiles(Array.from(input.files ?? []));
    };

    input.click();
  }, [processFiles]);

  return (
    <div className="space-y-2 px-3 py-1.5">
      <div
        onDrop={(e) => void handleDrop(e)}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        className={`
          cursor-pointer rounded-lg border border-dashed px-3 py-3 transition-colors
          ${dragging ? 'border-ds-accent bg-ds-accent/10' : 'border-ds-border hover:border-ds-muted hover:bg-ds-bg'}
          ${uploading ? 'pointer-events-none opacity-60' : ''}
        `}
      >
        <div className="flex flex-col items-center justify-center gap-1">
          {uploading ? (
            <Loader2 size={16} className="animate-spin text-ds-accent" />
          ) : (
            <Upload size={16} className="text-ds-muted" />
          )}
          <span className="text-center text-[11px] font-medium text-ds-text">
            {dragging ? t('sidebar.dropToImport') : t('sidebar.importFiles')}
          </span>
          <span className="text-center text-[10px] text-ds-muted">
            {t('sidebar.supportsUpTo')}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap gap-1">
        {SUPPORTED_FORMATS.map((format) => (
          <span
            key={format}
            className="rounded-full border border-ds-border bg-ds-bg px-2 py-0.5 text-[10px] text-ds-muted"
          >
            {format}
          </span>
        ))}
      </div>

      {message && (
        <div
          className={`rounded-lg border px-3 py-2 text-[11px] ${
            message.tone === 'error'
              ? 'border-ds-error/40 bg-ds-error/10 text-ds-text'
              : 'border-ds-success/40 bg-ds-success/10 text-ds-text'
          }`}
        >
          {message.text}
        </div>
      )}

      {oversizedFile && (
        <div className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] text-ds-text">
          <div className="flex items-start gap-2">
            <AlertCircle size={14} className="mt-0.5 flex-shrink-0 text-amber-300" />
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
        </div>
      )}
    </div>
  );
}
