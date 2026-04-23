import { useState, type ReactElement } from 'react';
import { MobileShell } from './components/MobileShell';
import { MissionPage } from './pages/MissionPage';
import { RunsPage } from './pages/RunsPage';
import { ArtifactsPage } from './pages/ArtifactsPage';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { SettingsPage } from './pages/SettingsPage';

export type MobileTab = 'mission' | 'runs' | 'artifacts' | 'approvals' | 'settings';

export const MOBILE_TABS: readonly MobileTab[] = [
  'mission',
  'runs',
  'artifacts',
  'approvals',
  'settings',
];

function renderPage(tab: MobileTab): ReactElement {
  switch (tab) {
    case 'mission':
      return <MissionPage />;
    case 'runs':
      return <RunsPage />;
    case 'artifacts':
      return <ArtifactsPage />;
    case 'approvals':
      return <ApprovalsPage />;
    case 'settings':
      return <SettingsPage />;
  }
}

export function MobileRouter(): ReactElement {
  const [activeTab, setActiveTab] = useState<MobileTab>('mission');
  return (
    <MobileShell activeTab={activeTab} onTabChange={setActiveTab}>
      {renderPage(activeTab)}
    </MobileShell>
  );
}
