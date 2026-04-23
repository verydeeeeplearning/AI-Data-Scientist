import type { ComponentPropsWithoutRef, HTMLAttributes, ReactElement } from 'react';
import { cn } from '../primitives/utils';

export interface DrawerSurfaceProps extends ComponentPropsWithoutRef<'section'> {}

export function DrawerSurface({
  className,
  children,
  ...rest
}: DrawerSurfaceProps): ReactElement {
  return (
    <section
      className={cn(
        'flex h-full min-h-0 flex-col border-l border-ds-border bg-ds-surface/95 text-ds-text shadow-ds-lg',
        className,
      )}
      {...rest}
    >
      {children}
    </section>
  );
}

export interface DrawerSurfaceHeaderProps extends HTMLAttributes<HTMLDivElement> {}

export function DrawerSurfaceHeader({
  className,
  children,
  ...rest
}: DrawerSurfaceHeaderProps): ReactElement {
  return (
    <div
      className={cn(
        'flex items-start gap-ds-3 border-b border-ds-border/80 px-ds-4 py-ds-4',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export interface DrawerSurfaceBodyProps extends HTMLAttributes<HTMLDivElement> {}

export function DrawerSurfaceBody({
  className,
  children,
  ...rest
}: DrawerSurfaceBodyProps): ReactElement {
  return (
    <div
      className={cn('min-h-0 flex-1 overflow-y-auto px-ds-4 py-ds-4 space-y-ds-4', className)}
      {...rest}
    >
      {children}
    </div>
  );
}

export interface DrawerSurfaceEyebrowProps extends HTMLAttributes<HTMLDivElement> {}

export function DrawerSurfaceEyebrow({
  className,
  children,
  ...rest
}: DrawerSurfaceEyebrowProps): ReactElement {
  return (
    <div
      className={cn(
        'text-ds-xs font-semibold uppercase tracking-widest text-ds-muted',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

export interface DrawerSurfaceSectionProps extends HTMLAttributes<HTMLElement> {}

export function DrawerSurfaceSection({
  className,
  children,
  ...rest
}: DrawerSurfaceSectionProps): ReactElement {
  return (
    <section
      className={cn('rounded-ds-lg border border-ds-border/70 bg-ds-bg/70 p-ds-3', className)}
      {...rest}
    >
      {children}
    </section>
  );
}

export interface DrawerSurfaceSectionTitleProps extends HTMLAttributes<HTMLHeadingElement> {}

export function DrawerSurfaceSectionTitle({
  className,
  children,
  ...rest
}: DrawerSurfaceSectionTitleProps): ReactElement {
  return (
    <h3
      className={cn(
        'text-ds-xs font-semibold uppercase tracking-widest text-ds-muted',
        className,
      )}
      {...rest}
    >
      {children}
    </h3>
  );
}

export interface DrawerSurfaceStatGridProps extends HTMLAttributes<HTMLDivElement> {}

export function DrawerSurfaceStatGrid({
  className,
  children,
  ...rest
}: DrawerSurfaceStatGridProps): ReactElement {
  return (
    <div className={cn('grid grid-cols-2 gap-ds-2', className)} {...rest}>
      {children}
    </div>
  );
}

export interface DrawerSurfaceStatProps extends HTMLAttributes<HTMLDivElement> {
  readonly label: string;
  readonly value: string;
}

export function DrawerSurfaceStat({
  label,
  value,
  className,
  ...rest
}: DrawerSurfaceStatProps): ReactElement {
  return (
    <div
      className={cn('rounded-ds-md border border-ds-border/70 bg-ds-surface/60 px-ds-3 py-ds-2', className)}
      {...rest}
    >
      <div className="text-ds-2xs uppercase tracking-wider text-ds-muted">{label}</div>
      <div className="mt-ds-1 text-ds-sm text-ds-text">{value}</div>
    </div>
  );
}
