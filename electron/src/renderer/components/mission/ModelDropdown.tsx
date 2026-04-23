import { useI18n } from '../../stores/i18nStore';
import type { ModelCatalogEntry } from '../../domain/llm/modelCapability';
import {
  MissionDropdownMenu,
  type MissionDropdownItem,
} from './MissionDropdownMenu';

interface Props {
  readonly open: boolean;
  readonly current: string;
  readonly options: ReadonlyArray<ModelCatalogEntry>;
  readonly onSelect: (modelId: string) => void;
  readonly onClose: () => void;
}

export function ModelDropdown({
  open,
  current,
  options,
  onSelect,
  onClose,
}: Props) {
  const { t } = useI18n();
  const items: ReadonlyArray<MissionDropdownItem<string>> = options.slice(0, 8).map(
    (entry) => ({
      key: entry.id,
      value: entry.id,
      label: entry.displayName ?? entry.id,
      description: entry.id,
      active: entry.id === current,
    }),
  );

  return (
    <MissionDropdownMenu<string>
      open={open}
      title={t('mission.dropdown.model.title')}
      items={items}
      onSelect={onSelect}
      onClose={onClose}
    />
  );
}
