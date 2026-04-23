import {
  DEFAULT_DENSITY_MODE,
  isDensityMode,
  type DensityMode,
} from '../../domain/layout/density';
import { applyDensityScale } from '../../application/layout/applyDensityScale';

export const DENSITY_STORAGE_KEY = 'ds-agent-density:v1';

export function loadStoredDensity(): DensityMode {
  if (typeof window === 'undefined') {
    return DEFAULT_DENSITY_MODE;
  }
  try {
    const raw = window.localStorage.getItem(DENSITY_STORAGE_KEY);
    if (raw && isDensityMode(raw)) {
      return raw;
    }
  } catch {
    // Storage unavailable (private mode, etc.) — fall through to default.
  }
  return DEFAULT_DENSITY_MODE;
}

export function persistDensity(mode: DensityMode): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    window.localStorage.setItem(DENSITY_STORAGE_KEY, mode);
  } catch {
    // Quota or permission denied — silently drop; runtime still applies.
  }
}

export function applyDensityToDocument(mode: DensityMode): void {
  if (typeof document === 'undefined') {
    return;
  }
  document.documentElement.setAttribute('data-density', mode);
  const overrides = applyDensityScale(mode);
  for (const [variable, value] of Object.entries(overrides)) {
    document.documentElement.style.setProperty(variable, value);
  }
}
