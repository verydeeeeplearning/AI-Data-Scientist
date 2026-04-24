/**
 * File explorer files grouped by top-level folder with preview + delete.
 *
 * Layout:
 *   Files header (icon, count, refresh button)
 *   workspace root
 *     titanic.csv       (preview / delete on hover or focus)
 *     report.md         (preview / delete on hover or focus)
 *   projects/
 *     meta.json
 *     ...
 *
 * Plot files are hidden here (they live in PlotGallery instead).
 */

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ElementType,
  type MouseEvent as ReactMouseEvent,
} from 'react';
import {
  Files,
  FileText,
  FileSpreadsheet,
  FileCode,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  Folder,
  Download,
  Eye,
  Trash2,
} from 'lucide-react';
import { Badge, Button, Card } from '../../design-system/primitives';
import { useFilesStore, type FileEntry, type FileGroup } from '../../stores/filesStore';
import { useI18n } from '../../stores/i18nStore';
import { resolveMainIpcErrorMessage } from '../../utils/mainIpcErrors';
import { useWs } from '../../hooks/WsProvider';
import { FilePreviewModal } from './FilePreviewModal';

interface Props {
  onRefresh: () => void;
}

const TYPE_ICONS: Record<string, ElementType> = {
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
  return <Icon size={13} className="shrink-0 text-ds-muted" aria-hidden="true" />;
}

