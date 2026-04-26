import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CheckCircle2,
  Clock3,
  GitBranch,
  Loader2,
  XCircle,
} from 'lucide-react';
import { prefersReducedMotion } from '../../application/a11y/reducedMotion';
import {
  flattenForKeyboardNav,
  planTreeKeyboardNav,
  type PlanTreeKeyboardKey,
  type PlanTreeKeyboardState,
} from '../../application/runtime/planTreeKeyboardNav';
import { Badge, Card } from '../../design-system/primitives';
import type { PlanNode, PlanNodeStatus } from '../../types/events';
import { useI18n } from '../../stores/i18nStore';
import { useReasoningTraceStore } from '../../stores/reasoningTraceStore';

const KEYBOARD_KEYS: ReadonlySet<string> = new Set([
  'ArrowDown',
  'ArrowUp',
  'ArrowRight',
  'ArrowLeft',
  'Home',
  'End',
]);

/**
 * Stable DOM id for a plan-tree node. Exported so other panels (e.g.
 * ReasoningTracePanel) can `document.getElementById` to focus the matching
 * tree item without introducing a global focus store.
 */
export function planTreeNodeDomId(nodeId: string): string {
  return `plan-tree-node-${nodeId}`;
}

function formatTimestamp(value: number | null | undefined): string | null {
  if (typeof value !== 'number') {
    return null;
  }
  return new Date(value).toLocaleTimeString();
}

function countPlanNodes(node: PlanNode): number {
  return 1 + node.children.reduce((total, child) => total + countPlanNodes(child), 0);
}

function statusTone(status: PlanNodeStatus): 'accent' | 'success' | 'danger' | 'warning' | 'neutral' {
  if (status === 'running') return 'accent';
  if (status === 'completed') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'skipped') return 'warning';
  return 'neutral';
}

function statusIcon(status: PlanNodeStatus, reduceMotion: boolean) {
  if (status === 'running') {
    return (
      <Loader2
        size={12}
        className={reduceMotion ? 'text-ds-accent' : 'animate-spin text-ds-accent'}
        aria-hidden="true"
      />
    );
  }
  if (status === 'completed') {
    return <CheckCircle2 size={12} className="text-ds-success" aria-hidden="true" />;
  }
  if (status === 'failed') {
    return <XCircle size={12} className="text-ds-error" aria-hidden="true" />;
  }
  return <Clock3 size={12} className="text-ds-muted" aria-hidden="true" />;
}

interface ReplanHighlightFlags {
  readonly added: boolean;
  readonly removed: boolean;
  readonly modified: boolean;
}

interface NodeMeta {
  readonly setSize: number;
  readonly posInSet: number;
}

