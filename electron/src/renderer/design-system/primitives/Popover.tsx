import {
  cloneElement,
  useEffect,
  useId,
  useRef,
  useState,
  type HTMLAttributes,
  type KeyboardEventHandler,
  type MouseEventHandler,
  type ReactElement,
  type ReactNode,
} from 'react';
import {
  captureFocus,
  findFocusableElements,
  restoreFocus,
  type FocusToken,
} from '../../application/a11y/focusManagement';
import { cn, joinIds } from './utils';

type PopoverPlacement = 'top' | 'right' | 'bottom' | 'left';
type PopoverAlign = 'start' | 'center' | 'end';
type PopoverTone = 'default' | 'accent' | 'danger';

type PopoverTriggerProps = {
  readonly 'aria-controls'?: string;
  readonly 'aria-expanded'?: boolean;
  readonly 'aria-haspopup'?: 'dialog';
  readonly onClick?: MouseEventHandler<HTMLElement>;
  readonly onKeyDown?: KeyboardEventHandler<HTMLElement>;
};

export interface PopoverProps extends Omit<HTMLAttributes<HTMLDivElement>, 'children' | 'title'> {
  readonly trigger: ReactElement<PopoverTriggerProps>;
  readonly children: ReactNode;
  readonly title?: ReactNode;
  readonly description?: ReactNode;
  readonly placement?: PopoverPlacement;
  readonly align?: PopoverAlign;
  readonly tone?: PopoverTone;
  readonly open?: boolean;
  readonly defaultOpen?: boolean;
  readonly onOpenChange?: (open: boolean) => void;
  readonly disabled?: boolean;
  readonly closeOnInteractOutside?: boolean;
  readonly closeOnEscape?: boolean;
  readonly contentClassName?: string;
}

const POSITION_CLASSES: Record<PopoverPlacement, Record<PopoverAlign, string>> = {
  top: {
    start: 'bottom-full left-0 mb-ds-2',
    center: 'bottom-full left-1/2 mb-ds-2 -translate-x-1/2',
    end: 'bottom-full right-0 mb-ds-2',
  },
  right: {
    start: 'left-full top-0 ml-ds-2',
    center: 'left-full top-1/2 ml-ds-2 -translate-y-1/2',
    end: 'left-full bottom-0 ml-ds-2',
  },
  bottom: {
    start: 'left-0 top-full mt-ds-2',
    center: 'left-1/2 top-full mt-ds-2 -translate-x-1/2',
    end: 'right-0 top-full mt-ds-2',
  },
  left: {
    start: 'right-full top-0 mr-ds-2',
    center: 'right-full top-1/2 mr-ds-2 -translate-y-1/2',
    end: 'right-full bottom-0 mr-ds-2',
  },
};

const TONE_CLASSES: Record<PopoverTone, string> = {
  default: 'border-ds-border bg-ds-surface-elevated/98',
  accent: 'border-ds-accent/30 bg-ds-surface-elevated/98',
  danger: 'border-ds-error/30 bg-ds-surface-elevated/98',
};

function useControllableOpenState(
  open: boolean | undefined,
  defaultOpen: boolean,
  onOpenChange?: (nextOpen: boolean) => void,
): readonly [boolean, (nextOpen: boolean) => void] {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(defaultOpen);
  const isControlled = open !== undefined;
  const resolvedOpen = isControlled ? open : uncontrolledOpen;

  const setOpen = (nextOpen: boolean) => {
    if (!isControlled) {
      setUncontrolledOpen(nextOpen);
    }
    onOpenChange?.(nextOpen);
  };

  return [resolvedOpen, setOpen] as const;
}

function composeEventHandlers<EventType>(
  original?: (event: EventType) => void,
  next?: (event: EventType) => void,
): (event: EventType) => void {
  return (event) => {
    original?.(event);
    next?.(event);
  };
}

