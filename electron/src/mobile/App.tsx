import type { ReactElement } from 'react';
import { MobileRouter } from './router';
import { MobileRuntimeProvider } from './runtime';

export default function App(): ReactElement {
  return (
    <MobileRuntimeProvider>
      <MobileRouter />
    </MobileRuntimeProvider>
  );
}
