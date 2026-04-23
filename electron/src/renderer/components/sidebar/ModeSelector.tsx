/**
 * Mode selector — auto / supervised / step-by-step radio buttons.
 */

import { Settings } from 'lucide-react';
import { Card, Radio } from '../../design-system/primitives';
import { useAgentStore } from '../../stores/agentStore';

interface Props {
  onChange: (mode: 'auto' | 'supervised' | 'step-by-step') => void;
}

const MODES: { value: 'auto' | 'supervised' | 'step-by-step'; label: string; desc: string }[] = [
  { value: 'auto', label: 'Auto', desc: 'Agent runs freely' },
  { value: 'supervised', label: 'Supervised', desc: 'Confirm before actions' },
  { value: 'step-by-step', label: 'Step-by-Step', desc: 'Approve each step' },
];

export function ModeSelector({ onChange }: Props) {
  const { mode } = useAgentStore();

  return (
    <div className="px-3 py-1.5">
      <fieldset className="space-y-ds-3" aria-label="Execution mode">
        <legend className="mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-ds-muted">
          <Settings size={12} aria-hidden="true" />
          Mode
        </legend>
        <Card className="space-y-ds-2 bg-ds-bg/40 px-ds-3 py-ds-3 shadow-none">
          {MODES.map((m) => (
            <Radio
              key={m.value}
              name="sidebar-execution-mode"
              value={m.value}
              checked={mode === m.value}
              onChange={() => onChange(m.value)}
              label={m.label}
              description={m.desc}
              className="rounded-ds-lg px-ds-2 py-ds-2 hover:bg-ds-bg/60"
            />
          ))}
        </Card>
      </fieldset>
    </div>
  );
}