export function Popover({
  trigger,
  children,
  title,
  description,
  placement = 'bottom',
  align = 'start',
  tone = 'default',
  open,
  defaultOpen = false,
  onOpenChange,
  disabled = false,
  closeOnInteractOutside = true,
  closeOnEscape = true,
  contentClassName,
  className,
  'aria-describedby': ariaDescribedBy,
  ...rest
}: PopoverProps): ReactElement {
  const generatedId = useId().replace(/:/g, '');
  const panelId = `ds-popover-${generatedId}`;
  const titleId = title ? `${panelId}-title` : undefined;
  const descriptionId = description ? `${panelId}-description` : undefined;
  const [visible, setVisible] = useControllableOpenState(open, defaultOpen, onOpenChange);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const focusTokenRef = useRef<FocusToken>({ previous: null });
  const triggerElement = trigger as ReactElement<PopoverTriggerProps>;

  useEffect(() => {
    if (disabled && visible) {
      setVisible(false);
    }
  }, [disabled, visible, setVisible]);

  useEffect(() => {
    if (!visible) {
      return undefined;
    }

    focusTokenRef.current = captureFocus();
    const frameHandle = window.requestAnimationFrame(() => {
      const panel = panelRef.current;
      if (!panel) {
        return;
      }
      const [firstFocusable] = findFocusableElements(panel);
      (firstFocusable ?? panel).focus();
    });

    const handlePointerDown = (event: PointerEvent) => {
      if (!closeOnInteractOutside) {
        return;
      }
      const wrapper = wrapperRef.current;
      if (!wrapper || wrapper.contains(event.target as Node)) {
        return;
      }
      setVisible(false);
    };

    const handleFocusIn = (event: FocusEvent) => {
      if (!closeOnInteractOutside) {
        return;
      }
      const wrapper = wrapperRef.current;
      if (!wrapper || wrapper.contains(event.target as Node)) {
        return;
      }
      setVisible(false);
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('focusin', handleFocusIn);

    return () => {
      window.cancelAnimationFrame(frameHandle);
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('focusin', handleFocusIn);
      restoreFocus(focusTokenRef.current);
      focusTokenRef.current = { previous: null };
    };
  }, [closeOnInteractOutside, setVisible, visible]);

  const clonedTrigger = cloneElement(triggerElement, {
    'aria-controls': visible ? panelId : triggerElement.props['aria-controls'],
    'aria-expanded': visible,
    'aria-haspopup': 'dialog',
    onClick: composeEventHandlers(triggerElement.props.onClick, () => {
      if (!disabled) {
        setVisible(!visible);
      }
    }),
    onKeyDown: composeEventHandlers(triggerElement.props.onKeyDown, (event) => {
      if (event.key === 'Escape' && closeOnEscape && visible) {
        event.preventDefault();
        setVisible(false);
      }
    }),
  });

  return (
    <div ref={wrapperRef} className={cn('relative inline-flex', className)} {...rest}>
      {clonedTrigger}
      {visible && !disabled ? (
        <div
          ref={panelRef}
          id={panelId}
          role="dialog"
          aria-modal="false"
          aria-labelledby={titleId}
          aria-describedby={joinIds(descriptionId, ariaDescribedBy)}
          tabIndex={-1}
          className={cn(
            'absolute z-50 w-ds-popover rounded-ds-xl border p-ds-4 text-ds-text shadow-ds-lg',
            POSITION_CLASSES[placement][align],
            TONE_CLASSES[tone],
            contentClassName,
          )}
          onKeyDown={(event) => {
            if (event.key === 'Escape' && closeOnEscape) {
              event.preventDefault();
              setVisible(false);
            }
          }}
        >
          {title || description ? (
            <div className="min-w-0 space-y-ds-2">
              {title ? (
                <div id={titleId} className="text-ds-sm font-semibold text-ds-text">
                  {title}
                </div>
              ) : null}
              {description ? (
                <p id={descriptionId} className="text-ds-xs leading-5 text-ds-muted">
                  {description}
                </p>
              ) : null}
            </div>
          ) : null}
          <div className={cn(title || description ? 'mt-ds-3' : '')}>{children}</div>
        </div>
      ) : null}
    </div>
  );
}
