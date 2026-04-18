/**
 * Plot gallery — thumbnails of generated plots in sidebar, grouped by folder.
 *
 * Layout:
 *   Plots (count)
 *   ├─ (workspace root)
 *   │   [thumb] [thumb]
 *   └─ eda_titanic/
 *       [thumb] [thumb] [thumb]
 *
 * Hover a thumbnail to reveal a delete button. Click to open the full-size
 * modal, which also has a delete action.
 */

import { useCallback, useEffect, useState } from 'react';
import { BarChart3, X, Trash2, Loader2, ChevronDown, ChevronRight, Folder } from 'lucide-react';
import { useFilesStore, type PlotEntry, type PlotGroup } from '../../stores/filesStore';
import { useI18n } from '../../stores/i18nStore';
import { useWs } from '../../hooks/WsProvider';
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
      <div>
        {/* Header */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-ds-muted uppercase tracking-wider">
          <BarChart3 size={12} />
          {t('sidebar.plots')}
          {plots.length > 0 && (
            <span className="ml-1 bg-ds-accent/20 text-ds-accent text-[10px] px-1.5 rounded-full">
              {plots.length}
            </span>
          )}
        </div>

        {/* Grouped thumbnails */}
        <div className="px-1">
          {plots.length === 0 ? (
            <div className="px-3 py-2 text-[11px] text-ds-muted/60">
              {t('sidebar.noPlots')}
            </div>
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
      </div>

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
  const isRoot = group.folder === '';

  return (
    <div className="mb-1">
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
        <div
          className={`grid grid-cols-2 gap-1 ${
            isRoot ? 'px-2' : 'pl-3 pr-2 ml-2 border-l border-ds-border/40'
          }`}
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
    async (e: React.MouseEvent) => {
      e.stopPropagation();
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
    [rpc, plot, t],
  );

  return (
    <div className="relative group">
      <button
        onClick={() => onSelect(plot)}
        className="
          block w-full rounded border border-ds-border overflow-hidden
          hover:border-ds-accent transition-colors cursor-pointer
          bg-ds-bg
        "
        title={plot.name}
      >
        <img
          src={plotSrc(plot.path)}
          alt={plot.name}
          className="w-full h-16 object-cover"
          loading="lazy"
        />
        <div className="px-1 py-0.5 text-[9px] text-ds-muted truncate">
          {plot.name}
        </div>
      </button>

      {/* Delete overlay — shown on hover */}
      <button
        onClick={handleDelete}
        disabled={busy}
        className="
          absolute top-0.5 right-0.5 p-1 rounded
          bg-black/60 text-white/90 hover:bg-red-500/80
          opacity-0 group-hover:opacity-100 transition-opacity
          disabled:opacity-50
        "
        title={t('sidebar.delete')}
        aria-label={t('sidebar.delete')}
      >
        {busy ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
      </button>
    </div>
  );
}

function PlotModal({ plot, onClose }: { plot: PlotEntry; onClose: () => void }) {
  const { rpc } = useWs();
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
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
  }, [rpc, plot, onClose, t]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="plot-gallery-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="relative max-w-[90vw] max-h-[90vh] bg-ds-surface rounded-lg border border-ds-border shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-ds-border gap-3">
          <span id="plot-gallery-title" className="text-sm text-ds-text font-medium truncate flex-1">
            {plot.path}
          </span>
          <button
            onClick={handleDelete}
            disabled={busy}
            className="p-1 rounded hover:bg-red-500/20 text-ds-muted hover:text-red-400 transition-colors disabled:opacity-50"
            title={t('sidebar.delete')}
        aria-label={t('sidebar.delete')}
          >
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}
          </button>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-ds-bg text-ds-muted hover:text-ds-text transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Image */}
        <div className="p-4 flex items-center justify-center">
          <img
            src={plotSrc(plot.path)}
            alt={plot.name}
            className="max-w-full max-h-[80vh] object-contain"
          />
        </div>
      </div>
    </div>
  );
}
