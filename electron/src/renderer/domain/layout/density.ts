export const DENSITY_MODES = ['compact', 'comfortable', 'spacious'] as const;
export type DensityMode = (typeof DENSITY_MODES)[number];

export const DEFAULT_DENSITY_MODE: DensityMode = 'comfortable';

export interface DensityScale {
  readonly spacing: number;
  readonly font: number;
}

const SCALE_TABLE: Record<DensityMode, DensityScale> = {
  compact: { spacing: 0.75, font: 0.9 },
  comfortable: { spacing: 1, font: 1 },
  spacious: { spacing: 1.25, font: 1.1 },
};

export function isDensityMode(value: unknown): value is DensityMode {
  return typeof value === 'string'
    && (DENSITY_MODES as readonly string[]).includes(value);
}

export function getDensityScale(mode: DensityMode): DensityScale {
  return SCALE_TABLE[mode];
}
