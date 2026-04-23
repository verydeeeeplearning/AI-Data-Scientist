import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { Button, DialogShell, Select, Textarea } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import { createRuntimeDialogA11yController } from './runtimeDialogA11y';

export interface BranchRunDraft {
  readonly message: string;
  readonly model: string | null;
}

export interface BranchRunDialogModelOption {
  readonly value: string;
  readonly label: string;
}

export const BRANCH_RUN_DIALOG_IDS = {
  shell: 'run-branch-dialog-shell',
  title: 'run-branch-dialog-title',
  description: 'run-branch-dialog-description',
} as const;

export function validateBranchRunDraft(
  draft: BranchRunDraft,
): 'message_required' | null {
  if (!draft.message.trim()) {
    return 'message_required';
  }
  return null;
}

interface Props {
  readonly open: boolean;
  readonly busy?: boolean;
  readonly error?: string | null;
  readonly initialMessage?: string;
  readonly initialModel?: string | null;
  readonly modelOptions: readonly BranchRunDialogModelOption[];
  readonly onClose: () => void;
  readonly onSubmit: (draft: BranchRunDraft) => void | Promise<void>;
}

export function BranchRunDialog({
  open,
  busy = false,
  error = null,
  initialMessage = '',
  initialModel = null,
  modelOptions,
  onClose,
  onSubmit,
}: Props) {
  const { t } = useI18n();
  const a11yRef = useRef<ReturnType<typeof createRuntimeDialogA11yController> | null>(null);
  const [message, setMessage] = useState(initialMessage);
  const [model, setModel] = useState(initialModel ?? '');
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    setMessage(initialMessage);
    setModel(initialModel ?? '');
    setValidationError(null);
  }, [initialMessage, initialModel, open]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const element = document.getElementById(BRANCH_RUN_DIALOG_IDS.shell);
    if (!(element instanceof HTMLElement)) {
      return undefined;
    }
    const controller = createRuntimeDialogA11yController(element);
    a11yRef.current = controller;
    controller.activate();
    return () => {
      controller.deactivate();
      a11yRef.current = null;
    };
  }, [open]);

  if (!open) {
    return null;
  }

  const visibleError = validationError ?? error;

  const handleClose = () => {
    if (!busy) {
      onClose();
    }
  };

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const action = a11yRef.current?.handleKeyDown(event.nativeEvent);
    if (action === 'escape') {
      handleClose();
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextDraft: BranchRunDraft = {
      message: message.trim(),
      model: model.trim() ? model.trim() : null,
    };
    const validation = validateBranchRunDraft(nextDraft);
    if (validation === 'message_required') {
      setValidationError(t('run:branchDialog.validation.messageRequired'));
      return;
    }
    setValidationError(null);
    void onSubmit(nextDraft);
  };

  return (
    <DialogShell
      id={BRANCH_RUN_DIALOG_IDS.shell}
      open={open}
      size="sm"
      className="max-w-xl rounded-3xl"
      title={<span id={BRANCH_RUN_DIALOG_IDS.title}>{t('run:branchDialog.title')}</span>}
      description={<span id={BRANCH_RUN_DIALOG_IDS.description}>{t('run:branchDialog.description')}</span>}
      onKeyDown={handleKeyDown}
      tabIndex={-1}
      aria-describedby={BRANCH_RUN_DIALOG_IDS.description}
      footer={(
        <>
          <Button variant="secondary" onClick={handleClose} disabled={busy}>
            {t('run:branchDialog.cancel')}
          </Button>
          <Button variant="primary" type="submit" form="branch-run-dialog-form" disabled={busy}>
            {busy ? t('run:branchDialog.confirmBusy') : t('run:branchDialog.confirm')}
          </Button>
        </>
      )}
    >
      <form id="branch-run-dialog-form" className="space-y-ds-4" onSubmit={handleSubmit}>
        <Textarea
          id="run-branch-dialog-message"
          value={message}
          onChange={(event) => {
            setMessage(event.target.value);
            setValidationError(null);
          }}
          label={t('run:branchDialog.messageLabel')}
          placeholder={t('run:branchDialog.messagePlaceholder')}
          rows={5}
        />

        <Select
          id="run-branch-dialog-model"
          value={model}
          onChange={(event) => setModel(event.target.value)}
          label={t('run:branchDialog.modelLabel')}
          options={[
            { value: '', label: t('run:branchDialog.modelPlaceholder') },
            ...modelOptions,
          ]}
        />

        {visibleError && (
          <div className="text-ds-sm text-ds-error" role="alert">
            {visibleError}
          </div>
        )}
      </form>
    </DialogShell>
  );
}
