import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type ReactNode,
} from 'react';
import {
  captureFocus,
  createFocusTrap,
  restoreFocus,
  type FocusToken,
  type FocusTrap,
} from '../../application/a11y/focusManagement';
import { useI18n } from '../../stores/i18nStore';

export interface MissionDropdownItem<T> {
  readonly key: string;
  readonly label: string;
  readonly description?: string;
  readonly value: T;
  readonly active: boolean;
}

interface Props<T> {
  readonly open: boolean;
  readonly title: string;
  readonly items: ReadonlyArray<MissionDropdownItem<T>>;
  readonly emptyLabel?: string;
  readonly onSelect: (value: T) => void;
  readonly onClose: () => void;
  readonly footer?: ReactNode;
}

export function MissionDropdownMenu<T>({
  open,
  title,
  items,
  emptyLabel,
  onSelect,
  onClose,
  footer,
}: Props<T>) {
  const { t } = useI18n();
  const id = useId();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const trapRef = useRef<FocusTrap | null>(null);
  const focusTokenRef = useRef<FocusToken>({ previous: null });

  useEffect(() => {
    const node = containerRef.current;
    if (!open || !node) {
      trapRef.current?.deactivate();
      trapRef.current = null;
      return undefined;
    }

    focusTokenRef.current = captureFocus();
    const trap = createFocusTrap(node);
    trapRef.current = trap;
    trap.activate();

    return () => {
      trap.deactivate();
      if (trapRef.current === trap) {
        trapRef.current = null;
      }
      restoreFocus(focusTokenRef.current);
      focusTokenRef.current = { previous: null };
    };
  }, [open]);

  if (!open) {
    return null;
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === 'Tab') {
      event.preventDefault();
      trapRef.current?.cycle(event.shiftKey ? 'backward' : 'forward');
    }
  };

  const empty = items.length === 0;

  return (
    <div
      ref={containerRef}
      role="menu"
      aria-labelledby={`${id}-title`}
      className="rounded-2xl border border-ds-border bg-ds-bg/90 p-2 shadow-xl"
      onKeyDown={handleKeyDown}
    >
      <div
        id={`${id}-title`}
        className="px-2 pb-2 text-[10px] uppercase tracking-[0.18em] text-ds-muted"
      >
        {title}
      </div>
      {empty ? (
        <div className="rounded-xl bg-ds-surface px-3 py-2 text-xs text-ds-muted">
          {emptyLabel ?? t('mission.dropdown.empty')}
        </div>
      ) : (
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.key} role="none">
              <button
                type="button"
                role="menuitem"
                onClick={() => onSelect(item.value)}
                className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ds-bg ${
                  item.active
                    ? 'border-ds-accent bg-ds-accent/10 text-ds-accent'
                    : 'border-ds-border bg-ds-surface text-ds-text hover:border-ds-accent/50'
                }`}
              >
                <span className="font-medium">{item.label}</span>
                {item.description && (
                  <span className="mt-1 block text-[11px] text-ds-muted">
                    {item.description}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
      {footer && <div className="mt-2 border-t border-ds-border pt-2">{footer}</div>}
    </div>
  );
}
