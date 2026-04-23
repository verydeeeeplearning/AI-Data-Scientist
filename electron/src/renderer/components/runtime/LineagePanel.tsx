import { useId } from 'react';
import {
  DrawerSurfaceSection,
  DrawerSurfaceSectionTitle,
  ResultCardMetaRow,
  ResultCardSectionPanel,
} from '../../design-system/composites';
import { Badge } from '../../design-system/primitives';
import { cn } from '../../design-system/primitives/utils';
import { useI18n } from '../../stores/i18nStore';

export interface RunLineageEntry {
  readonly runId: string;
  readonly sessionId: string;
  readonly status: string;
  readonly message: string;
  readonly createdAt: number;
  readonly startedAt: number;
  readonly finishedAt?: number | null;
  readonly branchedFromRunId?: string | null;
  readonly rerunFromNodeId?: string | null;
  readonly depth: number;
  readonly isRoot: boolean;
  readonly isSeed: boolean;
}

interface Props {
  readonly loading: boolean;
  readonly error: string | null;
  readonly nodes: readonly RunLineageEntry[];
  readonly activeRunId: string;
}

type BadgeTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info';

function formatDateTime(timestamp?: number | null): string {
  if (!timestamp) {
    return '-';
  }
  return new Date(timestamp * 1000).toLocaleString();
}

function buildDepthPrefix(depth: number): string {
  if (depth <= 0) {
    return '';
  }
  return `${'  '.repeat(Math.max(0, depth - 1))}|- `;
}

function statusTone(status: string): BadgeTone {
  const normalized = status.trim().toLowerCase();
  if (normalized === 'running') {
    return 'accent';
  }
  if (normalized === 'succeeded' || normalized === 'completed') {
    return 'success';
  }
  if (normalized === 'failed') {
    return 'danger';
  }
  if (normalized === 'cancelled' || normalized === 'canceled') {
    return 'warning';
  }
  return 'neutral';
}

export function LineagePanel({ loading, error, nodes, activeRunId }: Props) {
  const { t } = useI18n();
  const titleId = useId();
  const descriptionId = `${titleId}-description`;

  return (
    <DrawerSurfaceSection
      className="space-y-ds-3"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
    >
      <div className="space-y-ds-1">
        <DrawerSurfaceSectionTitle id={titleId}>
          {t('run:lineage.title')}
        </DrawerSurfaceSectionTitle>
        <p id={descriptionId} className="text-ds-xs text-ds-muted">
          {t('run:lineage.description')}
        </p>
      </div>

      {loading ? (
        <p className="text-ds-xs text-ds-muted" role="status" aria-live="polite">
          {t('run:lineage.loading')}
        </p>
      ) : error ? (
        <p className="text-ds-xs text-ds-error" role="alert">
          {t('run:lineage.error', { reason: error })}
        </p>
      ) : nodes.length === 0 ? (
        <p className="text-ds-xs text-ds-muted" role="status" aria-live="polite">
          {t('run:lineage.empty')}
        </p>
      ) : (
        <ul className="space-y-ds-2">
          {nodes.map((node) => {
            const isActive = node.runId === activeRunId;
            return (
              <li
                key={node.runId}
                style={{ marginLeft: `${node.depth * 0.75}rem` }}
                aria-current={isActive ? 'true' : undefined}
              >
                <ResultCardSectionPanel
                  className={cn(
                    'space-y-ds-2',
                    isActive ? 'border-ds-accent/40 bg-ds-accent/10' : 'bg-ds-surface/60',
                  )}
                >
                  <ResultCardMetaRow>
                    <span className="font-mono text-ds-text">
                      {buildDepthPrefix(node.depth)}
                      {node.runId}
                    </span>
                    {node.isRoot && (
                      <Badge compact tone="neutral">
                        {t('run:lineage.badge.root')}
                      </Badge>
                    )}
                    {node.isSeed && (
                      <Badge compact tone="accent">
                        {t('run:lineage.badge.current')}
                      </Badge>
                    )}
                    {node.rerunFromNodeId ? (
                      <Badge compact tone="warning">
                        {t('run:lineage.badge.rerun')}
                      </Badge>
                    ) : node.branchedFromRunId ? (
                      <Badge compact tone="neutral">
                        {t('run:lineage.badge.branch')}
                      </Badge>
                    ) : null}
                    <Badge compact tone={statusTone(node.status)} className="uppercase">
                      {node.status}
                    </Badge>
                  </ResultCardMetaRow>

                  <p className="text-ds-sm text-ds-text">{node.message || '-'}</p>

                  <ResultCardMetaRow className="gap-x-ds-2 gap-y-ds-1 text-[11px]">
                    <span>{formatDateTime(node.createdAt)}</span>
                    <span>{t('run:lineage.meta.session', { sessionId: node.sessionId })}</span>
                    {node.rerunFromNodeId && (
                      <span>
                        {t('run:lineage.meta.rerunFrom', { nodeId: node.rerunFromNodeId })}
                      </span>
                    )}
                  </ResultCardMetaRow>
                </ResultCardSectionPanel>
              </li>
            );
          })}
        </ul>
      )}
    </DrawerSurfaceSection>
  );
}
