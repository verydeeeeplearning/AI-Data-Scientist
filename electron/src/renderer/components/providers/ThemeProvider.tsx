import { useEffect, type ReactNode } from 'react';
import { applyThemeToDocument } from '../../design-system/themes';
import { useConfigStore } from '../../stores/configStore';

interface ThemeProviderProps {
  readonly children: ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const theme = useConfigStore((state) => state.theme);

  useEffect(() => {
    applyThemeToDocument(theme);
  }, [theme]);

  return <>{children}</>;
}
