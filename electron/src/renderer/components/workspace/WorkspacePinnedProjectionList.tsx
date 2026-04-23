import { ArrowUpRight, Pin } from 'lucide-react';
import { resolveCardDisplayMode } from '../../application/workspace/cardEmphasisAdopter';
import { useAudienceView } from '../../hooks/useAudienceView';
import {
  findWorkspacePinnedItem,
  matchesWorkspacePinnedItem,
  type WorkspacePinnedProjectionItem,
  type WorkspacePinnedProjectionStatus,
} from '../../stores/workspaceStore';
import type { EvidenceWorkspaceFocus } from '../../application/workspace/workspaceRoute';

interface Props {
  items: WorkspacePinnedProjectionItem[];
  pinnedCardCount: number;
  status: WorkspacePinnedProjectionStatus;
  focus?: EvidenceWorkspaceFocus | null;
  onSelectItem?: (item: WorkspacePinnedProjectionItem) => void;
  variant?: 'summary' | 'rail';
}

function formatPinnedType(type: WorkspacePinnedProjectionItem['type']): string {
  return type.charAt(0).toUpperCase() + type.slice(1);
}

function formatCreatedAt(timestamp: number): string {
  return new Date(timestamp).toLocaleString();
}

function renderSelectionTone(focus: EvidenceWorkspaceFocus | null | undefined): string {
  return focus?.mode === 'detail' ? 'Detail route' : 'Highlight route';
}

export function WorkspacePinnedProjectionList({
  items,
  pinnedCardCount,
  status,
  focus = null,
  onSelectItem,
  variant = 'summary',
}: Props) {
  const { view: audienceView } = useAudienceView();
  // Workspace-level density hint per item: the rail variant always wants
  // compact rows (forceCollapsed), while the summary variant follows the
  // active audience view via the shared precedence helper.
  const itemDisplayMode = resolveCardDisplayMode(
    {
      forceCollapsed: variant === 'rail',
    },
    audienceView,
  );
  const showItemDetails = itemDisplayMode === 'expanded';
  const selectedItem = focus ? findWorkspacePinnedItem(items, focus.target, focus.value) : null;
  const visibleItems = variant === 'rail' ? items.slice(0, 3) : items;

  if (status === 'empty') {
    return (
      <div className="rounded-2xl border border-dashed border-ds-border bg-ds-bg/40 px-4 py-4 text-sm leading-6 text-ds-muted">
        No pinned evidence yet. Pinning a result card in chat will project it into this workspace surface.
      </div>
    );
  }

  if (status === 'count_only') {
    return (
      <div className="rounded-2xl border border-dashed border-ds-border bg-ds-bg/40 px-4 py-4 text-sm leading-6 text-ds-muted">
        {pinnedCardCount} pinned items are known. Projection details will appear once the workspace receives the normalized card feed.
      </div>
    );
  }

  const interactive = typeof onSelectItem === 'function';

  return (
    <div
      className="space-y-3"
      data-audience-view={audienceView}
      data-display-mode={itemDisplayMode}
    >
      {variant === 'summary' && selectedItem && focus?.mode === 'detail' && (
        <section className="rounded-2xl border border-ds-accent/30 bg-ds-accent/10 px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-ds-accent">
                {renderSelectionTone(focus)}
              </p>
              <h4 className="mt-2 text-base font-semibold text-ds-text">{selectedItem.title}</h4>
            </div>
            <span className="rounded-full bg-ds-surface/80 px-2 py-1 text-xs text-ds-accent">
              {formatPinnedType(selectedItem.type)}
            </span>
          </div>
          {selectedItem.summary && (
            <p className="mt-3 text-sm leading-6 text-ds-muted">{selectedItem.summary}</p>
          )}
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-ds-muted">
            <span className="rounded-full border border-ds-border px-2 py-1">
              card {selectedItem.cardId}
            </span>
            <span className="rounded-full border border-ds-border px-2 py-1">
              result {selectedItem.resultId}
            </span>
            <span className="rounded-full border border-ds-border px-2 py-1">
              message {selectedItem.messageId}
            </span>
          </div>
        </section>
      )}

      {variant === 'summary' && focus && !selectedItem && (
        <div className="rounded-2xl border border-dashed border-ds-border bg-ds-bg/40 px-4 py-4 text-sm leading-6 text-ds-muted">
          The selected {focus.target} target is not present in the current pinned projection.
        </div>
      )}

      {visibleItems.map((item) => {
        const isSelected = focus ? matchesWorkspacePinnedItem(item, focus.target, focus.value) : false;
        const className = `w-full rounded-2xl border px-4 py-4 text-left transition-colors ${
          isSelected
            ? 'border-ds-accent bg-ds-accent/10'
            : 'border-ds-border bg-ds-bg/40 hover:border-ds-accent/40'
        }`;

        const content = (
          <>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate text-sm font-semibold text-ds-text">{item.title}</span>
                  {isSelected && (
                    <span className="rounded-full bg-ds-accent/15 px-2 py-0.5 text-[11px] text-ds-accent">
                      {renderSelectionTone(focus)}
                    </span>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ds-muted">
                  <span className="rounded-full border border-ds-border px-2 py-0.5">
                    {formatPinnedType(item.type)}
                  </span>
                  <span>Run {item.runId}</span>
                  <span>{formatCreatedAt(item.createdAt)}</span>
                </div>
              </div>
              {interactive && (
                <ArrowUpRight size={14} className={isSelected ? 'text-ds-accent' : 'text-ds-muted'} />
              )}
            </div>

            {showItemDetails && item.summary && (
              <p className="mt-3 text-sm leading-6 text-ds-muted">{item.summary}</p>
            )}

            {showItemDetails && (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ds-muted">
                <span className="inline-flex items-center gap-1 rounded-full border border-ds-border px-2 py-0.5">
                  <Pin size={11} />
                  {item.cardId}
                </span>
                <span>message {item.messageId}</span>
                {item.artifactPath && <span className="truncate">artifact {item.artifactPath}</span>}
              </div>
            )}
          </>
        );

        if (!interactive) {
          return (
            <div key={item.cardId} className={className}>
              {content}
            </div>
          );
        }

        return (
          <button
            key={item.cardId}
            type="button"
            onClick={() => onSelectItem(item)}
            className={className}
            aria-label={`Open pinned evidence ${item.title}`}
          >
            {content}
          </button>
        );
      })}

      {variant === 'rail' && items.length > visibleItems.length && (
        <div className="rounded-2xl border border-dashed border-ds-border bg-ds-bg/30 px-3 py-3 text-xs text-ds-muted">
          +{items.length - visibleItems.length} more pinned items in the workspace summary.
        </div>
      )}
    </div>
  );
}
