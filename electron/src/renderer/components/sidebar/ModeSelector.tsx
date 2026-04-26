/**
 * Mode selector — auto / supervised / step-by-step radio buttons.
 */

import { Settings } from 'lucide-react';
import { Card, Radio } from '../../design-system/primitives';
import { useAgentStore } from '../../stores/agentStore';
import { useI18n } from '../../stores/i18nStore';

interface Props {
  onChange: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
}

const MODES: Array<{
  value: 'auto' | 'supervised' | 'step-by-step';
  labelKey: string;
  descKey: string;
}> = [
  {
    value: 'auto',
    labelKey: 'settings.modeSelector.auto.label',
    descKey: 'settings.modeSelector.auto.description',
  },
  {
    value: 'supervised',
    labelKey: 'settings.modeSelector.supervised.label',
    descKey: 'settings.modeSelector.supervised.description',
  },
  {
    value: 'step-by-step',
    labelKey: 'settings.modeSelector.stepByStep.label',
    descKey: 'settings.modeSelector.stepByStep.description',
  },
];

export function ModeSelector({ onChange }: Props) {
  const { mode } = useAgentStore();
  const { t } = useI18n();

  return (
    <div className="px-3 py-1.5">
      <fieldset className="space-y-ds-3" aria-label={t('settings.modeSelector.ariaLabel')}>
        <legend className="mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-ds-muted">
          <Settings size={12} aria-hidden="true" />
          {t('settings.mode')}
        </legend>
        <Card className="space-y-ds-2 bg-ds-bg/40 px-ds-3 py-ds-3 shadow-none">
          {MODES.map((m) => (
            <Radio
              key={m.value}
              name="sidebar-execution-mode"
              value={m.value}
              checked={mode === m.value}
              onChange={() => onChange(m.value)}
              label={t(m.labelKey)}
              description={t(m.descKey)}
              className="rounded-ds-lg px-ds-2 py-ds-2 hover:bg-ds-bg/60"
            />
          ))}
        </Card>
      </fieldset>
    </div>
  );
}
