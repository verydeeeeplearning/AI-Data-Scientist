import { useCallback } from 'react';
import { announce } from '../application/a11y/ariaLive';
import {
  buildSuggestedActionPrompt,
  isSuggestedActionAvailable,
} from '../application/workspace/buildSuggestedActionPrompt';
import type {
  UploadedFileSchemaPreview,
  UploadedFileSuggestedAction,
} from '../domain/workspace/uploadedFile';
import { useConfigStore } from '../stores/configStore';
import { useI18n } from '../stores/i18nStore';

interface TriggerArgs {
  action: UploadedFileSuggestedAction;
  preview: UploadedFileSchemaPreview;
}

interface TriggerResult {
  prompt: string | null;
  available: boolean;
}

export function useSuggestedAction() {
  const setPendingStarterPrompt = useConfigStore((s) => s.setPendingStarterPrompt);
  const { t } = useI18n();

  const triggerSuggestedAction = useCallback(
    ({ action, preview }: TriggerArgs): TriggerResult => {
      if (!isSuggestedActionAvailable(action, preview)) {
        return { prompt: null, available: false };
      }

      const prompt = buildSuggestedActionPrompt(action, preview);
      setPendingStarterPrompt(prompt);
      announce(
        t('workspace.upload.suggestedActions.queued', {
          label: t(action.label),
        }),
      );
      return { prompt, available: true };
    },
    [setPendingStarterPrompt, t],
  );

  return { triggerSuggestedAction };
}
