import type { HTMLAttributes, ReactElement } from 'react';
import { cn } from './utils';

type SkeletonShape = 'line' | 'block' | 'avatar' | 'pill';
type SkeletonTone = 'default' | 'muted';

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  readonly shape?: SkeletonShape;
  readonly tone?: SkeletonTone;
  readonly animated?: boolean;
}

const SHAPE_CLASSES: Record<SkeletonShape, string> = {
  line: 'h-4 w-full rounded-ds-pill',
  block: 'h-24 w-full rounded-ds-lg',
  avatar: 'h-12 w-12 rounded-full',
  pill: 'h-8 w-24 rounded-ds-pill',
};

const TONE_CLASSES: Record<SkeletonTone, string> = {
  default: 'bg-ds-border/70',
  muted: 'bg-ds-muted/20',
};

export function Skeleton({
  shape = 'line',
  tone = 'default',
  animated = true,
  className,
  ...rest
}: SkeletonProps): ReactElement {
  return (
    <div
      className={cn(
        'shrink-0',
        animated ? 'animate-pulse' : '',
        SHAPE_CLASSES[shape],
        TONE_CLASSES[tone],
        className,
      )}
      aria-hidden="true"
      {...rest}
    />
  );
}
