import type {
  ButtonHTMLAttributes,
  ComponentPropsWithoutRef,
  HTMLAttributes,
  ReactElement,
  ReactNode,
} from 'react';
import { Badge, Button } from '../primitives';
import { cn } from '../primitives/utils';

export interface ResultCardShellProps extends ComponentPropsWithoutRef<'article'> {}

export function ResultCardShell({
  className,
  children,
  ...rest
}: ResultCardShellProps): ReactElement {
  return (
    <article
      className={cn(
        'rounded-ds-xl border border-ds-border bg-ds-surface/80 p-ds-4 text-ds-text shadow-ds-sm shadow-black/10',
        className,
      )}
      {...rest}
    >
      {children}
    </article>
  );
}

export interface ResultCardMetaRowProps extends HTMLAttributes<HTMLDivElement> {}

export function ResultCardMetaRow({
  className,
  children,
  ...rest
}: ResultCardMetaRowProps): ReactElement {
  return (
    <div
      className={cn('flex flex-wrap items-center gap-ds-2 text-ds-xs text-ds-muted', className)}
      {...rest}
    >
      {children}
    </div>
  );
}

export interface ResultCardPillProps extends HTMLAttributes<HTMLSpanElement> {
  readonly compact?: boolean;
}

export function ResultCardPill({
  compact = true,
  className,
  children,
  ...rest
}: ResultCardPillProps): ReactElement {
  return (
    <Badge compact={compact} className={cn('normal-case tracking-normal', className)} {...rest}>
      {children}
    </Badge>
  );
}

export interface ResultCardPillButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {}

export function ResultCardPillButton({
  className,
  children,
  type = 'button',
  ...rest
}: ResultCardPillButtonProps): ReactElement {
  return (
    <Badge<'button'>
      as="button"
      type={type}
      compact
      className={cn(
        'normal-case tracking-normal transition-colors duration-ds-fast ease-ds-standard',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg',
        'hover:border-ds-accent/40 hover:text-ds-accent disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...rest}
    >
      {children}
    </Badge>
  );
}

export interface ResultCardIconFrameProps extends HTMLAttributes<HTMLDivElement> {}

export function ResultCardIconFrame({
  className,
  children,
  ...rest
}: ResultCardIconFrameProps): ReactElement {
  return (
    <div
      className={cn(
        'flex h-10 w-10 items-center justify-center rounded-ds-lg border px-ds-3 py-ds-2',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export interface ResultCardFooterProps extends HTMLAttributes<HTMLElement> {}

export function ResultCardFooter({
  className,
  children,
  ...rest
}: ResultCardFooterProps): ReactElement {
  return (
    <footer className={cn('mt-ds-4 space-y-ds-3 border-t border-ds-border/60 pt-ds-3', className)} {...rest}>
      {children}
    </footer>
  );
}

export interface ResultCardSectionTitleProps extends HTMLAttributes<HTMLHeadingElement> {}

export function ResultCardSectionTitle({
  className,
  children,
  ...rest
}: ResultCardSectionTitleProps): ReactElement {
  return (
    <h4
      className={cn(
        'text-ds-xs font-semibold uppercase tracking-widest text-ds-muted',
        className,
      )}
      {...rest}
    >
      {children}
    </h4>
  );
}

export interface ResultCardSectionPanelProps extends HTMLAttributes<HTMLElement> {}

export function ResultCardSectionPanel({
  className,
  children,
  ...rest
}: ResultCardSectionPanelProps): ReactElement {
  return (
    <section
      className={cn('rounded-ds-lg border border-ds-border/70 bg-ds-bg/60 p-ds-3', className)}
      {...rest}
    >
      {children}
    </section>
  );
}

export interface ResultCardMetricPanelProps {
  readonly label: string;
  readonly value: string;
  readonly hint?: string;
  readonly className?: string;
}

export function ResultCardMetricPanel({
  label,
  value,
  hint,
  className,
}: ResultCardMetricPanelProps): ReactElement {
  return (
    <section
      className={cn(
        'rounded-ds-lg border border-ds-accent/20 bg-ds-accent/5 p-ds-3',
        className,
      )}
    >
      <ResultCardSectionTitle>{label}</ResultCardSectionTitle>
      <div className="mt-ds-2 text-ds-2xl font-semibold text-ds-text">{value}</div>
      {hint && <div className="mt-ds-1 text-ds-xs text-ds-muted">{hint}</div>}
    </section>
  );
}

export interface ResultCardDetailBlockProps {
  readonly label: string;
  readonly value: string;
  readonly className?: string;
}

export function ResultCardDetailBlock({
  label,
  value,
  className,
}: ResultCardDetailBlockProps): ReactElement {
  return (
    <ResultCardSectionPanel className={className}>
      <ResultCardSectionTitle>{label}</ResultCardSectionTitle>
      <div className="mt-ds-2 text-ds-sm text-ds-text">{value}</div>
    </ResultCardSectionPanel>
  );
}

type ActionTone = 'default' | 'accent' | 'danger';

export interface ResultCardActionButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly tone?: ActionTone;
  readonly leadingIcon?: ReactNode;
  readonly trailingIcon?: ReactNode;
}

const ACTION_TONE_CLASSES: Record<Exclude<ActionTone, 'danger'>, string> = {
  default: '',
  accent: 'border-ds-accent/40 bg-ds-accent/5 text-ds-accent hover:bg-ds-accent/10',
};

export function ResultCardActionButton({
  tone = 'default',
  className,
  leadingIcon,
  trailingIcon,
  children,
  ...rest
}: ResultCardActionButtonProps): ReactElement {
  if (tone === 'danger') {
    return (
      <Button
        variant="danger"
        size="sm"
        leadingIcon={leadingIcon}
        trailingIcon={trailingIcon}
        className={className}
        {...rest}
      >
        {children}
      </Button>
    );
  }

  return (
    <Button
      variant="secondary"
      size="sm"
      leadingIcon={leadingIcon}
      trailingIcon={trailingIcon}
      className={cn(ACTION_TONE_CLASSES[tone], className)}
      {...rest}
    >
      {children}
    </Button>
  );
}
