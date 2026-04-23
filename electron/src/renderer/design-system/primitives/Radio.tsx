import type { InputHTMLAttributes, ReactElement } from 'react';
import { useId } from 'react';
import { cn, isAriaInvalid, joinIds } from './utils';

export interface RadioProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size' | 'type'> {
  readonly label?: string;
  readonly description?: string;
  readonly hint?: string;
  readonly errorMessage?: string;
}

export function Radio({
  id,
  label,
  description,
  hint,
  errorMessage,
  className,
  disabled = false,
  required = false,
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
  ...rest
}: RadioProps): ReactElement {
  const generatedId = useId().replace(/:/g, '');
  const controlId = id ?? `ds-radio-${generatedId}`;
  const descriptionId = description ? `${controlId}-description` : undefined;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = errorMessage ? `${controlId}-error` : undefined;
  const invalid = isAriaInvalid(ariaInvalid) || Boolean(errorMessage);

  return (
    <div className="space-y-ds-2">
      <label
        htmlFor={controlId}
        className={cn(
          'flex min-h-11 items-start gap-ds-3 rounded-ds-md transition-colors duration-ds-fast ease-ds-standard',
          disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
          className,
        )}
      >
        <input
          id={controlId}
          type="radio"
          aria-describedby={joinIds(descriptionId, errorId, hintId, ariaDescribedBy)}
          aria-invalid={invalid || undefined}
          disabled={disabled}
          required={required}
          className="peer sr-only"
          {...rest}
        />
        <span
          className={cn(
            'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-ds-pill border bg-ds-bg text-transparent shadow-ds-sm transition-all duration-ds-fast ease-ds-standard',
            'peer-focus-visible:outline-none peer-focus-visible:ring-2 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-ds-bg',
            'peer-disabled:bg-ds-surface',
            invalid
              ? 'border-ds-error peer-checked:border-ds-error peer-checked:bg-ds-error/10 peer-checked:text-ds-error peer-focus-visible:ring-ds-error/30'
              : 'border-ds-border peer-checked:border-ds-accent peer-checked:bg-ds-accent/10 peer-checked:text-ds-accent peer-focus-visible:ring-ds-accent/70',
          )}
          aria-hidden="true"
        >
          <span className="h-2 w-2 rounded-ds-pill bg-current" />
        </span>
        <span className="min-w-0 space-y-ds-1 pt-0.5">
          {label ? (
            <span className="block text-ds-sm font-medium text-ds-text">
              {label}
              {required ? (
                <span className="ml-ds-1 text-ds-error" aria-hidden="true">
                  *
                </span>
              ) : null}
            </span>
          ) : null}
          {description ? (
            <span id={descriptionId} className="block text-ds-xs leading-5 text-ds-muted">
              {description}
            </span>
          ) : null}
        </span>
      </label>
      {errorMessage ? (
        <p id={errorId} className="text-ds-xs leading-5 text-ds-error">
          {errorMessage}
        </p>
      ) : null}
      {hint ? (
        <p
          id={hintId}
          className={cn(
            'text-ds-xs leading-5',
            errorMessage ? 'text-ds-muted/80' : 'text-ds-muted',
          )}
        >
          {hint}
        </p>
      ) : null}
    </div>
  );
}
