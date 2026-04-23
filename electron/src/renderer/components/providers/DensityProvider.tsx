import { useEffect, type ReactNode } from 'react';
import { applyDensityScale } from '../../application/layout/applyDensityScale';
import type { DensityMode } from '../../domain/layout/density';
import { useConfigStore } from '../../stores/configStore';

interface DensityProviderProps {
  readonly children: ReactNode;
}

function applyToDocument(mode: DensityMode): void {
  if (typeof document === 'undefined') {
    return;
  }
  document.documentElement.setAttribute('data-density', mode);
  const overrides = applyDensityScale(mode);
  for (const [variable, value] of Object.entries(overrides)) {
    document.documentElement.style.setProperty(variable, value);
  }
}

export function DensityProvider({ children }: DensityProviderProps) {
  const density = useConfigStore((state) => state.density);

  useEffect(() => {
    applyToDocument(density);
  }, [density]);

  return <>{children}</>;
}
