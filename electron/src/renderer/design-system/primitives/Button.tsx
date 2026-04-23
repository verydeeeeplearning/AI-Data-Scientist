import type { ButtonHTMLAttributes, ReactElement, ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from './utils';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: ButtonVariant;
  readonly size?: ButtonSize;
  readonly leadingIcon?: ReactNode;
  readonly trailingIcon?: ReactNode;
  readonly loading?: boolean;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    'border-transparent bg-ds-accent text-ds-accent-contrast hover:bg-ds-accent-hover',
  secondary:
    'border-ds-border bg-ds-surface text-ds-text hover:border-ds-accent/40 hover:bg-ds-bg',
  ghost:
    'border-transparent bg-transparent text-ds-muted hover:bg-ds-bg hover:text-ds-text',
  danger: 'border-transparent bg-ds-error text-white hover:opacity-90',
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: 'min-h-11 gap-ds-1 px-ds-3 text-ds-xs',
  md: 'min-h-11 gap-ds-2 px-ds-4 text-ds-sm',
  lg: 'min-h-12 gap-ds-2 px-ds-5 text-ds-sm',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  leadingIcon,
  trailingIcon,
  loading = false,
  className,
  children,
  disabled,
  type = 'button',
  ...rest
}: ButtonProps): ReactElement {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center rounded-ds-pill border font-medium shadow-ds-sm transition-all duration-ds-normal ease-ds-standard',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg',
        'disabled:cursor-not-allowed disabled:opacity-50',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : leadingIcon}
      {children}
      {trailingIcon}
    </button>
  );
}

