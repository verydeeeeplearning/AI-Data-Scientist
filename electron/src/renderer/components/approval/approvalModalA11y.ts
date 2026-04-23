import { createFocusTrap } from '../../application/a11y/focusManagement';

export interface ApprovalModalKeyEvent {
  key: string;
  shiftKey?: boolean;
  preventDefault(): void;
}

export interface ApprovalModalA11yController {
  activate(): void;
  deactivate(): void;
  handleKeyDown(event: ApprovalModalKeyEvent): 'tab' | 'escape' | null;
}

export function createApprovalModalA11yController(
  container: HTMLElement,
  options: { document?: Document } = {},
): ApprovalModalA11yController {
  const trap = createFocusTrap(container, options);

  return {
    activate(): void {
      trap.activate();
    },
    deactivate(): void {
      trap.deactivate();
    },
    handleKeyDown(event: ApprovalModalKeyEvent): 'tab' | 'escape' | null {
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
