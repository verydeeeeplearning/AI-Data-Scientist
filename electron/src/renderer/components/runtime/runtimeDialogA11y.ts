import { createFocusTrap } from '../../application/a11y/focusManagement';

export interface RuntimeDialogKeyEvent {
  key: string;
  shiftKey?: boolean;
  preventDefault(): void;
}

export interface RuntimeDialogA11yController {
  activate(): void;
  deactivate(): void;
  handleKeyDown(event: RuntimeDialogKeyEvent): 'tab' | 'escape' | null;
}

export function createRuntimeDialogA11yController(
  container: HTMLElement,
  options: { document?: Document } = {},
): RuntimeDialogA11yController {
  const trap = createFocusTrap(container, options);

  return {
    activate(): void {
      trap.activate();
    },
    deactivate(): void {
      trap.deactivate();
    },
    handleKeyDown(event: RuntimeDialogKeyEvent): 'tab' | 'escape' | null {
      if (event.key === 'Tab') {
        event.preventDefault();
        trap.cycle(event.shiftKey ? 'backward' : 'forward');
        return 'tab';
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        return 'escape';
      }
      return null;
    },
  };
}
