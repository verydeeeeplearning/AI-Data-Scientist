/**
 * Tool activity surface — feature-flagged shell that picks between the new
 * stage-based ExecutionTimeline (W1-F) and the legacy raw tool list
 * (`LegacyToolActivity`). The hook `useExecutionTimeline` owns aggregation +
 * stage transition memoization so multiple consumers stay in sync.
 */

import { useEffect, useRef } from 'react';
import { announce } from '../../application/a11y/ariaLive';
import { useExecutionTimeline } from '../../hooks/useExecutionTimeline';
import { useChatStore, type ToolActivity as ToolActivityType } from '../../stores/chatStore';
import { useConfigStore } from '../../stores/configStore';
import { useI18n } from '../../stores/i18nStore';
import { ExecutionTimeline } from '../runtime/ExecutionTimeline';
import { LegacyToolActivity } from './LegacyToolActivity';

interface Props {
  activities: ToolActivityType[];
}

function selectLatestAssistantMessageId(): string | null {
  const messages = useChatStore.getState().messages;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === 'assistant') {
      return messages[index].id;
    }
  }
  return null;
}

export function ToolActivity({ activities }: Props) {
  const useNewTimeline = useConfigStore((state) => state.useNewExecutionTimeline);
  const t = useI18n((state) => state.t);
  const messages = useChatStore((state) => state.messages);
  const snapshot = useExecutionTimeline({ activitiesOverride: activities });
  const lastAnnouncementRef = useRef<string>('');

  useEffect(() => {
    if (!useNewTimeline) {
      return;
    }
    const transition = snapshot.latestTransition;
    if (!transition) {
      lastAnnouncementRef.current = '';
      return;
    }
    const key = `${transition.stageKey}:${transition.status}:${transition.toolEventCount}`;
    if (lastAnnouncementRef.current === key) {
      return;
    }
    lastAnnouncementRef.current = key;

    const stage = snapshot.currentStage;
    if (!stage) {
      return;
    }
    const stageLabel = t(`execution.stage.${stage.key}`) || stage.label;

    if (transition.status === 'running') {
      announce(t('execution.announce.started', { label: stageLabel }), { politeness: 'polite' });
      return;
    }
    if (transition.status === 'completed') {
      announce(t('execution.announce.completed', { label: stageLabel }), { politeness: 'polite' });
      return;
    }
    if (transition.status === 'failed') {
      announce(t('execution.announce.failed', { label: stageLabel }), { politeness: 'assertive' });
    }
  }, [snapshot.latestTransition, snapshot.currentStage, useNewTimeline, t]);

  if (!useNewTimeline) {
    return <LegacyToolActivity activities={activities} />;
  }

  if (snapshot.stages.length === 0) {
    return null;
  }

  // Re-derive latest assistant id from store snapshot used in render path.
  const latestAssistantMessageId = (() => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      if (messages[index].role === 'assistant') {
        return messages[index].id;
      }
    }
    return selectLatestAssistantMessageId();
  })();

  return (
    <div className="border-t border-ds-border bg-ds-surface/30">
      <ExecutionTimeline
        stages={snapshot.stages}
        defaultExpandedKeys={snapshot.stages
          .filter((stage) => stage.status === 'running')
          .map((stage) => stage.key)}
        emptyLabel={t('execution.empty_tools')}
        latestAssistantMessageId={latestAssistantMessageId}
      />
    </div>
  );
}
