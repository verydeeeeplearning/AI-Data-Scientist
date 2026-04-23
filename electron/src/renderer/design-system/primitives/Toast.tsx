import type { HTMLAttributes, ReactElement, ReactNode } from 'react';
import { X } from 'lucide-react';
import { cn } from './utils';

type ToastTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';
type ToastPlacement = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
type ToastAnnounce = 'polite' | 'assertive' | 'off';

export interface ToastViewportProps extends HTMLAttributes<HTMLDivElement> {
  readonly placement?: ToastPlacement;
  readonly label?: string;
}

export interface ToastProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  readonly title: ReactNode;
  readonly description?: ReactNode;
  readonly meta?: ReactNode;
  readonly tone?: ToastTone;
  readonly leadingIcon?: ReactNode;
  readonly announce?: ToastAnnounce;
  readonly dismissLabel?: string;
  readonly onDismiss?: () => void;
}

const VIEWPORT_PLACEMENT_CLASSES: Record<ToastPlacement, string> = {
  'top-left': 'left-4 top-4',
  'top-right': 'right-4 top-4',
  'bottom-left': 'bottom-4 left-4',
  'bottom-right': 'bottom-4 right-4',
};

const TONE_CLASSES: Record<ToastTone, { readonly container: string; readonly icon: string }> = {
  neutral: {
    container: 'border-ds-border bg-ds-surface-elevated/96',
    icon: 'border-ds-border/70 bg-ds-bg/70 text-ds-muted',
  },
  info: {
    container: 'border-ds-info/30 bg-ds-info/10',
    icon: 'border-ds-info/30 bg-ds-info/15 text-ds-info',
  },
  success: {
    container: 'border-ds-success/30 bg-ds-success/10',
    icon: 'border-ds-success/30 bg-ds-success/15 text-ds-success',
  },
  warning: {
    container: 'border-ds-warning/30 bg-ds-warning/10',
    icon: 'border-ds-warning/30 bg-ds-warning/15 text-ds-warning',
  },
  danger: {
    container: 'border-ds-error/30 bg-ds-error/10',
    icon: 'border-ds-error/30 bg-ds-error/15 text-ds-error',
  },
};

export function ToastViewport({
  placement = 'bottom-right',
  label = 'Notifications',
  className,
  children,
  ...rest
}: ToastViewportProps): ReactElement {
  return (
    <div
      aria-label={label}
      className={cn(
        'pointer-events-none fixed z-50 flex w-full max-w-ds-toast flex-col gap-ds-2 sm:w-auto',
        VIEWPORT_PLACEMENT_CLASSES[placement],
        className,
      )}
      role="region"
      {...rest}
    >
      {children}
    </div>
  );
}

export function Toast({
  title,
  description,
  meta,
  tone = 'neutral',
  leadingIcon,
  announce = 'polite',
  dismissLabel = 'Dismiss notification',
  onDismiss,
  className,
  children,
  ...rest
}: ToastProps): ReactElement {
  const role = announce === 'assertive' ? 'alert' : announce === 'off' ? 'group' : 'status';

  return (
    <div
      aria-live={announce === 'off' ? undefined : announce}
      className={cn(
        'pointer-events-auto rounded-ds-xl border px-ds-4 py-ds-3 text-ds-text shadow-ds-lg',
        TONE_CLASSES[tone].container,
        className,
      )}
      role={role}
      {...rest}
    >
      <div className="flex items-start gap-ds-3">
        {leadingIcon ? (
          <div
            aria-hidden="true"
            className={cn(
              'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-ds-pill border',
              TONE_CLASSES[tone].icon,
            )}
          >
            {leadingIcon}
          </div>
        ) : null}
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-ds-2">
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex items-start justify-between gap-ds-2">
                <div className="min-w-0">
                  <div className="text-ds-sm font-semibold text-ds-text">{title}</div>
                  {description ? (
                    <div className="mt-1 text-ds-xs leading-5 text-ds-text/90">{description}</div>
                  ) : null}
                </div>
                {meta ? (
                  <div className="shrink-0 text-ds-2xs font-mono text-ds-muted">{meta}</div>
                ) : null}
              </div>
              {children ? <div className="pt-ds-1">{children}</div> : null}
            </div>
            {onDismiss ? (
              <button
                type="button"
                aria-label={dismissLabel}
                className={cn(
                  'inline-flex h-7 w-7 min-h-11 min-w-11 shrink-0 items-center justify-center rounded-ds-pill border border-transparent text-ds-muted transition-colors duration-ds-fast ease-ds-standard',
                  'hover:bg-ds-bg/70 hover:text-ds-text',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg',
                )}
                onClick={onDismiss}
              >
                <X size={14} aria-hidden="true" />
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
