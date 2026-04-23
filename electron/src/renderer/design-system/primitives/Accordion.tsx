import type { HTMLAttributes, ReactElement, ReactNode } from 'react';
import { useId } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from './utils';

export interface AccordionItem {
  readonly value: string;
  readonly title: ReactNode;
  readonly content: ReactNode;
  readonly disabled?: boolean;
}

export interface AccordionProps extends HTMLAttributes<HTMLDivElement> {
  readonly value: string | null;
  readonly onValueChange: (value: string | null) => void;
  readonly items: readonly AccordionItem[];
  readonly allowCollapse?: boolean;
  readonly itemClassName?: string;
  readonly triggerClassName?: string;
  readonly contentClassName?: string;
}

export function Accordion({
  value,
  onValueChange,
  items,
  allowCollapse = true,
  itemClassName,
  triggerClassName,
  contentClassName,
  className,
  ...rest
}: AccordionProps): ReactElement {
  const generatedId = useId().replace(/:/g, '');

  return (
    <div className={cn('space-y-ds-2', className)} {...rest}>
      {items.map((item) => {
        const open = item.value === value;
        const triggerId = `ds-accordion-${generatedId}-trigger-${item.value}`;
        const panelId = `ds-accordion-${generatedId}-panel-${item.value}`;

        return (
          <div
            key={item.value}
            className={cn(
              'rounded-ds-xl border border-ds-border bg-ds-surface/92 shadow-ds-sm',
              itemClassName,
            )}
          >
            <button
              type="button"
              id={triggerId}
              aria-expanded={open}
              aria-controls={panelId}
              disabled={item.disabled}
              onClick={() => {
                if (item.disabled) {
                  return;
                }

                onValueChange(open && allowCollapse ? null : item.value);
              }}
              className={cn(
                'flex w-full items-center justify-between gap-ds-3 rounded-ds-xl px-ds-4 py-ds-3 text-left text-ds-sm font-medium text-ds-text transition-colors duration-ds-fast ease-ds-standard',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg',
                open ? 'bg-ds-bg' : 'hover:bg-ds-bg',
                item.disabled ? 'cursor-not-allowed opacity-50 hover:bg-transparent' : '',
                triggerClassName,
              )}
            >
              <span className="min-w-0">{item.title}</span>
              <ChevronDown
                size={16}
                aria-hidden="true"
                className={cn(
                  'shrink-0 text-ds-muted transition-transform duration-ds-fast ease-ds-standard',
                  open ? 'rotate-180 text-ds-text' : '',
                )}
              />
            </button>
            {open ? (
              <div
                id={panelId}
                role="region"
                aria-labelledby={triggerId}
                className={cn('border-t border-ds-border px-ds-4 py-ds-4', contentClassName)}
              >
                {item.content}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
