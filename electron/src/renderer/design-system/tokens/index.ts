import { MOTION_TOKENS } from './motion';
import { RADIUS_TOKENS } from './radius';
import { SHADOW_TOKENS } from './shadow';
import { SPACING_TOKENS } from './spacing';
import { TYPOGRAPHY_TOKENS } from './typography';

export const DESIGN_SYSTEM_BASE_TOKENS = {
  ...SPACING_TOKENS,
  ...TYPOGRAPHY_TOKENS,
  ...RADIUS_TOKENS,
  ...SHADOW_TOKENS,
  ...MOTION_TOKENS,
} as const;

export type DesignTokenMap = Record<string, string>;

