import type { MouseEventHandler, ReactElement } from 'react';
import { buildTrustBadgeHref } from '../../application/trust/trustMapper';
import type { TrustBadgeViewModel } from '../../application/trust/trustTypes';
import { Badge } from '../../design-system/primitives';

export interface TrustBadgeProps {
  readonly badge: TrustBadgeViewModel;
  readonly compact?: boolean;
  readonly className?: string;
  readonly onNavigate?: (path: string, badge: TrustBadgeViewModel) => void;
}

const STATUS_TONES = Object.freeze({
  pass: 'success',
  warn: 'warning',
  fail: 'danger',
  pending: 'info',
  unknown: 'neutral',
});

function joinClasses(...classNames: Array<string | null | undefined | false>): string {
  return classNames.filter(Boolean).join(' ');
}

function buildAriaLabel(badge: TrustBadgeViewModel): string {
  const parts = [badge.label, badge.status];
  if (badge.detail) {
    parts.push(badge.detail);
  }
  return parts.join(': ');
}

export function TrustBadge({
  badge,
  compact = false,
  className,
  onNavigate,
}: TrustBadgeProps): ReactElement {
  const href = buildTrustBadgeHref(badge);
  const handleClick: MouseEventHandler<HTMLAnchorElement> = (event) => {
    if (!onNavigate) {
      return;
    }
    event.preventDefault();
    onNavigate(href, badge);
  };

  return (
    <Badge
      as="a"
      href={`#${href}`}
      onClick={handleClick}
      tone={STATUS_TONES[badge.status]}
      compact={compact}
      className={joinClasses(
        'focus-visible:ring-offset-ds-bg hover:border-ds-accent/60 hover:bg-ds-accent/10',
        className,
      )}
      aria-label={buildAriaLabel(badge)}
      data-trust-kind={badge.kind}
      data-trust-status={badge.status}
    >
      {compact || !badge.detail ? badge.label : `${badge.label} - ${badge.detail}`}
    </Badge>
  );
}