function PlanNodeRow({
  node,
  depth,
  level,
  meta,
  reduceMotion,
  highlightFor,
  collapsedIds,
  focusedId,
  onKeyDown,
  onFocus,
  registerRef,
}: {
  node: PlanNode;
  depth: number;
  level: number;
  meta: NodeMeta;
  reduceMotion: boolean;
  highlightFor: (id: string) => ReplanHighlightFlags;
  collapsedIds: ReadonlySet<string>;
  focusedId: string | null;
  onKeyDown: (event: React.KeyboardEvent<HTMLButtonElement>, nodeId: string) => void;
  onFocus: (nodeId: string) => void;
  registerRef: (nodeId: string, el: HTMLButtonElement | null) => void;
}) {
  const startedAt = formatTimestamp(node.startedAt);
  const completedAt = formatTimestamp(node.completedAt);
  const flags = highlightFor(node.id);
  const hasChildren = node.children.length > 0;
  const expanded = hasChildren ? !collapsedIds.has(node.id) : false;
  const reasoningCount = node.reasoningRefs.length;

  const containerHighlight = flags.removed
    ? 'opacity-60 line-through decoration-ds-error/60'
    : flags.added || flags.modified
      ? 'ring-1 ring-ds-accent/40 bg-ds-accent/10'
      : '';

  const replanBadge = flags.added
    ? { label: 'added', tone: 'success' as const }
    : flags.removed
      ? { label: 'removed', tone: 'danger' as const }
      : flags.modified
        ? { label: 'modified', tone: 'accent' as const }
        : null;

  const replanSrText = flags.added
    ? 'This step was just added by a re-plan.'
    : flags.modified
      ? 'This step was just modified by a re-plan.'
      : flags.removed
        ? 'This step was just removed by a re-plan.'
        : null;

  const ariaLabelParts: string[] = [
    node.label,
    `status ${node.status}`,
  ];
  if (reasoningCount > 0) {
    ariaLabelParts.push(`${reasoningCount} reasoning ${reasoningCount === 1 ? 'note' : 'notes'}`);
  }
  if (replanSrText) {
    ariaLabelParts.push(replanSrText);
  }
  const ariaLabel = ariaLabelParts.join(', ');

  // ARIA tree treeitem props.
  const treeItemProps: Record<string, string | number | boolean> = {
    role: 'treeitem',
    'aria-level': level,
    'aria-setsize': meta.setSize,
    'aria-posinset': meta.posInSet,
  };
  if (hasChildren) {
    treeItemProps['aria-expanded'] = expanded;
  }

  const isFocused = focusedId === node.id;

  return (
    <li className="space-y-2" {...treeItemProps}>
      <button
        type="button"
        id={planTreeNodeDomId(node.id)}
        ref={(el) => registerRef(node.id, el)}
        tabIndex={isFocused ? 0 : -1}
        aria-label={ariaLabel}
        aria-busy="false"
        onKeyDown={(event) => onKeyDown(event, node.id)}
        onFocus={() => onFocus(node.id)}
        onClick={() => onFocus(node.id)}
        className={`block w-full text-left rounded-xl border border-ds-border/70 bg-ds-bg/60 px-3 py-3 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/60 ${containerHighlight}`}
        style={{ marginLeft: `${depth * 16}px` }}
        data-replan-state={replanBadge?.label ?? 'stable'}
      >
        <div className="flex flex-wrap items-start gap-2">
          <span className="mt-0.5">{statusIcon(node.status, reduceMotion)}</span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-ds-text">{node.label}</span>
              <Badge
                tone={statusTone(node.status)}
                compact
                className="uppercase tracking-[0.16em]"
              >
                {node.status}
              </Badge>
              {replanBadge ? (
                <Badge
                  tone={replanBadge.tone}
                  compact
                  className="uppercase tracking-[0.16em]"
                >
                  {replanBadge.label}
                </Badge>
              ) : null}
              {reasoningCount > 0 ? (
                <Badge compact aria-hidden="true">
                  {reasoningCount} {reasoningCount === 1 ? 'note' : 'notes'}
                </Badge>
              ) : null}
            </div>
            {node.description ? (
              <div className="mt-1 text-xs leading-5 text-ds-muted">{node.description}</div>
            ) : null}
            {(startedAt || completedAt) ? (
              <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-ds-muted">
                {startedAt ? <span>Started {startedAt}</span> : null}
                {completedAt ? <span>Finished {completedAt}</span> : null}
              </div>
            ) : null}
            {replanSrText ? (
              <span className="sr-only">{replanSrText}</span>
            ) : null}
          </div>
        </div>
      </button>

      {hasChildren && expanded ? (
        <ol role="group" className="space-y-2 list-none p-0">
          {node.children.map((child, idx) => (
            <PlanNodeRow
              key={child.id}
              node={child}
              depth={depth + 1}
              level={level + 1}
              meta={{ setSize: node.children.length, posInSet: idx + 1 }}
              reduceMotion={reduceMotion}
              highlightFor={highlightFor}
              collapsedIds={collapsedIds}
              focusedId={focusedId}
              onKeyDown={onKeyDown}
              onFocus={onFocus}
              registerRef={registerRef}
            />
          ))}
        </ol>
      ) : null}
    </li>
  );
}

