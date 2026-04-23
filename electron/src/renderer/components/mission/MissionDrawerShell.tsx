import type { ReactNode } from 'react';
import { DrawerShell } from '../../design-system/primitives/DrawerShell';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  readonly open: boolean;
  readonly title: string;
  readonly description?: string;
  readonly onClose: () => void;
  readonly children: ReactNode;
  readonly footer?: ReactNode;
  readonly testId?: string;
}

export function MissionDrawerShell({
  open,
  title,
  description,
  onClose,
  children,
  footer,
  testId,
}: Props) {
  const { t } = useI18n();

  return (
    <DrawerShell
      open={open}
      title={title}
      description={description}
      footer={footer}
      dismissLabel={t('mission.drawer.close')}
      onDismiss={onClose}
      bodyClassName="text-ds-sm text-ds-text"
      data-testid={testId}
    >
      {children}
    </DrawerShell>
  );
}
