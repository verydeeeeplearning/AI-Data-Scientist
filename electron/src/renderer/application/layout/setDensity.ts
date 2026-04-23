import type { DensityMode } from '../../domain/layout/density';
import type { SetDensityPort } from './setDensityPort';

export function setDensity(port: SetDensityPort, mode: DensityMode): DensityMode {
  port.persist(mode);
  port.applyToDocument(mode);
  return mode;
}
