/**
 * Focus management utilities (WCAG 2.4.3 Focus Order, 2.4.7 Focus Visible).
 *
 * Pure DOM API — no React or 3rd-party lib (ADR-0008). Components in
 * higher layers wrap these in hooks (e.g. `useFocusTrap`).
 */

const FOCUSABLE_TAGS = new Set(['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA']);

interface ElementLike {
  tagName: string;
  hasAttribute(name: string): boolean;
  getAttribute(name: string): string | null;
  focus(): void;
  querySelectorAll(selector: string): ArrayLike<unknown>;
}

interface DocumentLike {
  activeElement: unknown;
}

interface FocusOptions {
  document?: DocumentLike;
}

export interface FocusToken {
  previous: { focus(): void } | null;
}

export function isFocusable(el: HTMLElement): boolean {
  const e = el as unknown as ElementLike;
  if (!e || typeof e.tagName !== 'string') return false;
  if (e.hasAttribute('disabled')) return false;

  const tabindex = e.getAttribute('tabindex');
  if (tabindex !== null) {
    const value = Number(tabindex);
    if (Number.isFinite(value) && value < 0) return false;
  }

  if (FOCUSABLE_TAGS.has(e.tagName)) {
    return true;
  }
  if (e.tagName === 'A' && e.getAttribute('href') !== null) {
    return true;
  }
  // Element with explicit non-negative tabindex is focusable
  if (tabindex !== null) {
    const value = Number(tabindex);
    if (Number.isFinite(value) && value >= 0) return true;
  }
  return false;
}

export function findFocusableElements(container: HTMLElement): HTMLElement[] {
  const c = container as unknown as ElementLike;
  const all = Array.from(c.querySelectorAll('*')) as unknown as HTMLElement[];
  return all.filter((el) => isFocusable(el));
}

export function captureFocus(options: FocusOptions = {}): FocusToken {
  const doc = options.document ?? (typeof document !== 'undefined' ? document : null);
  if (!doc) return { previous: null };
  const active = doc.activeElement;
  if (active && typeof (active as { focus?: unknown }).focus === 'function') {
    return { previous: active as { focus(): void } };
  }
  return { previous: null };
}

export function restoreFocus(token: FocusToken): void {
  if (!token || !token.previous) return;
  try {
    token.previous.focus();
  } catch {
    // Element may have been removed from the DOM; swallow silently.
  }
}

export interface FocusTrap {
  activate(): void;
  deactivate(): void;
  cycle(direction: 'forward' | 'backward'): HTMLElement | null;
}

export function createFocusTrap(
  container: HTMLElement,
  options: FocusOptions = {},
): FocusTrap {
  const doc = options.document ?? (typeof document !== 'undefined' ? document : null);
  let priorToken: FocusToken = { previous: null };
  let active = false;

  function getFocusables(): HTMLElement[] {
    return findFocusableElements(container);
  }

  return {
    activate(): void {
      if (active) return;
      active = true;
      priorToken = captureFocus({ document: doc ?? undefined });
      const focusables = getFocusables();
      if (focusables.length > 0) {
        focusables[0].focus();
      } else {
        container.focus();
      }
    },
    deactivate(): void {
      if (!active) return;
      active = false;
      restoreFocus(priorToken);
      priorToken = { previous: null };
    },
    cycle(direction: 'forward' | 'backward'): HTMLElement | null {
      const focusables = getFocusables();
      if (focusables.length === 0) return null;
      const current = doc ? doc.activeElement : null;
      const idx = focusables.findIndex((el) => (el as unknown) === current);
      let next: HTMLElement;
      if (direction === 'forward') {
        next = idx === -1 || idx === focusables.length - 1 ? focusables[0] : focusables[idx + 1];
      } else {
        next = idx <= 0 ? focusables[focusables.length - 1] : focusables[idx - 1];
      }
      next.focus();
      return next;
    },
  };
}
