import type { ThemeDefinition } from './types';

export const HIGH_CONTRAST_THEME: ThemeDefinition = {
  id: 'high-contrast',
  className: 'hc',
  colorScheme: 'dark',
  variables: {
    '--ds-color-bg': '#000000',
    '--ds-color-surface': '#000000',
    '--ds-color-surface-elevated': '#050505',
    '--ds-color-border': '#ffffff',
    '--ds-color-border-strong': '#ffffff',
    '--ds-color-text': '#ffffff',
    '--ds-color-muted': '#f5f5f5',
    '--ds-color-accent': '#00ffff',
    '--ds-color-accent-hover': '#7df9ff',
    '--ds-color-accent-contrast': '#000000',
    '--ds-color-success': '#00ff7f',
    '--ds-color-warning': '#ffd400',
    '--ds-color-error': '#ff5c5c',
    '--ds-color-info': '#7dd3fc',
    '--ds-color-overlay': 'rgba(0, 0, 0, 0.88)',
    '--ds-color-ring': '#ffffff',
  },
};

