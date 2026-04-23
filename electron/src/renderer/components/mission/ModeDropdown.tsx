import { useI18n } from '../../stores/i18nStore';
import {
  MissionDropdownMenu,
  type MissionDropdownItem,
} from './MissionDropdownMenu';

export type MissionMode = 'auto' | 'supervised' | 'step-by-step';

interface Props {
  readonly open: boolean;
  readonly current: MissionMode;
  readonly onSelect: (mode: MissionMode) => void;
  readonly onClose: () => void;
}

const MISSION_MODE_OPTIONS: ReadonlyArray<MissionMode> = [
  'auto',
  'supervised',
  'step-by-step',
];

export function ModeDropdown({ open, current, onSelect, onClose }: Props) {
  const { t } = useI18n();
  const items: ReadonlyArray<MissionDropdownItem<MissionMode>> = MISSION_MODE_OPTIONS.map(
    (mode) => ({
      key: mode,
      value: mode,
      label: formatLabel(mode, t),
      active: current === mode,
    }),
  );

  return (
    <MissionDropdownMenu<MissionMode>
      open={open}
      title={t('mission.dropdown.mode.title')}
      items={items}
      onSelect={onSelect}
      onClose={onClose}
    />
  );
}

function formatLabel(mode: MissionMode, t: (key: string) => string): string {
  switch (mode) {
    case 'auto':
      return t('mode.auto');
    case 'supervised':
      return t('mode.supervised');
    case 'step-by-step':
      return t('mode.step');
    default:
      return mode;
  }
}
