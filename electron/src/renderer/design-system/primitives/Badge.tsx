import type { ComponentPropsWithoutRef, ElementType, ReactElement, ReactNode } from 'react';
import { cn } from './utils';

type BadgeTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info';

type BadgeProps<T extends ElementType> = {
  readonly as?: T;
  readonly tone?: BadgeTone;
  readonly compact?: boolean;
  readonly leadingIcon?: ReactNode;
  readonly className?: string;
  readonly children: ReactNode;
};

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: 'border-ds-border bg-ds-bg/60 text-ds-muted',
  accent: 'border-ds-accent/30 bg-ds-accent/10 text-ds-accent',
  success: 'border-ds-success/30 bg-ds-success/10 text-ds-success',
  warning: 'border-ds-warning/30 bg-ds-warning/10 text-ds-warning',
  danger: 'border-ds-error/30 bg-ds-error/10 text-ds-error',
  info: 'border-ds-info/30 bg-ds-info/10 text-ds-info',
};

export function Badge<T extends ElementType = 'span'>({
  as,
  tone = 'neutral',
  compact = false,
  leadingIcon,
  className,
  children,
  ...rest
}: BadgeProps<T> & Omit<ComponentPropsWithoutRef<T>, keyof BadgeProps<T>>): ReactElement {
  const Component = as ?? 'span';
  return (
    <Component
      className={cn(
        'inline-flex min-w-0 items-center rounded-ds-pill border font-medium shadow-ds-sm transition-colors duration-ds-fast ease-ds-standard',
        compact ? 'gap-ds-1 px-ds-2 py-ds-1 text-ds-xs' : 'gap-ds-2 px-ds-3 py-ds-2 text-ds-xs',
        TONE_CLASSES[tone],
        className,
      )}
      {...rest}
    >
      {leadingIcon}
      <span className="truncate">{children}</span>
    </Component>
  );
}
