/**
 * Aria-live region helper (WCAG 4.1.3 Status Messages).
 *
 * Pure DOM API — no React. Components wrap `useAriaLive(politeness)`
 * around the announcer. The single document-level live region prevents
 * conflicting announcements per WCAG technique ARIA22.
 */

export type AriaLivePoliteness = 'polite' | 'assertive';

const REGION_ID = 'ds-a11y-live-region';

interface AnnounceOptions {
  document?: Document;
  politeness?: AriaLivePoliteness;
  clearAfterMs?: number;
}

function ensureRegion(doc: Document, politeness: AriaLivePoliteness): HTMLElement {
  let region = doc.getElementById(REGION_ID);
  if (!region) {
    region = doc.createElement('div');
    region.id = REGION_ID;
    region.setAttribute('aria-live', politeness);
    region.setAttribute('aria-atomic', 'true');
    region.setAttribute(
      'style',
      [
        'position: absolute',
        'width: 1px',
        'height: 1px',
        'padding: 0',
        'margin: -1px',
        'overflow: hidden',
        'clip: rect(0, 0, 0, 0)',
        'white-space: nowrap',
        'border: 0',
      ].join(';'),
    );
    doc.body.appendChild(region);
  } else if (region.getAttribute('aria-live') !== politeness) {
    region.setAttribute('aria-live', politeness);
  }
  return region;
}

export function announce(message: string, options: AnnounceOptions = {}): void {
  const doc = options.document ?? (typeof document !== 'undefined' ? document : null);
  if (!doc) return;
  const politeness = options.politeness ?? 'polite';
  const region = ensureRegion(doc, politeness);
  region.textContent = '';
  // Forcing a reflow gap helps screen readers re-announce identical strings.
  void region.offsetHeight;
  region.textContent = message;

  const clearAfter = options.clearAfterMs ?? 5000;
  if (clearAfter > 0 && typeof window !== 'undefined') {
    window.setTimeout(() => {
      if (region.textContent === message) {
        region.textContent = '';
      }
    }, clearAfter);
  }
}
