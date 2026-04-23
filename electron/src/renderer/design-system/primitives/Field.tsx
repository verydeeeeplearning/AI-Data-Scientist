import type { ReactElement, ReactNode } from 'react';
import { cn } from './utils';

export interface FieldFrameProps {
  readonly controlId: string;
  readonly label?: string;
  readonly description?: string;
  readonly descriptionId?: string;
  readonly hint?: string;
  readonly hintId?: string;
  readonly errorMessage?: string;
  readonly errorId?: string;
  readonly required?: boolean;
  readonly children: ReactNode;
}

export function FieldFrame({
  controlId,
  label,
  description,
  descriptionId,
  hint,
  hintId,
  errorMessage,
  errorId,
  required = false,
  children,
}: FieldFrameProps): ReactElement {
  return (
    <div className="space-y-ds-2">
      {label ? (
        <label htmlFor={controlId} className="flex items-center gap-ds-1 text-ds-xs font-medium text-ds-text">
          <span>{label}</span>
          {required ? (
            <span className="text-ds-error" aria-hidden="true">
              *
            </span>
          ) : null}
        </label>
      ) : null}
      {description ? (
        <p id={descriptionId} className="text-ds-xs leading-5 text-ds-muted">
          {description}
        </p>
      ) : null}
      {children}
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
