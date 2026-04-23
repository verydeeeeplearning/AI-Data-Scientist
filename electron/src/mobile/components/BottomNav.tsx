import type { ReactElement } from 'react';
import { Target, Play, Archive, ShieldCheck, Settings } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { MobileTab } from '../router';
import { MOBILE_TABS } from '../router';

const TAB_ICONS: Record<MobileTab, typeof Target> = {
  mission: Target,
  runs: Play,
  artifacts: Archive,
  approvals: ShieldCheck,
  settings: Settings,
};

interface BottomNavProps {
  readonly activeTab: MobileTab;
  readonly onTabChange: (tab: MobileTab) => void;
}

export function BottomNav({ activeTab, onTabChange }: BottomNavProps): ReactElement {
  const { t } = useTranslation('mobile');

  return (
    <nav
      role="tablist"
      aria-label={t('nav.primary')}
      style={{
        display: 'flex',
        borderTop: '1px solid var(--ds-border)',
        background: 'var(--ds-surface)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}
    >
      {MOBILE_TABS.map((tab) => {
        const Icon = TAB_ICONS[tab];
        const isActive = activeTab === tab;
        return (
          <button
            key={tab}
            role="tab"
            aria-selected={isActive}
            aria-current={isActive ? 'page' : undefined}
            onClick={() => onTabChange(tab)}
            data-tab={tab}
            style={{
              flex: 1,
              minHeight: '44px',
              minWidth: '44px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '2px',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: isActive ? 'var(--ds-accent)' : 'var(--ds-muted)',
              fontSize: '10px',
              fontWeight: isActive ? 600 : 400,
              padding: '8px 4px',
            }}
          >
            <Icon size={22} aria-hidden="true" />
            <span>{t(`nav.${tab}`)}</span>
          </button>
        );
      })}
    </nav>
  );
}
