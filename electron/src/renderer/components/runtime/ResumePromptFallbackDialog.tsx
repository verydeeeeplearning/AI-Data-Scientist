import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { Button, DialogShell, Textarea } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import { createRuntimeDialogA11yController } from './runtimeDialogA11y';

export const RESUME_PROMPT_FALLBACK_DIALOG_IDS = {
  shell: 'run-resume-fallback-shell',
  title: 'run-resume-fallback-title',
  description: 'run-resume-fallback-description',
  prompt: 'run-resume-fallback-prompt',
} as const;

interface Props {
  readonly open: boolean;
  readonly prompt: string;
  readonly errorDetail: string | null;
  readonly clipboardCopied: boolean;
  readonly onCopy: () => void | Promise<void>;
  readonly onClose: () => void;
}

export function ResumePromptFallbackDialog({
  open,
  prompt,
  errorDetail,
  clipboardCopied,
  onCopy,
  onClose,
}: Props) {
  const { t } = useI18n();
  const dialogRef = useRef<HTMLElement | null>(null);
  const a11yRef = useRef<ReturnType<typeof createRuntimeDialogA11yController> | null>(null);
  const [copyJustClicked, setCopyJustClicked] = useState(false);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const element = document.getElementById(RESUME_PROMPT_FALLBACK_DIALOG_IDS.shell);
    if (!(element instanceof HTMLElement)) {
      return undefined;
    }
    dialogRef.current = element;
    const controller = createRuntimeDialogA11yController(element);
    a11yRef.current = controller;
    controller.activate();
    return () => {
      controller.deactivate();
      a11yRef.current = null;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      setCopyJustClicked(false);
      return;
    }
    const handle = window.setTimeout(() => {
      const promptField = document.getElementById(
        RESUME_PROMPT_FALLBACK_DIALOG_IDS.prompt,
      );
      if (promptField instanceof HTMLTextAreaElement) {
        promptField.select();
      }
    }, 0);
    return () => window.clearTimeout(handle);
  }, [open]);

  if (!open) {
    return null;
  }

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const action = a11yRef.current?.handleKeyDown(event.nativeEvent);
    if (action === 'escape') {
      onClose();
    }
  };

  const handleCopyClick = async () => {
    setCopyJustClicked(true);
    await onCopy();
  };

  const footer = (
    <>
      <Button variant="secondary" onClick={onClose}>
        {t('run:resumeFallback.close')}
      </Button>
      <Button variant="primary" onClick={() => void handleCopyClick()}>
        {t('run:resumeFallback.copy')}
      </Button>
    </>
  );

  return (
    <DialogShell
      id={RESUME_PROMPT_FALLBACK_DIALOG_IDS.shell}
      open={open}
      size="md"
      title={<span id={RESUME_PROMPT_FALLBACK_DIALOG_IDS.title}>{t('run:resumeFallback.title')}</span>}
      description={
        <span id={RESUME_PROMPT_FALLBACK_DIALOG_IDS.description}>
          {errorDetail
            ? t('run:resumeFallback.descriptionWithReason', { reason: errorDetail })
            : t('run:resumeFallback.description')}
        </span>
      }
      footer={footer}
      dismissLabel={t('run:resumeFallback.close')}
      onDismiss={onClose}
      onKeyDown={handleKeyDown}
      tabIndex={-1}
    >
      <div className="space-y-ds-4">
        <Textarea
          id={RESUME_PROMPT_FALLBACK_DIALOG_IDS.prompt}
          value={prompt}
          readOnly
          rows={6}
          label={t('run:resumeFallback.promptLabel')}
          className="font-mono"
          resize="none"
        />

        <div
          className={`text-ds-sm ${
            copyJustClicked && clipboardCopied ? 'text-emerald-400' : 'text-ds-muted'
          }`}
          role="status"
          aria-live="polite"
        >
          {copyJustClicked
            ? clipboardCopied
              ? t('run:resumeFallback.copySucceeded')
              : t('run:resumeFallback.copyFailed')
            : t('run:resumeFallback.copyHint')}
        </div>
      </div>
    </DialogShell>
  );
}
