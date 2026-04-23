export const COLOR_VARIABLES = {
  bg: '--ds-color-bg',
  surface: '--ds-color-surface',
  surfaceElevated: '--ds-color-surface-elevated',
  border: '--ds-color-border',
  borderStrong: '--ds-color-border-strong',
  text: '--ds-color-text',
  muted: '--ds-color-muted',
  accent: '--ds-color-accent',
  accentHover: '--ds-color-accent-hover',
  accentContrast: '--ds-color-accent-contrast',
  success: '--ds-color-success',
  warning: '--ds-color-warning',
  error: '--ds-color-error',
  info: '--ds-color-info',
  overlay: '--ds-color-overlay',
  ring: '--ds-color-ring',
} as const;

export type ColorVariableName = (typeof COLOR_VARIABLES)[keyof typeof COLOR_VARIABLES];

