/**
 * Plot gallery thumbnails of generated plots in sidebar, grouped by folder.
 *
 * Layout:
 *   Plots (count)
 *   workspace root
 *     [thumb] [thumb]
 *   eda_titanic/
 *     [thumb] [thumb] [thumb]
 *
 * Hover or focus a thumbnail to reveal a delete button. Click to open the
 * full-size modal, which also has a delete action.
 */

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from 'react';
import { BarChart3, ChevronDown, ChevronRight, Folder, Trash2, X } from 'lucide-react';
import { Badge, Button, Card, cn } from '../../design-system/primitives';
import { useWs } from '../../hooks/WsProvider';
import { useFilesStore, type PlotEntry, type PlotGroup } from '../../stores/filesStore';
import { useI18n } from '../../stores/i18nStore';
import { getBackendBase } from '../../utils/backendUrl';

// 4.14 fix: Dynamic backend URL instead of hardcoded port
const BACKEND_BASE = getBackendBase();

function plotSrc(path: string): string {
  return `${BACKEND_BASE}/api/plots/${encodeURIComponent(path)}`;
}

export function PlotGallery() {
  const { plots, plotGroups } = useFilesStore();
  const { t } = useI18n();
  const [selectedPlot, setSelectedPlot] = useState<PlotEntry | null>(null);

  return (
    <>
      <section aria-labelledby="plot-gallery-title">
        <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium uppercase tracking-wider text-ds-muted">
          <BarChart3 size={12} aria-hidden="true" />
          <h2 id="plot-gallery-title" className="text-inherit">
            {t('sidebar.plots')}
          </h2>
          {plots.length > 0 && (
            <Badge
              compact
              tone="accent"
              className="ml-1 min-w-[1.25rem] justify-center px-ds-2 py-0.5 normal-case shadow-none"
            >
              {plots.length}
            </Badge>
          )}
        </div>

        <div className="px-1">
          {plots.length === 0 ? (
            <Card
              role="status"
              aria-live="polite"
              className="mx-2 bg-ds-bg/40 px-ds-3 py-ds-3 text-[11px] text-ds-muted shadow-none"
            >
              {t('sidebar.noPlots')}
            </Card>
          ) : (
            plotGroups.map((group) => (
              <PlotFolder
                key={group.folder || '__root__'}
                group={group}
                onSelect={setSelectedPlot}
              />
            ))
          )}
        </div>
      </section>

      {selectedPlot && (
        <PlotModal plot={selectedPlot} onClose={() => setSelectedPlot(null)} />
      )}
    </>
  );
}

