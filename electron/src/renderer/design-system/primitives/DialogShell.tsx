import type { HTMLAttributes, ReactElement, ReactNode } from 'react';
import { useId } from 'react';
import { X } from 'lucide-react';
import { Button } from './Button';
import { cn, joinIds } from './utils';

type DialogShellSize = 'sm' | 'md' | 'lg';
type DialogShellTone = 'default' | 'danger';

export interface DialogShellProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  readonly open?: boolean;
  readonly title: ReactNode;
  readonly description?: ReactNode;
  readonly footer?: ReactNode;
  readonly size?: DialogShellSize;
  readonly tone?: DialogShellTone;
  readonly dismissLabel?: string;
  readonly onDismiss?: () => void;
}

const SIZE_CLASSES: Record<DialogShellSize, string> = {
  sm: 'max-w-lg',
  md: 'max-w-2xl',
  lg: 'max-w-4xl',
};

const TONE_CLASSES: Record<DialogShellTone, string> = {
  default: 'border-ds-border bg-ds-surface-elevated/96',
  danger: 'border-ds-error/40 bg-ds-surface-elevated/96',
};

export function DialogShell({
  open = true,
  title,
  description,
  footer,
  size = 'md',
  tone = 'default',
  dismissLabel = 'Close dialog',
  onDismiss,
  className,
  children,
  'aria-describedby': ariaDescribedBy,
  ...rest
}: DialogShellProps): ReactElement | null {
  const generatedId = useId().replace(/:/g, '');
  const titleId = `ds-dialog-${generatedId}-title`;
  const descriptionId = description ? `ds-dialog-${generatedId}-description` : undefined;
  const borderClass = tone === 'danger' ? 'border-ds-error/20' : 'border-ds-border/80';

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ds-bg/75 p-ds-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={joinIds(descriptionId, ariaDescribedBy)}
        className={cn(
          'w-full rounded-ds-xl border text-ds-text shadow-ds-lg',
          SIZE_CLASSES[size],
          TONE_CLASSES[tone],
          className,
        )}
        {...rest}
      >
        <div className={cn('flex items-start justify-between gap-ds-3 border-b px-ds-4 py-ds-4', borderClass)}>
          <div className="min-w-0 space-y-ds-2">
            <div id={titleId} className="text-ds-lg font-semibold text-ds-text">
              {title}
            </div>
            {description ? (
              <p id={descriptionId} className="text-ds-sm leading-6 text-ds-muted">
                {description}
              </p>
            ) : null}
          </div>
          {onDismiss ? (
            <Button
              variant="ghost"
              size="sm"
              aria-label={dismissLabel}
              className="shrink-0"
              onClick={onDismiss}
            >
              <X size={16} aria-hidden="true" />
            </Button>
          ) : null}
        </div>
        <div className="px-ds-4 py-ds-4">{children}</div>
        {footer ? (
          <div className={cn('flex items-center justify-end gap-ds-2 border-t px-ds-4 py-ds-4', borderClass)}>
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
