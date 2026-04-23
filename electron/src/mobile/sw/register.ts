/**
 * Mobile service-worker registration entry.
 *
 * Skipped in dev (Vite dev server serves modules untranspiled, which the SW
 * cannot precache safely) and in environments without `serviceWorker`
 * support (e.g. embedded webviews used for a11y testing).
 */

export function registerMobileServiceWorker(): void {
  if (typeof window === 'undefined') return;
  if (!('serviceWorker' in navigator)) return;

  // Vite injects `import.meta.env.DEV` at build time. Skip dev to keep HMR
  // and the live module graph functional.
  try {
    if (import.meta.env?.DEV) return;
  } catch {
    // If env access throws, fall through and attempt registration.
  }

  // Register on `load` so we don't compete with first-paint.
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('./sw.js', { scope: './' })
      .catch((err: unknown) => {
        // Registration failures are non-fatal; the page still works online.
        // eslint-disable-next-line no-console
        console.warn('[mobile-sw] registration failed', err);
      });
  });
}
