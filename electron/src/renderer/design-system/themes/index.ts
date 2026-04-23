import { DESIGN_SYSTEM_BASE_TOKENS, type DesignTokenMap } from '../tokens';
import { DARK_THEME } from './dark';
import { HIGH_CONTRAST_THEME } from './highContrast';
import { LIGHT_THEME } from './light';
import type { Theme, ThemeDefinition } from './types';

export type { Theme, ThemeDefinition } from './types';

export const THEME_STORAGE_KEY = 'ds-agent-theme';

export const DESIGN_SYSTEM_THEMES: Readonly<Record<Theme, ThemeDefinition>> = {
  dark: DARK_THEME,
  light: LIGHT_THEME,
  'high-contrast': HIGH_CONTRAST_THEME,
};

export const THEME_OPTIONS = [
  { value: 'dark', labelKey: 'settings.dark', descriptionKey: 'settings.themeOption.dark' },
  { value: 'light', labelKey: 'settings.light', descriptionKey: 'settings.themeOption.light' },
  {
    value: 'high-contrast',
    labelKey: 'settings.highContrast',
    descriptionKey: 'settings.themeOption.highContrast',
  },
] as const satisfies ReadonlyArray<{
  value: Theme;
  labelKey: string;
  descriptionKey: string;
}>;

const THEME_ORDER: readonly Theme[] = ['dark', 'light', 'high-contrast'];

export function isTheme(value: unknown): value is Theme {
  return value === 'dark' || value === 'light' || value === 'high-contrast';
}

export function normalizeTheme(value: string | null | undefined): Theme | null {
  if (!value) {
    return null;
  }
  return isTheme(value) ? value : null;
}

export function resolvePreferredTheme(matchMediaImpl?: (query: string) => MediaQueryList): Theme {
  if (typeof window === 'undefined' && !matchMediaImpl) {
    return 'dark';
  }
  const matchMediaFn = matchMediaImpl ?? window.matchMedia.bind(window);
  return matchMediaFn('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function loadStoredTheme(
  storage?: Pick<Storage, 'getItem'> | null,
  matchMediaImpl?: (query: string) => MediaQueryList,
): Theme {
  const stored = storage?.getItem(THEME_STORAGE_KEY) ?? null;
  return normalizeTheme(stored) ?? resolvePreferredTheme(matchMediaImpl);
}

export function getNextTheme(theme: Theme): Theme {
  const index = THEME_ORDER.indexOf(theme);
  return THEME_ORDER[(index + 1) % THEME_ORDER.length];
}

export function buildThemeTokenMap(theme: Theme): DesignTokenMap {
  return {
    ...DESIGN_SYSTEM_BASE_TOKENS,
    ...DESIGN_SYSTEM_THEMES[theme].variables,
  };
}

export function applyThemeToRoot(root: HTMLElement, theme: Theme): void {
  const definition = DESIGN_SYSTEM_THEMES[theme];
  const tokenMap = buildThemeTokenMap(theme);
  for (const [key, value] of Object.entries(tokenMap)) {
    root.style.setProperty(key, value);
  }
  root.dataset.theme = theme;
  root.classList.remove('dark', 'light', 'hc');
  root.classList.add(definition.className);
  root.style.colorScheme = definition.colorScheme;
}

export function applyThemeToDocument(theme: Theme): void {
  if (typeof document === 'undefined') {
    return;
  }
  applyThemeToRoot(document.documentElement, theme);
}
