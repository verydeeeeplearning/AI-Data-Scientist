import type { HTMLAttributes, ReactElement, ReactNode } from 'react';
import { useEffect, useId, useRef, type KeyboardEvent } from 'react';
import { X } from 'lucide-react';
import {
  captureFocus,
  createFocusTrap,
  restoreFocus,
  type FocusToken,
  type FocusTrap,
} from '../../application/a11y/focusManagement';
import { prefersReducedMotion } from '../../application/a11y/reducedMotion';
import { cn, joinIds } from './utils';

type DrawerShellSize = 'sm' | 'md' | 'lg';
type DrawerShellPlacement = 'left' | 'right';

export interface DrawerShellProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  readonly open?: boolean;
  readonly title: ReactNode;
  readonly description?: ReactNode;
  readonly footer?: ReactNode;
  readonly size?: DrawerShellSize;
  readonly placement?: DrawerShellPlacement;
  readonly dismissLabel?: string;
  readonly onDismiss?: () => void;
  readonly bodyClassName?: string;
  readonly panelClassName?: string;
  readonly overlayClassName?: string;
}

const SIZE_CLASSES: Record<DrawerShellSize, string> = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
};

const PLACEMENT_CLASSES: Record<DrawerShellPlacement, string> = {
  left: 'justify-start',
  right: 'justify-end',
};

export function DrawerShell({
  open = true,
  title,
  description,
  footer,
  size = 'md',
  placement = 'right',
  dismissLabel = 'Close panel',
  onDismiss,
  bodyClassName,
  panelClassName,
  overlayClassName,
  className,
  children,
  'aria-describedby': ariaDescribedBy,
  ...rest
}: DrawerShellProps): ReactElement | null {
  const generatedId = useId().replace(/:/g, '');
  const titleId = `ds-drawer-${generatedId}-title`;
  const descriptionId = description ? `ds-drawer-${generatedId}-description` : undefined;
  const panelRef = useRef<HTMLDivElement | null>(null);
  const trapRef = useRef<FocusTrap | null>(null);
  const focusTokenRef = useRef<FocusToken>({ previous: null });
  const dismissButtonRef = useRef<HTMLButtonElement | null>(null);
  const motionClass = prefersReducedMotion()
    ? ''
    : 'transition-transform duration-ds-normal ease-ds-standard';

  useEffect(() => {
    const panel = panelRef.current;
    if (!open || !panel) {
      trapRef.current?.deactivate();
      trapRef.current = null;
      return undefined;
    }

    focusTokenRef.current = captureFocus();
    const trap = createFocusTrap(panel);
    trapRef.current = trap;
    trap.activate();
    const handle = window.requestAnimationFrame(() => {
      dismissButtonRef.current?.focus();
    });

    return () => {
      window.cancelAnimationFrame(handle);
      trap.deactivate();
      if (trapRef.current === trap) {
        trapRef.current = null;
      }
      restoreFocus(focusTokenRef.current);
      focusTokenRef.current = { previous: null };
    };
  }, [open]);

  if (!open) {
    return null;
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onDismiss?.();
      return;
    }
    if (event.key === 'Tab') {
      event.preventDefault();
      trapRef.current?.cycle(event.shiftKey ? 'backward' : 'forward');
    }
  };

  return (
    <div
      className={cn(
        'fixed inset-0 z-40 flex bg-black/40 p-ds-3 sm:p-ds-4',
        PLACEMENT_CLASSES[placement],
        overlayClassName,
      )}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={joinIds(descriptionId, ariaDescribedBy)}
        className={cn(
          'flex h-full w-full flex-col rounded-ds-xl border border-ds-border bg-ds-surface-elevated/98 text-ds-text shadow-ds-lg',
          SIZE_CLASSES[size],
          motionClass,
          panelClassName,
          className,
        )}
        onKeyDown={handleKeyDown}
        {...rest}
      >
        <div className="flex items-start justify-between gap-ds-3 border-b border-ds-border/80 px-ds-4 py-ds-4">
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
            <button
              ref={dismissButtonRef}
              type="button"
              aria-label={dismissLabel}
              className={cn(
                'inline-flex min-h-11 items-center justify-center rounded-ds-pill border border-transparent px-ds-3 text-ds-xs font-medium text-ds-muted shadow-ds-sm transition-all duration-ds-normal ease-ds-standard',
                'hover:bg-ds-bg hover:text-ds-text',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg',
              )}
              onClick={onDismiss}
            >
              <X size={16} aria-hidden="true" />
            </button>
          ) : null}
        </div>

        <div className={cn('min-h-0 flex-1 overflow-y-auto px-ds-4 py-ds-4', bodyClassName)}>
          {children}
        </div>

        {footer ? (
          <div className="flex items-center justify-end gap-ds-2 border-t border-ds-border/80 px-ds-4 py-ds-4">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
