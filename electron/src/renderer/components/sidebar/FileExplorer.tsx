/**
 * File explorer — files grouped by top-level folder with preview + delete.
 *
 * Layout:
 *   Files header (icon, count, refresh button)
 *   ├─ (workspace root)
 *   │   • titanic.csv       (preview / delete on hover)
 *   │   • report.md         (preview / delete on hover)
 *   └─ projects/
 *       • meta.json
 *       ...
 *
 * Plot files are hidden here (they live in PlotGallery instead).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Files,
  FileText,
  FileSpreadsheet,
  FileCode,
  RefreshCw,
  Loader2,
  ChevronRight,
  ChevronDown,
  Folder,
  Download,
  Eye,
  Trash2,
} from 'lucide-react';
import { useFilesStore, type FileEntry, type FileGroup } from '../../stores/filesStore';
import { useI18n } from '../../stores/i18nStore';
import { useWs } from '../../hooks/WsProvider';
import { FilePreviewModal } from './FilePreviewModal';

interface Props {
  onRefresh: () => void;
}

const TYPE_ICONS: Record<string, React.ElementType> = {
  csv: FileSpreadsheet,
  tsv: FileSpreadsheet,
  xlsx: FileSpreadsheet,
  xls: FileSpreadsheet,
  parquet: FileSpreadsheet,
  pq: FileSpreadsheet,
  json: FileCode,
  yaml: FileCode,
  yml: FileCode,
  py: FileCode,
  md: FileText,
  txt: FileText,
  log: FileText,
};

// File types where an inline preview makes sense.
const PREVIEWABLE = new Set([
  'csv',
  'tsv',
  'xlsx',
  'xls',
  'parquet',
  'pq',
  'md',
  'txt',
  'log',
  'json',
  'yaml',
  'yml',
  'toml',
  'py',
  'ini',
]);

// P1-12: Map source file type → available export targets.
const EXPORT_TARGETS: Record<string, { format: string; label: string }[]> = {
  md: [
    { format: 'pdf', label: 'PDF' },
    { format: 'docx', label: 'Word (.docx)' },
    { format: 'html', label: 'HTML' },
  ],
  markdown: [
    { format: 'pdf', label: 'PDF' },
    { format: 'docx', label: 'Word (.docx)' },
    { format: 'html', label: 'HTML' },
  ],
  csv: [
    { format: 'xlsx', label: 'Excel (.xlsx)' },
    { format: 'html', label: 'HTML' },
  ],
  tsv: [
    { format: 'xlsx', label: 'Excel (.xlsx)' },
    { format: 'html', label: 'HTML' },
  ],
  ipynb: [
    { format: 'pdf', label: 'PDF' },
    { format: 'html', label: 'HTML' },
    { format: 'ipynb', label: 'Notebook copy' },
  ],
  html: [{ format: 'pdf', label: 'PDF' }],
  htm: [{ format: 'pdf', label: 'PDF' }],
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function formatRelative(ms: number | undefined): string {
  if (!ms) return '';
  const diff = Date.now() - ms;
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

function FileIcon({ type }: { type: string }) {
  const Icon = TYPE_ICONS[type] ?? FileText;
  return <Icon size={13} className="text-ds-muted flex-shrink-0" />;
}

export function FileExplorer({ onRefresh }: Props) {
  const { fileGroups, files, loading } = useFilesStore();
  const { t } = useI18n();
  const totalNonPlot = fileGroups.reduce((n, g) => n + g.entries.length, 0);

  const [previewPath, setPreviewPath] = useState<string | null>(null);

  return (
    <>
      <div>
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-1.5">
          <div className="flex items-center gap-1.5 text-xs font-medium text-ds-muted uppercase tracking-wider">
            <Files size={12} />
            {t('sidebar.files')}
            {totalNonPlot > 0 && (
              <span className="ml-1 bg-ds-accent/20 text-ds-accent text-[10px] px-1.5 rounded-full">
                {totalNonPlot}
              </span>
            )}
          </div>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="p-0.5 rounded hover:bg-ds-bg text-ds-muted hover:text-ds-text transition-colors"
            title={t('sidebar.refreshFiles')}
            aria-label={t('sidebar.refreshFiles')}
          >
            {loading ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <RefreshCw size={12} />
            )}
          </button>
        </div>

        {/* Groups */}
        <div className="px-1">
          {totalNonPlot === 0 ? (
            <div className="px-3 py-2 text-[11px] text-ds-muted/60">
              {files.length === 0 ? t('sidebar.noFiles') : t('sidebar.onlyPlots')}
            </div>
          ) : (
            fileGroups.map((group) => (
              <FolderGroup
                key={group.folder || '__root__'}
                group={group}
                onPreview={setPreviewPath}
              />
            ))
          )}
        </div>
      </div>

      {previewPath && (
        <FilePreviewModal path={previewPath} onClose={() => setPreviewPath(null)} />
      )}
    </>
  );
}