export function FileExplorer({ onRefresh }: Props) {
  const { fileGroups, files, loading } = useFilesStore();
  const { t } = useI18n();
  const totalNonPlot = fileGroups.reduce((n, g) => n + g.entries.length, 0);
  const [previewPath, setPreviewPath] = useState<string | null>(null);

  return (
    <>
      <section aria-labelledby="file-explorer-title" aria-busy={loading}>
        <div className="flex items-center justify-between px-3 py-1.5">
          <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-ds-muted">
            <Files size={12} aria-hidden="true" />
            <h2 id="file-explorer-title" className="text-inherit">
              {t('sidebar.files')}
            </h2>
            {totalNonPlot > 0 && (
              <Badge
                compact
                tone="accent"
                className="ml-1 min-w-[1.25rem] justify-center px-ds-2 py-0.5 normal-case shadow-none"
              >
                {totalNonPlot}
              </Badge>
            )}
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            loading={loading}
            leadingIcon={<RefreshCw size={12} aria-hidden="true" />}
            title={t('sidebar.refreshFiles')}
            aria-label={t('sidebar.refreshFiles')}
            className="h-7 min-h-7 w-7 rounded-ds-md px-0 shadow-none"
          >
            <span className="sr-only">{t('sidebar.refreshFiles')}</span>
          </Button>
        </div>

        <div className="px-1">
          {totalNonPlot === 0 ? (
            <Card
              role="status"
              aria-live="polite"
              className="mx-2 bg-ds-bg/40 px-ds-3 py-ds-3 text-[11px] text-ds-muted shadow-none"
            >
              {files.length === 0 ? t('sidebar.noFiles') : t('sidebar.onlyPlots')}
            </Card>
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
      </section>

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
  const [expanded, setExpanded] = useState(true);
  const groupId = useId().replace(/:/g, '');
  const isRoot = group.folder === '';
  const panelId = `file-group-panel-${groupId}`;

  return (
    <div className="mb-1">
      {!isRoot && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setExpanded((e) => !e)}
          aria-expanded={expanded}
          aria-controls={panelId}
          className="w-full min-h-8 justify-start gap-ds-1 rounded-ds-lg px-ds-2 text-[11px] text-ds-muted shadow-none"
        >
          {expanded ? <ChevronDown size={11} aria-hidden="true" /> : <ChevronRight size={11} aria-hidden="true" />}
          <Folder size={11} aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate text-left">{group.folder}</span>
          <Badge compact tone="neutral" className="ml-auto px-ds-2 py-0.5 normal-case shadow-none">
            {group.entries.length}
          </Badge>
        </Button>
      )}

      {expanded && (
        <div
          id={isRoot ? undefined : panelId}
          className={isRoot ? '' : 'ml-2 border-l border-ds-border/40 pl-3'}
        >
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
  const exportMenuId = `file-export-menu-${useId().replace(/:/g, '')}`;

  useEffect(() => {
    if (!exportOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!exportMenuRef.current) return;
      if (exportMenuRef.current.contains(event.target as Node)) return;
      setExportOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setExportOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [exportOpen]);

  const handleDelete = useCallback(
    async (event: ReactMouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();
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
    [file.name, file.path, rpc, t],
  );

  const handlePreview = useCallback(
    (event: ReactMouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();
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
          window.alert(
            t('sidebar.exportFailed', {
              message: resolveMainIpcErrorMessage(result, 'common.mainIpc.export.finishFailed'),
            }),
          );
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
    [file.path, rpc, t],
  );

  const previewable = PREVIEWABLE.has(file.type.toLowerCase());
  const exportTargets = EXPORT_TARGETS[file.type.toLowerCase()] ?? [];
  const exportable = exportTargets.length > 0;

  return (
    <Card
      className="
        group flex items-center gap-ds-2 border-ds-border/40 bg-transparent px-ds-2 py-ds-2 text-xs
        shadow-none transition-colors hover:border-ds-accent/20 hover:bg-ds-bg/60
        focus-within:border-ds-accent/30 focus-within:bg-ds-bg/60
      "
      title={`${file.path} (${formatSize(file.size)})`}
    >
      <FileIcon type={file.type} />
      {previewable ? (
        <button
          type="button"
          onClick={handlePreview}
          className="
            min-w-0 flex-1 truncate text-left text-ds-text/80 transition-colors hover:text-ds-text
            focus-visible:rounded-ds-sm focus-visible:outline-none focus-visible:ring-2
            focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg
            focus-visible:text-ds-text
          "
          aria-label={`${t('sidebar.preview')}: ${file.name}`}
        >
          {file.name}
        </button>
      ) : (
        <span className="min-w-0 flex-1 truncate text-ds-text/80">{file.name}</span>
      )}
      <span className="hidden shrink-0 text-[10px] text-ds-muted/60 group-hover:inline group-focus-within:inline">
        {formatRelative(file.modifiedAt)}
      </span>
      <Badge compact tone="neutral" className="shrink-0 px-ds-2 py-0.5 text-[10px] shadow-none">
        {formatSize(file.size)}
      </Badge>

      <div className="hidden shrink-0 items-center gap-0.5 group-hover:flex group-focus-within:flex">
        {previewable && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handlePreview}
            leadingIcon={<Eye size={12} aria-hidden="true" />}
            className="h-7 min-h-7 w-7 rounded-ds-md px-0 shadow-none"
            title={t('sidebar.preview')}
            aria-label={t('sidebar.preview')}
          >
            <span className="sr-only">{t('sidebar.preview')}</span>
          </Button>
        )}
        {exportable && (
          <div className="relative" ref={exportMenuRef}>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={(event) => {
                event.stopPropagation();
                setExportOpen((open) => !open);
              }}
              loading={exporting !== null}
              leadingIcon={<Download size={12} aria-hidden="true" />}
              aria-expanded={exportOpen}
              aria-controls={exportMenuId}
              aria-haspopup="menu"
              className="h-7 min-h-7 w-7 rounded-ds-md px-0 shadow-none"
              title={t('sidebar.exportAs')}
              aria-label={t('sidebar.exportAs')}
            >
              <span className="sr-only">{t('sidebar.exportAs')}</span>
            </Button>
            {exportOpen && (
              <Card
                id={exportMenuId}
                role="menu"
                aria-label={t('sidebar.exportAs')}
                className="absolute right-0 top-full z-10 mt-1 w-40 border-ds-border bg-ds-surface/95 p-ds-1 shadow-ds-md"
              >
                <div className="px-ds-2 py-ds-1 text-[10px] uppercase tracking-wider text-ds-muted">
                  {t('sidebar.exportAs')}
                </div>
                {exportTargets.map((target) => (
                  <Button
                    key={target.format}
                    type="button"
                    variant="ghost"
                    size="sm"
                    role="menuitem"
                    onClick={() => void handleExport(target.format)}
                    className="w-full min-h-8 justify-start rounded-ds-lg px-ds-2 text-[11px] text-ds-text shadow-none"
                  >
                    {target.label}
                  </Button>
                ))}
              </Card>
            )}
          </div>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleDelete}
          loading={busy}
          leadingIcon={<Trash2 size={12} aria-hidden="true" />}
          className="h-7 min-h-7 w-7 rounded-ds-md px-0 text-ds-muted shadow-none hover:text-red-400"
          title={t('sidebar.delete')}
          aria-label={t('sidebar.delete')}
        >
          <span className="sr-only">{t('sidebar.delete')}</span>
        </Button>
      </div>
    </Card>
  );
}
