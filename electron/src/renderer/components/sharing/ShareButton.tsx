/**
 * ShareButton — owner-only control that copies a deep-link URL for the
 * current resource into the clipboard and announces the result via toast.
 *
 * The button is rendered ONLY for the resource owner. Viewers do not need —
 * and per ADR D-W4-3 are not allowed — to share resources.
 */

import { Share2 } from 'lucide-react';
import { useCallback, useState, type ReactElement } from 'react';

import {
  buildShareUrl,
  type ShareableResourceType,
} from '../../application/sharing/buildShareUrl';
import { Button, Toast, ToastViewport } from '../../design-system/primitives';
import { useAccessRole, type ViewerRole } from '../../hooks/useAccessRole';
import { useI18n } from '../../stores/i18nStore';

export interface ShareButtonProps {
  readonly resourceType: ShareableResourceType;
  readonly resourceId: string;
  readonly baseUrl?: string;
  readonly forceRole?: ViewerRole;
  readonly className?: string;
}

const TOAST_DISMISS_MS = 4_000;

async function copyToClipboard(value: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch {
    // fall through to legacy path below
  }
  if (typeof document === 'undefined') return false;
  try {
    const textarea = document.createElement('textarea');
    textarea.value = value;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}

export function ShareButton({
  resourceType,
  resourceId,
  baseUrl,
  forceRole,
  className,
}: ShareButtonProps): ReactElement | null {
  const { isOwner } = useAccessRole({ forceRole });
  const { t } = useI18n();
  const [toastOpen, setToastOpen] = useState(false);

  const handleClick = useCallback(async (): Promise<void> => {
    const { url } = buildShareUrl({ resourceType, resourceId, baseUrl });
    const ok = await copyToClipboard(url);
    if (!ok) return;
    setToastOpen(true);
    window.setTimeout(() => setToastOpen(false), TOAST_DISMISS_MS);
  }, [baseUrl, resourceId, resourceType]);

  if (!isOwner) {
    return null;
  }

  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        leadingIcon={<Share2 size={14} aria-hidden="true" />}
        onClick={() => void handleClick()}
        title={t('share.button.copy')}
        aria-label={t('share.button.copy')}
        className={className}
      >
        {t('share.button.copy')}
      </Button>
      {toastOpen ? (
        <ToastViewport placement="bottom-right" label={t('share.button.copied')}>
          <Toast
            title={t('share.button.copied')}
            tone="success"
            announce="polite"
            onDismiss={() => setToastOpen(false)}
            dismissLabel={t('share.button.copied')}
          />
        </ToastViewport>
      ) : null}
    </>
  );
}
