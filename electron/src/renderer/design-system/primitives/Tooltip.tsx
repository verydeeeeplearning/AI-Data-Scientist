import {
  Children,
  cloneElement,
  useEffect,
  useId,
  useRef,
  useState,
  type FocusEventHandler,
  type HTMLAttributes,
  type KeyboardEventHandler,
  type MouseEventHandler,
  type ReactElement,
  type ReactNode,
} from 'react';
import { cn, joinIds } from './utils';

type TooltipPlacement = 'top' | 'right' | 'bottom' | 'left';
type TooltipTone = 'default' | 'accent' | 'danger';

type TooltipTriggerProps = {
  readonly 'aria-describedby'?: string;
  readonly onBlur?: FocusEventHandler<HTMLElement>;
  readonly onFocus?: FocusEventHandler<HTMLElement>;
  readonly onKeyDown?: KeyboardEventHandler<HTMLElement>;
  readonly onMouseEnter?: MouseEventHandler<HTMLElement>;
  readonly onMouseLeave?: MouseEventHandler<HTMLElement>;
};

export interface TooltipProps extends Omit<HTMLAttributes<HTMLSpanElement>, 'children' | 'content'> {
  readonly children: ReactElement<TooltipTriggerProps>;
  readonly content: ReactNode;
  readonly placement?: TooltipPlacement;
  readonly tone?: TooltipTone;
  readonly open?: boolean;
  readonly defaultOpen?: boolean;
  readonly onOpenChange?: (open: boolean) => void;
  readonly delayMs?: number;
  readonly disabled?: boolean;
}

const PLACEMENT_CLASSES: Record<TooltipPlacement, string> = {
  top: 'bottom-full left-1/2 mb-ds-2 -translate-x-1/2',
  right: 'left-full top-1/2 ml-ds-2 -translate-y-1/2',
  bottom: 'left-1/2 top-full mt-ds-2 -translate-x-1/2',
  left: 'right-full top-1/2 mr-ds-2 -translate-y-1/2',
};

const TONE_CLASSES: Record<TooltipTone, string> = {
  default: 'border-ds-border bg-ds-surface-elevated/96 text-ds-text',
  accent: 'border-ds-accent/30 bg-ds-accent/10 text-ds-text',
  danger: 'border-ds-error/30 bg-ds-error/10 text-ds-text',
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

export function Tooltip({
  children,
  content,
  placement = 'top',
  tone = 'default',
  open,
  defaultOpen = false,
  onOpenChange,
  delayMs = 150,
  disabled = false,
  className,
  ...rest
}: TooltipProps): ReactElement {
  const generatedId = useId().replace(/:/g, '');
  const tooltipId = `ds-tooltip-${generatedId}`;
  const [visible, setVisible] = useControllableOpenState(open, defaultOpen, onOpenChange);
  const delayTimerRef = useRef<number | null>(null);
  const trigger = Children.only(children) as ReactElement<TooltipTriggerProps>;

  const clearDelayTimer = () => {
    if (delayTimerRef.current !== null) {
      window.clearTimeout(delayTimerRef.current);
      delayTimerRef.current = null;
    }
  };

  const showTooltip = (immediate: boolean) => {
    if (disabled) {
      return;
    }
    clearDelayTimer();
    if (immediate || delayMs <= 0) {
      setVisible(true);
      return;
    }
    delayTimerRef.current = window.setTimeout(() => {
      setVisible(true);
      delayTimerRef.current = null;
    }, delayMs);
  };

  const hideTooltip = () => {
    clearDelayTimer();
    setVisible(false);
  };

  useEffect(() => clearDelayTimer, []);

  useEffect(() => {
    if (disabled && visible) {
      hideTooltip();
    }
  }, [disabled, visible]);

  const triggerElement = cloneElement(trigger, {
    'aria-describedby': disabled
      ? trigger.props['aria-describedby']
      : joinIds(trigger.props['aria-describedby'], visible ? tooltipId : undefined),
    onFocus: composeEventHandlers(trigger.props.onFocus, () => showTooltip(true)),
    onBlur: composeEventHandlers(trigger.props.onBlur, hideTooltip),
    onMouseEnter: composeEventHandlers(trigger.props.onMouseEnter, () => showTooltip(false)),
    onMouseLeave: composeEventHandlers(trigger.props.onMouseLeave, hideTooltip),
    onKeyDown: composeEventHandlers(trigger.props.onKeyDown, (event) => {
      if (event.key === 'Escape') {
        hideTooltip();
      }
    }),
  });

  return (
    <span
      className={cn('relative inline-flex', className)}
      data-state={visible ? 'open' : 'closed'}
      {...rest}
    >
      {triggerElement}
      {!disabled && visible ? (
        <span
          id={tooltipId}
          role="tooltip"
          className={cn(
            'pointer-events-none absolute z-50 max-w-ds-tooltip rounded-ds-lg border px-ds-3 py-ds-2 text-ds-xs leading-5 shadow-ds-md',
            PLACEMENT_CLASSES[placement],
            TONE_CLASSES[tone],
          )}
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}
