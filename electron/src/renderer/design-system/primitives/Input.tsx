import type { InputHTMLAttributes, ReactElement, ReactNode } from 'react';
import { useId } from 'react';
import { FieldFrame } from './Field';
import { cn, isAriaInvalid, joinIds } from './utils';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  readonly label?: string;
  readonly description?: string;
  readonly hint?: string;
  readonly errorMessage?: string;
  readonly leadingIcon?: ReactNode;
  readonly trailingIcon?: ReactNode;
  readonly containerClassName?: string;
}

export function Input({
  id,
  type = 'text',
  label,
  description,
  hint,
  errorMessage,
  leadingIcon,
  trailingIcon,
  containerClassName,
  className,
  disabled = false,
  readOnly = false,
  required = false,
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
  ...rest
}: InputProps): ReactElement {
  const generatedId = useId().replace(/:/g, '');
  const controlId = id ?? `ds-input-${generatedId}`;
  const descriptionId = description ? `${controlId}-description` : undefined;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = errorMessage ? `${controlId}-error` : undefined;
  const invalid = isAriaInvalid(ariaInvalid) || Boolean(errorMessage);

  return (
    <FieldFrame
      controlId={controlId}
      label={label}
      description={description}
      descriptionId={descriptionId}
      hint={hint}
      hintId={hintId}
      errorMessage={errorMessage}
      errorId={errorId}
      required={required}
    >
      <div
        className={cn(
          'flex min-h-11 w-full items-center gap-ds-2 rounded-ds-md border px-ds-3 py-ds-2 shadow-ds-sm transition-colors duration-ds-fast ease-ds-standard',
          readOnly ? 'bg-ds-surface/80' : 'bg-ds-bg',
          invalid
            ? 'border-ds-error bg-ds-error/5 focus-within:border-ds-error focus-within:ring-ds-error/30'
            : 'border-ds-border focus-within:border-ds-accent focus-within:ring-ds-accent/70',
          'focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-offset-ds-bg',
          disabled ? 'cursor-not-allowed opacity-60' : '',
          containerClassName,
        )}
      >
        {leadingIcon ? (
          <span className="shrink-0 text-ds-muted" aria-hidden="true">
            {leadingIcon}
          </span>
        ) : null}
        <input
          id={controlId}
          type={type}
          aria-describedby={joinIds(descriptionId, errorId, hintId, ariaDescribedBy)}
          aria-invalid={invalid || undefined}
          disabled={disabled}
          readOnly={readOnly}
          required={required}
          className={cn(
            'min-w-0 flex-1 border-0 bg-transparent text-ds-sm text-ds-text outline-none placeholder:text-ds-muted/70 focus-visible:outline-none',
            className,
          )}
          {...rest}
        />
        {trailingIcon ? (
          <span className={cn('shrink-0', invalid ? 'text-ds-error' : 'text-ds-muted')} aria-hidden="true">
            {trailingIcon}
          </span>
        ) : null}
      </div>
    </FieldFrame>
  );
}
