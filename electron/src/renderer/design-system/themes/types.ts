export type Theme = 'dark' | 'light' | 'high-contrast';

export interface ThemeDefinition {
  readonly id: Theme;
  readonly className: 'dark' | 'light' | 'hc';
  readonly colorScheme: 'dark' | 'light';
  readonly variables: Record<string, string>;
}

