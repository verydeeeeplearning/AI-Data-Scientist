import type { DensityMode } from '../../domain/layout/density';

export interface SetDensityPort {
  readonly persist: (mode: DensityMode) => void;
  readonly applyToDocument: (mode: DensityMode) => void;
}
