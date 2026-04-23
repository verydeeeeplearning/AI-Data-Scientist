import type { ReactElement, ReactNode } from 'react';
import { BottomNav } from './BottomNav';
import { OfflineBanner } from './OfflineBanner';
import type { MobileTab } from '../router';

interface MobileShellProps {
  readonly activeTab: MobileTab;
  readonly onTabChange: (tab: MobileTab) => void;
  readonly children: ReactNode;
}

export function MobileShell({
  activeTab,
  onTabChange,
  children,
}: MobileShellProps): ReactElement {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100dvh',
        background: 'var(--ds-bg)',
        color: 'var(--ds-text)',
        overflow: 'hidden',
      }}
    >
      <OfflineBanner />
      <main
        id="mobile-main-content"
        style={{
          flex: 1,
          overflowY: 'auto',
          overflowX: 'hidden',
          WebkitOverflowScrolling: 'touch',
          paddingTop: 'env(safe-area-inset-top, 0px)',
        }}
      >
        {children}
      </main>
      <BottomNav activeTab={activeTab} onTabChange={onTabChange} />
    </div>
  );
}
