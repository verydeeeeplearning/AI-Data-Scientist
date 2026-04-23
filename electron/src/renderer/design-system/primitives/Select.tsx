import type { ReactElement, SelectHTMLAttributes } from 'react';
import { useId } from 'react';
import { cn } from './utils';

interface SelectOption {
  readonly value: string;
  readonly label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  readonly label?: string;
  readonly description?: string;
  readonly options: readonly SelectOption[];
}

export function Select({
  id,
  label,
  description,
  options,
  className,
  ...rest
}: SelectProps): ReactElement {
  const generatedId = useId().replace(/:/g, '');
  const controlId = id ?? `ds-select-${generatedId}`;
  const descriptionId = description ? `${controlId}-description` : undefined;

  return (
    <div className="space-y-ds-2">
      {label ? (
        <label htmlFor={controlId} className="block text-ds-xs font-medium text-ds-text">
          {label}
        </label>
      ) : null}
      {description ? (
        <p id={descriptionId} className="text-ds-xs leading-5 text-ds-muted">
          {description}
        </p>
      ) : null}
      <select
        id={controlId}
        aria-describedby={descriptionId}
        className={cn(
          'min-h-11 w-full rounded-ds-md border border-ds-border bg-ds-bg px-ds-3 py-ds-2 text-ds-sm text-ds-text shadow-ds-sm transition-colors',
          'focus:border-ds-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg',
          className,
        )}
        {...rest}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
