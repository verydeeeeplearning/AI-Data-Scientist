import { ActivitySquare } from 'lucide-react';
import { useState } from 'react';
import type { Stage, StageKey } from '../../domain/execution/stage';
import { useReasoningTraceBridge } from '../../hooks/useReasoningTrace';
import { useI18n } from '../../stores/i18nStore';
import { PlanTreePanel } from './PlanTreePanel';
import { StageRow } from './StageRow';

interface Props {
  stages: readonly Stage[];
  defaultExpandedKeys?: readonly StageKey[];
  emptyLabel?: string;
  latestAssistantMessageId?: string | null;
}

function createInitialExpanded(keys: readonly StageKey[] | undefined): Set<StageKey> {
  return new Set(keys ?? []);
}

export function ExecutionTimeline({
  stages,
  defaultExpandedKeys,
  emptyLabel,
  latestAssistantMessageId,
}: Props) {
  const t = useI18n((state) => state.t);
  const [expandedKeys, setExpandedKeys] = useState(() => createInitialExpanded(defaultExpandedKeys));
  useReasoningTraceBridge(true);

  const toggle = (key: StageKey) => {
    setExpandedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const fallbackEmpty = emptyLabel ?? t('execution.empty');

  return (
    <section
      className="px-3 py-2"
      aria-label={t('execution.title')}
    >
      <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-ds-muted">
        <ActivitySquare size={12} aria-hidden="true" />
        {t('execution.title')}
        <span className="ml-auto text-xs normal-case text-ds-text">{stages.length}</span>
      </div>

      <PlanTreePanel />

      {stages.length === 0 ? (
        <div className="rounded-md border border-ds-border bg-ds-bg/60 px-3 py-2 text-xs text-ds-muted">
          {fallbackEmpty}
        </div>
      ) : (
        <ol className="space-y-2 list-none p-0">
          {stages.map((stage) => (
            <li key={stage.key}>
              <StageRow
                stage={stage}
                expanded={expandedKeys.has(stage.key)}
                onToggle={() => toggle(stage.key)}
                latestAssistantMessageId={latestAssistantMessageId ?? null}
              />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
