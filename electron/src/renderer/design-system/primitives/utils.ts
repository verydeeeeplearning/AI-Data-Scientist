import type { AriaAttributes } from 'react';

export function cn(...values: Array<string | null | undefined | false>): string {
  return values.filter(Boolean).join(' ');
}

export function joinIds(...values: Array<string | undefined>): string | undefined {
  const ids = values.filter((value): value is string => Boolean(value));
  return ids.length > 0 ? ids.join(' ') : undefined;
}

export function isAriaInvalid(value: AriaAttributes['aria-invalid']): boolean {
  return value !== undefined && value !== false && value !== 'false';
}
