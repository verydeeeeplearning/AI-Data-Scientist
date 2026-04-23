import type { HTMLAttributes, ReactElement, ReactNode } from 'react';
import { useId, useMemo, useRef } from 'react';
import { cn } from './utils';

export interface TabsItem {
  readonly value: string;
  readonly label: ReactNode;
  readonly content: ReactNode;
  readonly disabled?: boolean;
}

export interface TabsProps extends HTMLAttributes<HTMLDivElement> {
  readonly value: string;
  readonly onValueChange: (value: string) => void;
  readonly items: readonly TabsItem[];
  readonly listClassName?: string;
  readonly tabClassName?: string;
  readonly panelClassName?: string;
}

export function Tabs({
  value,
  onValueChange,
  items,
  listClassName,
  tabClassName,
  panelClassName,
  className,
  ...rest
}: TabsProps): ReactElement {
  const generatedId = useId().replace(/:/g, '');
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const activeIndex = useMemo(
    () => items.findIndex((item) => item.value === value),
    [items, value],
  );
  const activeItem = activeIndex >= 0 ? items[activeIndex] : items[0];
  const activeValue = activeItem?.value ?? value;

  const focusTab = (index: number): void => {
    if (items.length === 0) {
      return;
    }

    const nextIndex = (index + items.length) % items.length;
    tabRefs.current[nextIndex]?.focus();
    onValueChange(items[nextIndex]?.value ?? value);
  };

  const selectedPanelId = activeValue ? `ds-tabs-${generatedId}-panel-${activeValue}` : undefined;

  return (
    <div className={cn('space-y-ds-3', className)} {...rest}>
      <div
        role="tablist"
        aria-orientation="horizontal"
        className={cn(
          'inline-flex max-w-full flex-wrap gap-ds-1 rounded-ds-pill border border-ds-border bg-ds-bg p-ds-1 shadow-ds-sm',
          listClassName,
        )}
      >
        {items.map((item, index) => {
          const selected = item.value === activeValue;
          const tabId = `ds-tabs-${generatedId}-tab-${item.value}`;
          const panelId = `ds-tabs-${generatedId}-panel-${item.value}`;

          return (
            <button
              key={item.value}
              ref={(node) => {
                tabRefs.current[index] = node;
              }}
              id={tabId}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={panelId}
              tabIndex={selected ? 0 : -1}
              disabled={item.disabled}
              onClick={() => onValueChange(item.value)}
              onKeyDown={(event) => {
                if (item.disabled) {
                  return;
                }

                switch (event.key) {
                  case 'ArrowRight':
                  case 'ArrowDown':
                    event.preventDefault();
                    focusTab(index + 1);
                    break;
                  case 'ArrowLeft':
                  case 'ArrowUp':
                    event.preventDefault();
                    focusTab(index - 1);
                    break;
                  case 'Home':
                    event.preventDefault();
                    tabRefs.current[0]?.focus();
                    onValueChange(items[0]?.value ?? value);
                    break;
                  case 'End':
                    event.preventDefault();
                    tabRefs.current[items.length - 1]?.focus();
                    onValueChange(items[items.length - 1]?.value ?? value);
                    break;
                  case 'Enter':
                  case ' ':
                    event.preventDefault();
                    onValueChange(item.value);
                    break;
                  default:
                    break;
                }
              }}
              className={cn(
                'inline-flex min-h-11 items-center justify-center rounded-ds-pill px-ds-4 text-ds-sm font-medium transition-all duration-ds-fast ease-ds-standard',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg',
                selected
                  ? 'border border-transparent bg-ds-accent text-ds-accent-contrast shadow-ds-sm'
                  : 'border border-transparent text-ds-muted hover:bg-ds-surface hover:text-ds-text',
                item.disabled ? 'cursor-not-allowed opacity-50 hover:bg-transparent hover:text-ds-muted' : '',
                tabClassName,
              )}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      {activeItem ? (
        <div
          id={selectedPanelId}
          role="tabpanel"
          aria-labelledby={`ds-tabs-${generatedId}-tab-${activeItem.value}`}
          className={cn(
            'rounded-ds-xl border border-ds-border bg-ds-surface/92 p-ds-4 text-ds-text shadow-ds-sm',
            panelClassName,
          )}
        >
          {activeItem.content}
        </div>
      ) : null}
    </div>
  );
}
