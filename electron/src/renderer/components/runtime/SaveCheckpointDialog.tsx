import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import { Button, DialogShell, Input, Textarea } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import { createRuntimeDialogA11yController } from './runtimeDialogA11y';

export interface SaveCheckpointDraft {
  readonly name: string;
  readonly description: string;
}

export const SAVE_CHECKPOINT_DIALOG_IDS = {
  shell: 'run-save-checkpoint-shell',
  title: 'run-save-checkpoint-title',
  description: 'run-save-checkpoint-description',
} as const;

export function validateSaveCheckpointDraft(
  draft: SaveCheckpointDraft,
): 'name_required' | null {
  if (!draft.name.trim()) {
    return 'name_required';
  }
  return null;
}

interface Props {
  readonly open: boolean;
  readonly busy?: boolean;
  readonly error?: string | null;
  readonly initialName?: string;
  readonly initialDescription?: string;
  readonly onClose: () => void;
  readonly onSubmit: (draft: SaveCheckpointDraft) => void | Promise<void>;
}

export function SaveCheckpointDialog({
  open,
  busy = false,
  error = null,
  initialName = '',
  initialDescription = '',
  onClose,
  onSubmit,
}: Props) {
  const { t } = useI18n();
  const dialogRef = useRef<HTMLElement | null>(null);
  const a11yRef = useRef<ReturnType<typeof createRuntimeDialogA11yController> | null>(null);
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    setName(initialName);
    setDescription(initialDescription);
    setValidationError(null);
  }, [initialDescription, initialName, open]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const element = document.getElementById(SAVE_CHECKPOINT_DIALOG_IDS.shell);
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
    const nextDraft: SaveCheckpointDraft = {
      name: name.trim(),
      description: description.trim(),
    };
    const validation = validateSaveCheckpointDraft(nextDraft);
    if (validation === 'name_required') {
      setValidationError(t('run:checkpointDialog.validation.nameRequired'));
      return;
    }
    setValidationError(null);
    void onSubmit(nextDraft);
  };

  const footer = (
    <>
      <Button variant="secondary" onClick={handleClose} disabled={busy}>
        {t('run:checkpointDialog.cancel')}
      </Button>
      <Button variant="primary" type="submit" form="save-checkpoint-dialog-form" disabled={busy}>
        {busy
          ? t('run:checkpointDialog.confirmBusy')
          : t('run:checkpointDialog.confirm')}
      </Button>
    </>
  );

  return (
    <DialogShell
      id={SAVE_CHECKPOINT_DIALOG_IDS.shell}
      open={open}
      size="sm"
      title={<span id={SAVE_CHECKPOINT_DIALOG_IDS.title}>{t('run:checkpointDialog.title')}</span>}
      description={<span id={SAVE_CHECKPOINT_DIALOG_IDS.description}>{t('run:checkpointDialog.description')}</span>}
      footer={footer}
      dismissLabel={t('run:checkpointDialog.cancel')}
      onDismiss={busy ? undefined : handleClose}
      onKeyDown={handleKeyDown}
      tabIndex={-1}
    >
      <form id="save-checkpoint-dialog-form" className="space-y-ds-4" onSubmit={handleSubmit}>
        <Input
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            setValidationError(null);
          }}
          label={t('run:checkpointDialog.nameLabel')}
          placeholder={t('run:checkpointDialog.namePlaceholder')}
        />

        <Textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          label={t('run:checkpointDialog.descriptionLabel')}
          placeholder={t('run:checkpointDialog.descriptionPlaceholder')}
          rows={3}
        />

        {visibleError && (
          <div className="text-ds-sm text-rose-300" role="alert">
            {visibleError}
          </div>
        )}
      </form>
    </DialogShell>
  );
}
