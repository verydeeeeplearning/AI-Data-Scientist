import { getDensityScale, type DensityMode } from '../../domain/layout/density';

export interface DensityCssOverrides {
  readonly [variable: `--${string}`]: string;
}

const SCALABLE_SPACING_VARS = [
  '--ds-space-1',
  '--ds-space-2',
  '--ds-space-3',
  '--ds-space-4',
  '--ds-space-5',
  '--ds-space-6',
  '--ds-space-8',
  '--ds-space-10',
  '--ds-space-12',
  '--ds-space-16',
] as const;

const BASE_SPACING_REM: Record<(typeof SCALABLE_SPACING_VARS)[number], number> = {
  '--ds-space-1': 0.25,
  '--ds-space-2': 0.5,
  '--ds-space-3': 0.75,
  '--ds-space-4': 1,
  '--ds-space-5': 1.25,
  '--ds-space-6': 1.5,
  '--ds-space-8': 2,
  '--ds-space-10': 2.5,
  '--ds-space-12': 3,
  '--ds-space-16': 4,
};

const SCALABLE_FONT_VARS = [
  '--ds-font-size-2xs',
  '--ds-font-size-xs',
  '--ds-font-size-sm',
  '--ds-font-size-md',
  '--ds-font-size-lg',
  '--ds-font-size-xl',
  '--ds-font-size-2xl',
] as const;

const BASE_FONT_REM: Record<(typeof SCALABLE_FONT_VARS)[number], number> = {
  '--ds-font-size-2xs': 0.6875,
  '--ds-font-size-xs': 0.75,
  '--ds-font-size-sm': 0.875,
  '--ds-font-size-md': 1,
  '--ds-font-size-lg': 1.125,
  '--ds-font-size-xl': 1.25,
  '--ds-font-size-2xl': 1.5,
};

function formatRem(value: number): string {
  // Three-decimal precision keeps the rendered px integer at typical 16px root.
  return `${Number(value.toFixed(3))}rem`;
}

export function applyDensityScale(mode: DensityMode): DensityCssOverrides {
  const scale = getDensityScale(mode);
  const overrides: Record<string, string> = {};
  for (const variable of SCALABLE_SPACING_VARS) {
    overrides[variable] = formatRem(BASE_SPACING_REM[variable] * scale.spacing);
  }
  for (const variable of SCALABLE_FONT_VARS) {
    overrides[variable] = formatRem(BASE_FONT_REM[variable] * scale.font);
  }
  return overrides as DensityCssOverrides;
}