function PlotFolder({
  group,
  onSelect,
}: {
  group: PlotGroup;
  onSelect: (plot: PlotEntry) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const folderId = useId().replace(/:/g, '');
  const isRoot = group.folder === '';
  const panelId = `plot-folder-panel-${folderId}`;

  return (
    <div className="mb-1">
      {!isRoot && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setExpanded((open) => !open)}
          aria-expanded={expanded}
          aria-controls={panelId}
          className="w-full min-h-8 justify-start gap-ds-1 rounded-ds-lg px-ds-2 text-[11px] text-ds-muted shadow-none"
        >
          {expanded ? (
            <ChevronDown size={11} aria-hidden="true" />
          ) : (
            <ChevronRight size={11} aria-hidden="true" />
          )}
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
          className={cn(
            'grid grid-cols-2 gap-1',
            isRoot ? 'px-2' : 'ml-2 border-l border-ds-border/40 pl-3 pr-2',
          )}
        >
          {group.entries.map((plot) => (
            <PlotThumbnail key={plot.path} plot={plot} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  );
}

function PlotThumbnail({
  plot,
  onSelect,
}: {
  plot: PlotEntry;
  onSelect: (plot: PlotEntry) => void;
}) {
  const { rpc } = useWs();
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);

  const handleDelete = useCallback(
    async (event: ReactMouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();
      const ok = window.confirm(t('sidebar.deleteConfirm', { name: plot.name }));
      if (!ok) return;
      setBusy(true);
      try {
        await rpc('files.delete', { path: plot.path });
      } catch (err) {
        console.error('[PlotGallery] delete failed:', err);
        window.alert(
          t('sidebar.deleteFailed', { message: (err as Error)?.message ?? String(err) }),
        );
      } finally {
        setBusy(false);
      }
    },
    [plot.name, plot.path, rpc, t],
  );

  return (
    <Card className="group relative overflow-hidden border-ds-border/40 bg-transparent p-0 shadow-none transition-colors hover:border-ds-accent/30 focus-within:border-ds-accent/30">
      <button
        type="button"
        onClick={() => onSelect(plot)}
        className="
          block w-full overflow-hidden rounded-ds-xl bg-ds-bg text-left transition-colors
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70
          focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg
        "
        title={plot.name}
        aria-label={`${t('sidebar.preview')}: ${plot.name}`}
      >
        <img
          src={plotSrc(plot.path)}
          alt={plot.name}
          className="h-16 w-full object-cover"
          loading="lazy"
        />
        <div className="truncate px-1 py-0.5 text-[9px] text-ds-muted">{plot.name}</div>
      </button>

      <div className="pointer-events-none absolute right-1 top-1 flex opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleDelete}
          disabled={busy}
          loading={busy}
          leadingIcon={<Trash2 size={12} aria-hidden="true" />}
          className="
            pointer-events-auto h-7 min-h-7 w-7 rounded-ds-md bg-ds-surface-elevated/90 px-0
            text-ds-text shadow-none backdrop-blur-sm hover:bg-ds-error/15 hover:text-ds-error
          "
          title={t('sidebar.delete')}
          aria-label={t('sidebar.delete')}
        >
          <span className="sr-only">{t('sidebar.delete')}</span>
        </Button>
      </div>
    </Card>
  );
}

function PlotModal({ plot, onClose }: { plot: PlotEntry; onClose: () => void }) {
  const { rpc } = useWs();
  const { t } = useI18n();
  const modalId = useId().replace(/:/g, '');
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const [busy, setBusy] = useState(false);
  const titleId = `plot-gallery-title-${modalId}`;
  const descriptionId = `plot-gallery-description-${modalId}`;

  useEffect(() => {
    previouslyFocused.current = (document.activeElement as HTMLElement | null) ?? null;
    queueMicrotask(() => {
      dialogRef.current?.focus();
    });

    return () => {
      previouslyFocused.current?.focus();
    };
  }, []);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const handleDelete = useCallback(async () => {
    const ok = window.confirm(t('sidebar.deleteConfirm', { name: plot.name }));
    if (!ok) return;
    setBusy(true);
    try {
      await rpc('files.delete', { path: plot.path });
      onClose();
    } catch (err) {
      console.error('[PlotGallery] delete failed:', err);
      window.alert(
        t('sidebar.deleteFailed', { message: (err as Error)?.message ?? String(err) }),
      );
      setBusy(false);
    }
  }, [onClose, plot.name, plot.path, rpc, t]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        tabIndex={-1}
        className="max-h-[90vh] w-full max-w-[90vw] outline-none"
        onClick={(event) => event.stopPropagation()}
      >
        <Card className="relative flex max-h-[90vh] flex-col overflow-hidden border-ds-border bg-ds-surface p-0 shadow-2xl">
          <div className="flex items-center justify-between gap-3 border-b border-ds-border px-4 py-2">
            <div className="min-w-0">
              <div id={titleId} className="truncate text-sm font-medium text-ds-text">
                {plot.path}
              </div>
              <div id={descriptionId} className="sr-only">
                {plot.name}
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleDelete}
                disabled={busy}
                loading={busy}
                leadingIcon={<Trash2 size={15} aria-hidden="true" />}
                className="h-8 min-h-8 w-8 rounded-ds-md px-0 text-ds-muted shadow-none hover:text-ds-error"
                title={t('sidebar.delete')}
                aria-label={t('sidebar.delete')}
              >
                <span className="sr-only">{t('sidebar.delete')}</span>
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onClose}
                leadingIcon={<X size={16} aria-hidden="true" />}
                className="h-8 min-h-8 w-8 rounded-ds-md px-0 text-ds-muted shadow-none hover:text-ds-text"
                title={t('common.close')}
                aria-label={t('common.close')}
              >
                <span className="sr-only">{t('common.close')}</span>
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-center p-4">
            <img
              src={plotSrc(plot.path)}
              alt={plot.name}
              className="max-h-[80vh] max-w-full object-contain"
            />
          </div>
        </Card>
      </div>
    </div>
  );
}
