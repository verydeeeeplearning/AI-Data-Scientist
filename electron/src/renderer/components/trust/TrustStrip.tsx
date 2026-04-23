import type { ReactElement, ReactNode } from 'react';
import { Button, Card } from '../../design-system/primitives';
import { TrustBadge } from './TrustBadge';
import { useResultCardTrust } from '../../hooks/useResultCardTrust';
import type { TrustBadgeViewModel } from '../../application/trust/trustTypes';

export interface TrustStripProps {
  readonly resultId: string | null | undefined;
  readonly initialData?: unknown;
  readonly autoLoad?: boolean;
  readonly compact?: boolean;
  readonly maxBadges?: number;
  readonly className?: string;
  readonly emptyState?: ReactNode;
  readonly onNavigate?: (path: string, badge: TrustBadgeViewModel) => void;
}

function joinClasses(...classNames: Array<string | null | undefined | false>): string {
  return classNames.filter(Boolean).join(' ');
}

function LoadingSkeleton({ compact }: { compact: boolean }): ReactElement {
  return (
    <div className="flex flex-wrap items-center gap-2" aria-hidden="true">
      {Array.from({ length: compact ? 2 : 3 }, (_, index) => (
        <span
          // eslint-disable-next-line react/no-array-index-key
          key={`trust-skeleton-${index}`}
          className="inline-block h-8 w-24 animate-pulse rounded-full border border-slate-700/70 bg-slate-800/60"
        />
      ))}
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}): ReactElement {
  return (
    <div className="flex items-center gap-ds-3 text-ds-xs text-ds-error">
      <span className="truncate">{message}</span>
      <Button type="button" size="sm" variant="danger" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

export function TrustStrip({
  resultId,
  initialData,
  autoLoad = true,
  compact = false,
  maxBadges,
  className,
  emptyState,
  onNavigate,
}: TrustStripProps): ReactElement | null {
  const { badges, error, isError, isIdle, isLoading, load } = useResultCardTrust(resultId, {
    enabled: autoLoad,
    initialData,
  });

  if (!resultId) {
    return null;
  }

  if (isIdle && !autoLoad && badges.length === 0) {
    return (
      <Card
        className={joinClasses('flex items-center gap-ds-3 px-ds-3 py-ds-2', className)}
        role="status"
        aria-live="polite"
      >
        <span className="text-xs text-ds-muted">Trust signals are available on demand.</span>
        <Button type="button" size="sm" variant="secondary" onClick={() => void load()}>
          Load trust
        </Button>
      </Card>
    );
  }

  if (isLoading && badges.length === 0) {
    return (
      <Card
        className={joinClasses('px-ds-3 py-ds-2', className)}
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        <LoadingSkeleton compact={compact} />
      </Card>
    );
  }

  if (isError && badges.length === 0) {
    return (
      <div className={className} role="status" aria-live="polite">
        <ErrorState message={error ?? 'Unable to load trust signals.'} onRetry={() => void load({ force: true })} />
      </div>
    );
  }

  const visibleBadges = typeof maxBadges === 'number' ? badges.slice(0, maxBadges) : badges;
  if (visibleBadges.length === 0) {
    return (
      <Card
        className={joinClasses('px-ds-3 py-ds-2 text-ds-xs text-ds-muted', className)}
        role="status"
        aria-live="polite"
      >
        {emptyState ?? 'Trust signals are not available for this result yet.'}
      </Card>
    );
  }

  return (
    <Card
      className={joinClasses(
        'flex flex-wrap items-center gap-ds-2 px-ds-3 py-ds-2',
        className,
      )}
      role="group"
      aria-label="Trust signals"
    >
      {visibleBadges.map((badge) => (
        <TrustBadge
          key={badge.key}
          badge={badge}
          compact={compact}
          onNavigate={onNavigate}
        />
      ))}
    </Card>
  );
}
