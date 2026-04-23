import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
} from 'react';
import {
  PROMOTE_AUDIENCES,
  type PromoteAudience,
} from '../../application/run/promoteToArtifactPort';
import { Button, DialogShell, Input, Radio } from '../../design-system/primitives';
import { useI18n } from '../../stores/i18nStore';
import { createRuntimeDialogA11yController } from './runtimeDialogA11y';

export interface PromoteDialogDraft {
  readonly audience: PromoteAudience;
  readonly title: string;
}

export const PROMOTE_DIALOG_IDS = {
  shell: 'cards-promote-dialog-shell',
  title: 'cards-promote-dialog-title',
  description: 'cards-promote-dialog-description',
} as const;

export function validatePromoteDialogDraft(
  draft: { audience: string; title: string },
): 'audience_required' | null {
  if (!(PROMOTE_AUDIENCES as readonly string[]).includes(draft.audience.trim().toLowerCase())) {
    return 'audience_required';
  }
  return null;
}

interface Props {
  readonly open: boolean;
  readonly busy?: boolean;
  readonly error?: string | null;
  readonly initialAudience?: PromoteAudience;
  readonly initialTitle?: string;
  readonly onClose: () => void;
  readonly onSubmit: (draft: PromoteDialogDraft) => void | Promise<void>;
}

export function PromoteDialog({
  open,
  busy = false,
  error = null,
  initialAudience = 'ds',
  initialTitle = '',
  onClose,
  onSubmit,
}: Props) {
  const { t } = useI18n();
  const dialogRef = useRef<HTMLElement | null>(null);
  const a11yRef = useRef<ReturnType<typeof createRuntimeDialogA11yController> | null>(null);
  const [audience, setAudience] = useState<PromoteAudience>(initialAudience);
  const [title, setTitle] = useState(initialTitle);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    setAudience(initialAudience);
    setTitle(initialTitle);
    setValidationError(null);
  }, [initialAudience, initialTitle, open]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const element = document.getElementById(PROMOTE_DIALOG_IDS.shell);
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
    const nextDraft = {
      audience,
      title: title.trim(),
    };
    const validation = validatePromoteDialogDraft(nextDraft);
    if (validation === 'audience_required') {
      setValidationError(t('cards:promoteDialog.validation.audienceRequired'));
      return;
    }
    setValidationError(null);
    void onSubmit(nextDraft);
  };

  const footer = (
    <>
      <Button variant="secondary" onClick={handleClose} disabled={busy}>
        {t('cards:promoteDialog.cancel')}
      </Button>
      <Button variant="primary" type="submit" form="promote-dialog-form" disabled={busy}>
        {busy ? t('cards:promoteDialog.confirmBusy') : t('cards:promoteDialog.confirm')}
      </Button>
    </>
  );

  return (
    <DialogShell
      id={PROMOTE_DIALOG_IDS.shell}
      open={open}
      size="sm"
      title={<span id={PROMOTE_DIALOG_IDS.title}>{t('cards:promoteDialog.title')}</span>}
      description={<span id={PROMOTE_DIALOG_IDS.description}>{t('cards:promoteDialog.description')}</span>}
      footer={footer}
      dismissLabel={t('cards:promoteDialog.cancel')}
      onDismiss={busy ? undefined : handleClose}
      onKeyDown={handleKeyDown}
      tabIndex={-1}
    >
      <form id="promote-dialog-form" className="space-y-ds-4" onSubmit={handleSubmit}>
        <fieldset>
          <legend className="text-ds-xs font-medium uppercase tracking-widest text-ds-muted">
            {t('cards:promoteDialog.audienceLabel')}
          </legend>
          <div className="mt-ds-2 grid gap-ds-2 sm:grid-cols-3">
            {PROMOTE_AUDIENCES.map((value) => (
              <Radio
                key={value}
                name="promote-audience"
                value={value}
                checked={audience === value}
                onChange={() => {
                  setAudience(value);
                  setValidationError(null);
                }}
                label={t(`cards:promoteDialog.audience.${value}`)}
                className="rounded-ds-lg border border-ds-border bg-ds-bg px-ds-3 py-ds-2"
              />
            ))}
          </div>
        </fieldset>

        <Input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          label={t('cards:promoteDialog.titleLabel')}
          placeholder={t('cards:promoteDialog.titlePlaceholder')}
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
