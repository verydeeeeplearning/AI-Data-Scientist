import { useConfigStore } from '../stores/configStore';
import type { DensityMode } from '../domain/layout/density';

export interface UseDensityResult {
  readonly density: DensityMode;
  readonly setDensity: (mode: DensityMode) => void;
}

export function useDensity(): UseDensityResult {
  const density = useConfigStore((state) => state.density);
  const setDensity = useConfigStore((state) => state.setDensity);
  return { density, setDensity };
}
