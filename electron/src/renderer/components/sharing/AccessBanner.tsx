/**
 * AccessBanner — viewer-only read-only notice rendered above the resource
 * surface. Owners never see it. Viewers see a single-line explanation plus
 * the resource owner reference so the read-only state is unambiguous.
 */

import { Eye } from 'lucide-react';
import type { ReactElement } from 'react';

import { useAccessRole, type ViewerRole } from '../../hooks/useAccessRole';
import { useI18n } from '../../stores/i18nStore';

export interface AccessBannerProps {
  readonly ownerLabel?: string;
  readonly forceRole?: ViewerRole;
  readonly className?: string;
}

export function AccessBanner({
  ownerLabel,
  forceRole,
  className,
}: AccessBannerProps): ReactElement | null {
  const { isViewer } = useAccessRole({ forceRole });
  const { t } = useI18n();

  if (!isViewer) {
    return null;
  }

  const labelText = ownerLabel
    ? t('share.banner.ownerLabel', { owner: ownerLabel })
    : null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={[
        'flex items-center gap-ds-2 rounded-ds-md border border-ds-border bg-ds-surface px-ds-3 py-ds-2 text-ds-xs text-ds-muted',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <Eye size={14} className="shrink-0 text-ds-muted" aria-hidden="true" />
      <span className="font-medium text-ds-text">{t('share.banner.viewerOnly')}</span>
      {labelText ? <span className="truncate text-ds-muted">{labelText}</span> : null}
    </div>
  );
}