export function PlanTreePanel() {
  const { t } = useI18n();
  const reduceMotion = prefersReducedMotion();
  const planState = useReasoningTraceStore((state) => state.planState);
  const planTree = planState.planTree;
  const createdAt = formatTimestamp(planState.lastCreatedAt);
  const updatedAt = formatTimestamp(planState.lastUpdatedAt);
  const replannedAt = formatTimestamp(planState.lastReplannedAt);
  const nodeCount = planTree == null ? 0 : Math.max(0, countPlanNodes(planTree) - 1);

  const addedSet = useMemo(() => new Set(planState.replanAddedIds), [planState.replanAddedIds]);
  const removedSet = useMemo(() => new Set(planState.replanRemovedIds), [planState.replanRemovedIds]);
  const modifiedSet = useMemo(() => new Set(planState.replanModifiedIds), [planState.replanModifiedIds]);

  const highlightFor = useCallback(
    (id: string): ReplanHighlightFlags => ({
      added: addedSet.has(id),
      removed: removedSet.has(id),
      modified: modifiedSet.has(id),
    }),
    [addedSet, removedSet, modifiedSet],
  );

  // Keyboard nav state — focused node + collapsed parents.
  const [navState, setNavState] = useState<PlanTreeKeyboardState>({
    focusedId: planTree?.id ?? null,
    collapsedIds: new Set<string>(),
  });

  // Make sure focusedId tracks the currently rendered tree's root if the
  // tree has been (re)materialized and the previous focus no longer maps.
  useEffect(() => {
    if (!planTree) return;
    setNavState((prev) => {
      if (prev.focusedId == null) {
        return { ...prev, focusedId: planTree.id };
      }
      return prev;
    });
  }, [planTree]);

  const flatNodes = useMemo(
    () => flattenForKeyboardNav(planTree),
    [planTree],
  );

  const refMap = useRef<Map<string, HTMLButtonElement>>(new Map());
  const registerRef = useCallback((nodeId: string, el: HTMLButtonElement | null) => {
    if (el) {
      refMap.current.set(nodeId, el);
    } else {
      refMap.current.delete(nodeId);
    }
  }, []);

  // After a state update that moves focus, push the DOM focus to the
  // matching button.
  useEffect(() => {
    if (!navState.focusedId) return;
    const el = refMap.current.get(navState.focusedId);
    if (el && document.activeElement !== el && el.tabIndex === 0) {
      // Only re-focus if the user is already navigating inside the tree;
      // do not steal focus on first mount.
      const active = document.activeElement;
      const treeRoot = el.closest('[role="tree"]');
      if (active && treeRoot && treeRoot.contains(active)) {
        el.focus({ preventScroll: false });
      }
    }
  }, [navState.focusedId]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLButtonElement>, _nodeId: string) => {
      if (!KEYBOARD_KEYS.has(event.key)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      setNavState((prev) =>
        planTreeKeyboardNav({
          nodes: flatNodes,
          state: prev,
          key: event.key as PlanTreeKeyboardKey,
        }),
      );
    },
    [flatNodes],
  );

  const handleFocus = useCallback((nodeId: string) => {
    setNavState((prev) => {
      if (prev.focusedId === nodeId) return prev;
      return { ...prev, focusedId: nodeId };
    });
  }, []);

  return (
    <Card className="mb-3 bg-black/10" aria-label={t('run.planTree.ariaLabel')}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-ds-muted">
          <GitBranch size={12} />
          {t('run.planTree.title')}
        </div>
        <Badge compact>
          {t('run.planTree.stageCount', { count: nodeCount })}
        </Badge>
        {createdAt ? (
          <Badge compact>
            {t('run.planTree.created', { time: createdAt })}
          </Badge>
        ) : null}
        {updatedAt ? (
          <Badge compact>
            {t('run.planTree.updated', { time: updatedAt })}
          </Badge>
        ) : null}
        {replannedAt ? (
          <Badge tone="warning" compact>
            {t('run.planTree.replanned', { time: replannedAt })}
          </Badge>
        ) : null}
      </div>

      {planTree == null ? (
        <div className="mt-3 rounded-lg border border-ds-border/70 bg-ds-bg/60 px-3 py-3 text-xs text-ds-muted">
          {t('run.planTree.empty')}
        </div>
      ) : (
        <ol
          className="mt-3 space-y-2 list-none p-0"
          role="tree"
          aria-label={t('run.planTree.nodesAria')}
        >
          <PlanNodeRow
            node={planTree}
            depth={0}
            level={1}
            meta={{ setSize: 1, posInSet: 1 }}
            reduceMotion={reduceMotion}
            highlightFor={highlightFor}
            collapsedIds={navState.collapsedIds}
            focusedId={navState.focusedId}
            onKeyDown={handleKeyDown}
            onFocus={handleFocus}
            registerRef={registerRef}
          />
        </ol>
      )}
    </Card>
  );
}
