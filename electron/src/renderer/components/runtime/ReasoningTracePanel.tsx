import { useCallback, useId, useMemo } from 'react';
import { BrainCircuit, GitBranchPlus } from 'lucide-react';
import type { StageKey } from '../../domain/execution/stage';
import {
  DrawerSurfaceSection,
  DrawerSurfaceSectionTitle,
  ResultCardMetaRow,
  ResultCardPillButton,
  ResultCardSectionPanel,
  ResultCardSectionTitle,
} from '../../design-system/composites';
import { Badge } from '../../design-system/primitives';
import type { PlanNode } from '../../types/events';
import { useStageReasoningTrace } from '../../hooks/useReasoningTrace';
import { planTreeNodeDomId } from './PlanTreePanel';

interface Props {
  readonly stageKey: StageKey;
}

function formatTimestamp(value: number): string {
  return new Date(value).toLocaleTimeString();
}

function buildPlanNodeLabelIndex(node: PlanNode | null): Map<string, string> {
  const index = new Map<string, string>();
  if (!node) return index;
  function walk(current: PlanNode): void {
    index.set(current.id, current.label);
    for (const child of current.children) {
      walk(child);
    }
  }
  walk(node);
  return index;
}

function TraceSection({
  title,
  value,
}: {
  title: string;
  value?: string;
}) {
  if (!value) {
    return null;
  }

  return (
    <ResultCardSectionPanel className="space-y-ds-2 bg-ds-surface/60">
      <ResultCardSectionTitle>{title}</ResultCardSectionTitle>
      <div className="whitespace-pre-wrap text-ds-xs leading-5 text-ds-text">
        {value}
      </div>
    </ResultCardSectionPanel>
  );
}

export function ReasoningTracePanel({ stageKey }: Props) {
  const { traces, planState } = useStageReasoningTrace(stageKey);
  const titleId = useId();
  const planNodeLabels = useMemo(
    () => buildPlanNodeLabelIndex(planState.planTree),
    [planState.planTree],
  );

  // Focus the matching plan-tree treeitem when the user clicks the
  // planNodeId chip. Implemented via a DOM id lookup so we do not need a
  // shared focus store between the two panels.
  const focusPlanNode = useCallback((planNodeId: string) => {
    if (typeof document === 'undefined') return;
    const target = document.getElementById(planTreeNodeDomId(planNodeId));
    if (target instanceof HTMLElement) {
      target.focus({ preventScroll: false });
      target.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, []);

  return (
    <DrawerSurfaceSection
      className="mt-ds-3 space-y-ds-3"
      role="region"
      aria-labelledby={titleId}
    >
      <div className="flex flex-wrap items-center gap-ds-2">
        <div className="inline-flex items-center gap-ds-2">
          <BrainCircuit size={12} className="text-ds-muted" aria-hidden="true" />
          <DrawerSurfaceSectionTitle id={titleId}>
            Reasoning Trace
          </DrawerSurfaceSectionTitle>
        </div>
        <Badge compact tone="neutral">
          {traces.length} item{traces.length === 1 ? '' : 's'}
        </Badge>
        {planState.lastReplannedAt ? (
          <Badge
            compact
            tone="warning"
            leadingIcon={<GitBranchPlus size={10} aria-hidden="true" />}
          >
            Replanned {formatTimestamp(planState.lastReplannedAt)}
          </Badge>
        ) : null}
      </div>

      {planState.lastReplanReason ? (
        <ResultCardSectionPanel className="border-ds-warning/30 bg-ds-warning/10 text-ds-warning">
          <p className="text-ds-xs">{planState.lastReplanReason}</p>
        </ResultCardSectionPanel>
      ) : null}

      {traces.length === 0 ? (
        <ResultCardSectionPanel role="status" aria-live="polite">
          <p className="text-ds-xs text-ds-muted">
            No reasoning trace has been captured for this stage yet.
          </p>
        </ResultCardSectionPanel>
      ) : (
        <div className="space-y-ds-3">
          {traces.map((trace) => {
            const planNodeId = trace.planNodeId;
            const planNodeLabel = planNodeId
              ? planNodeLabels.get(planNodeId)
              : undefined;
            return (
              <article
                key={trace.id}
                id={`reasoning-trace-${trace.id}`}
                aria-label={`Trace emitted at ${formatTimestamp(trace.emittedAt)}`}
              >
                <ResultCardSectionPanel className="space-y-ds-3">
                  <ResultCardMetaRow>
                    <span>{formatTimestamp(trace.emittedAt)}</span>
                    {planNodeId ? (
                      <ResultCardPillButton
                        onClick={() => focusPlanNode(planNodeId)}
                        className="border-ds-accent/30 bg-ds-accent/10 text-ds-accent hover:bg-ds-accent/20"
                        title={`Jump to plan node ${planNodeId}`}
                        aria-label={
                          planNodeLabel
                            ? `Jump to plan node ${planNodeLabel} (${planNodeId})`
                            : `Jump to plan node ${planNodeId}`
                        }
                      >
                        <span className="font-mono">{planNodeId}</span>
                        {planNodeLabel ? (
                          <span className="text-ds-accent/80"> - {planNodeLabel}</span>
                        ) : null}
                      </ResultCardPillButton>
                    ) : null}
                  </ResultCardMetaRow>

                  {trace.thinking ? (
                    <ResultCardSectionPanel className="space-y-ds-2 border-ds-accent/20 bg-ds-accent/5">
                      <ResultCardSectionTitle>Thinking</ResultCardSectionTitle>
                      <div className="whitespace-pre-wrap text-ds-xs leading-5 text-ds-text">
                        {trace.thinking}
                      </div>
                    </ResultCardSectionPanel>
                  ) : null}

                  <div className="grid gap-ds-2 md:grid-cols-2">
                    <TraceSection title="Hypothesis" value={trace.hypothesis} />
                    <TraceSection title="Action" value={trace.action} />
                    <TraceSection title="Observation" value={trace.observation} />
                    <TraceSection title="Decision" value={trace.decision} />
                  </div>
                </ResultCardSectionPanel>
              </article>
            );
          })}
        </div>
      )}
    </DrawerSurfaceSection>
  );
}
