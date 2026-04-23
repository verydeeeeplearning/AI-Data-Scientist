"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.THEME_OPTIONS = exports.DESIGN_SYSTEM_THEMES = exports.THEME_STORAGE_KEY = void 0;
exports.isTheme = isTheme;
exports.normalizeTheme = normalizeTheme;
exports.resolvePreferredTheme = resolvePreferredTheme;
exports.loadStoredTheme = loadStoredTheme;
exports.getNextTheme = getNextTheme;
exports.buildThemeTokenMap = buildThemeTokenMap;
exports.applyThemeToRoot = applyThemeToRoot;
exports.applyThemeToDocument = applyThemeToDocument;
const tokens_1 = require("../tokens");
const dark_1 = require("./dark");
const highContrast_1 = require("./highContrast");
const light_1 = require("./light");
exports.THEME_STORAGE_KEY = 'ds-agent-theme';
exports.DESIGN_SYSTEM_THEMES = {
    dark: dark_1.DARK_THEME,
    light: light_1.LIGHT_THEME,
    'high-contrast': highContrast_1.HIGH_CONTRAST_THEME,
};
exports.THEME_OPTIONS = [
    { value: 'dark', labelKey: 'settings.dark', descriptionKey: 'settings.themeOption.dark' },
    { value: 'light', labelKey: 'settings.light', descriptionKey: 'settings.themeOption.light' },
    {
        value: 'high-contrast',
        labelKey: 'settings.highContrast',
        descriptionKey: 'settings.themeOption.highContrast',
    },
];
const THEME_ORDER = ['dark', 'light', 'high-contrast'];
function isTheme(value) {
    return value === 'dark' || value === 'light' || value === 'high-contrast';
}
function normalizeTheme(value) {
    if (!value) {
        return null;
    }
    return isTheme(value) ? value : null;
}
function resolvePreferredTheme(matchMediaImpl) {
    if (typeof window === 'undefined' && !matchMediaImpl) {
        return 'dark';
    }
    const matchMediaFn = matchMediaImpl ?? window.matchMedia.bind(window);
    return matchMediaFn('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}
function loadStoredTheme(storage, matchMediaImpl) {
    const stored = storage?.getItem(exports.THEME_STORAGE_KEY) ?? null;
    return normalizeTheme(stored) ?? resolvePreferredTheme(matchMediaImpl);
}
function getNextTheme(theme) {
    const index = THEME_ORDER.indexOf(theme);
    return THEME_ORDER[(index + 1) % THEME_ORDER.length];
}
function buildThemeTokenMap(theme) {
    return {
        ...tokens_1.DESIGN_SYSTEM_BASE_TOKENS,
        ...exports.DESIGN_SYSTEM_THEMES[theme].variables,
    };
}
function applyThemeToRoot(root, theme) {
    const definition = exports.DESIGN_SYSTEM_THEMES[theme];
    const tokenMap = buildThemeTokenMap(theme);
    for (const [key, value] of Object.entries(tokenMap)) {
        root.style.setProperty(key, value);
    }
    root.dataset.theme = theme;
    root.classList.remove('dark', 'light', 'hc');
    root.classList.add(definition.className);
    root.style.colorScheme = definition.colorScheme;
}
function applyThemeToDocument(theme) {
    if (typeof document === 'undefined') {
        return;
    }
    applyThemeToRoot(document.documentElement, theme);
}
