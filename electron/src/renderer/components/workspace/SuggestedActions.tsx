import { Bot, ShieldCheck, Target } from 'lucide-react';
import { isSuggestedActionAvailable } from '../../application/workspace/buildSuggestedActionPrompt';
import { Button } from '../../design-system/primitives';
import { cn } from '../../design-system/primitives/utils';
import type {
  UploadedFileSchemaPreview,
  UploadedFileSuggestedAction,
} from '../../domain/workspace/uploadedFile';
import { useSuggestedAction } from '../../hooks/useSuggestedAction';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  preview: UploadedFileSchemaPreview;
}

function iconFor(action: UploadedFileSuggestedAction['icon']) {
  if (action === 'target') {
    return Target;
  }
  if (action === 'shield') {
    return ShieldCheck;
  }
  return Bot;
}

export function SuggestedActions({ preview }: Props) {
  const { t } = useI18n();
  const { triggerSuggestedAction } = useSuggestedAction();
  const actions = preview.suggestedActions;
  const sectionId = `suggested-actions-${preview.fileId}`;

  if (actions.length === 0) {
    return null;
  }

  return (
    <div className="space-y-ds-2">
      <div id={sectionId} className="text-[10px] uppercase tracking-[0.18em] text-ds-muted">
        {t('workspace.upload.suggestedActions.title')}
      </div>
      <div role="group" aria-labelledby={sectionId} className="space-y-ds-2">
        {actions.map((action) => {
          const Icon = iconFor(action.icon);
          const available = isSuggestedActionAvailable(action, preview);
          const blockingReason = available
            ? null
            : t('workspace.upload.suggestedActions.targetRequired');
          const descriptionId = `${preview.fileId}-${action.id}-description`;
          const blockingReasonId = `${preview.fileId}-${action.id}-blocking`;

          return (
            <Button
              key={action.id}
              variant="ghost"
              size="md"
              disabled={!available}
              aria-disabled={!available}
              aria-describedby={
                blockingReason ? `${descriptionId} ${blockingReasonId}` : descriptionId
              }
              title={blockingReason ?? t(action.description)}
              onClick={() => {
                triggerSuggestedAction({ action, preview });
              }}
              leadingIcon={
                <Icon size={14} className="mt-[1px] shrink-0 text-ds-accent" aria-hidden="true" />
              }
              className={cn(
                'h-auto w-full items-start justify-start rounded-ds-xl border border-ds-border bg-ds-bg/50 px-ds-4 py-ds-3 text-left shadow-none',
                'hover:border-ds-accent/60 hover:bg-ds-accent/10',
                'disabled:hover:border-ds-border disabled:hover:bg-ds-bg/50',
              )}
            >
              <span className="flex min-w-0 flex-1 flex-col items-start text-left">
                <span className="text-ds-xs font-semibold text-ds-text">{t(action.label)}</span>
                <span id={descriptionId} className="mt-ds-1 text-ds-xs leading-5 text-ds-muted">
                  {t(action.description)}
                </span>
                {blockingReason && (
                  <span id={blockingReasonId} className="mt-ds-1 text-ds-xs text-ds-warning">
                    {blockingReason}
                  </span>
                )}
              </span>
            </Button>
          );
        })}
      </div>
    </div>
  );
}