function FolderGroup({
  group,
  onPreview,
}: {
  group: FileGroup;
  onPreview: (path: string) => void;
}) {
  // Root files always visible; named folders collapsible (expanded by default).
  const [expanded, setExpanded] = useState(true);
  const isRoot = group.folder === '';

  return (
    <div className="mb-0.5">
      {!isRoot && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="w-full flex items-center gap-1 px-2 py-0.5 rounded hover:bg-ds-bg text-[11px] text-ds-muted hover:text-ds-text transition-colors"
        >
          {expanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          <Folder size={11} />
          <span className="truncate">{group.folder}</span>
          <span className="ml-auto text-[10px] text-ds-muted/50">
            {group.entries.length}
          </span>
        </button>
      )}

      {expanded && (
        <div className={isRoot ? '' : 'pl-3 border-l border-ds-border/40 ml-2'}>
          {group.entries.map((file) => (
            <FileRow key={file.path} file={file} onPreview={onPreview} />
          ))}
        </div>
      )}
    </div>
  );
}

function FileRow({
  file,
  onPreview,
}: {
  file: FileEntry;
  onPreview: (path: string) => void;
}) {
  const { rpc } = useWs();
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const exportMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!exportOpen) return;
    const handler = (event: MouseEvent) => {
      if (!exportMenuRef.current) return;
      if (exportMenuRef.current.contains(event.target as Node)) return;
      setExportOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [exportOpen]);

  const handleDelete = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      const ok = window.confirm(t('sidebar.deleteConfirm', { name: file.name }));
      if (!ok) return;
      setBusy(true);
      try {
        await rpc('files.delete', { path: file.path });
      } catch (err) {
        console.error('[FileExplorer] delete failed:', err);
        window.alert(
          t('sidebar.deleteFailed', { message: (err as Error)?.message ?? String(err) }),
        );
      } finally {
        setBusy(false);
      }
    },
    [rpc, file, t],
  );

  const handlePreview = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onPreview(file.path);
    },
    [file.path, onPreview],
  );

  const handleExport = useCallback(
    async (format: string) => {
      if (!window.electronAPI?.finishArtifactExport) {
        window.alert(t('sidebar.exportDesktopOnly'));
        return;
      }
      setExportOpen(false);
      setExporting(format);
      try {
        const staged = (await rpc('files.export', { path: file.path, format })) as {
          exportPath: string;
          suggestedFilename: string;
          format: string;
          needsPdfRender: boolean;
        };
        const result = await window.electronAPI.finishArtifactExport({
          stagedPath: staged.exportPath,
          suggestedFilename: staged.suggestedFilename,
          format: staged.format,
          needsPdfRender: staged.needsPdfRender,
        });
        if (!result.canceled && result.error) {
          window.alert(t('sidebar.exportFailed', { message: result.error }));
        }
      } catch (err) {
        console.error('[FileExplorer] export failed:', err);
        window.alert(
          t('sidebar.exportFailed', { message: (err as Error)?.message ?? String(err) }),
        );
      } finally {
        setExporting(null);
      }
    },
    [rpc, file.path, t],
  );

  const previewable = PREVIEWABLE.has(file.type.toLowerCase());
  const exportTargets = EXPORT_TARGETS[file.type.toLowerCase()] ?? [];
  const exportable = exportTargets.length > 0;

  return (
    <div
      className="
        flex items-center gap-2 px-2 py-1 rounded
        hover:bg-ds-bg group text-xs
      "
      title={`${file.path} (${formatSize(file.size)})`}
    >
      <FileIcon type={file.type} />
      <button
        onClick={previewable ? handlePreview : undefined}
        disabled={!previewable}
        className="truncate text-left text-ds-text/80 group-hover:text-ds-text flex-1 min-w-0 disabled:cursor-default"
      >
        {file.name}
      </button>
      <span className="text-[10px] text-ds-muted/50 flex-shrink-0 hidden group-hover:inline">
        {formatRelative(file.modifiedAt)}
      </span>
      <span className="text-[10px] text-ds-muted/50 flex-shrink-0">
        {formatSize(file.size)}
      </span>

      {/* Action buttons — visible on hover */}
      <div className="hidden group-hover:flex items-center gap-0.5 flex-shrink-0">
        {previewable && (
          <button
            onClick={handlePreview}
            className="p-0.5 rounded hover:bg-ds-surface text-ds-muted hover:text-ds-accent transition-colors"
            title={t('sidebar.preview')}
            aria-label={t('sidebar.preview')}
          >
            <Eye size={12} />
          </button>
        )}
        {exportable && (
          <div className="relative" ref={exportMenuRef}>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setExportOpen((open) => !open);
              }}
              disabled={exporting !== null}
              className="p-0.5 rounded hover:bg-ds-surface text-ds-muted hover:text-ds-accent transition-colors disabled:opacity-50"
              title={t('sidebar.exportAs')}
              aria-label={t('sidebar.exportAs')}
            >
              {exporting ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Download size={12} />
              )}
            </button>
            {exportOpen && (
              <div className="absolute right-0 top-full z-10 mt-1 w-36 rounded-md border border-ds-border bg-ds-surface shadow-lg">
                <div className="px-2 py-1 text-[10px] uppercase tracking-wider text-ds-muted">
                  {t('sidebar.exportAs')}
                </div>
                {exportTargets.map((target) => (
                  <button
                    key={target.format}
                    onClick={() => void handleExport(target.format)}
                    className="flex w-full items-center px-2 py-1 text-left text-[11px] text-ds-text hover:bg-ds-bg"
                  >
                    {target.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        <button
          onClick={handleDelete}
          disabled={busy}
          className="p-0.5 rounded hover:bg-ds-surface text-ds-muted hover:text-red-400 transition-colors disabled:opacity-50"
          title={t('sidebar.delete')}
          aria-label={t('sidebar.delete')}
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
        </button>
      </div>
    </div>
  );
}
