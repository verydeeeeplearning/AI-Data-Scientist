/**
 * Mode selector — auto / supervised / step-by-step radio buttons.
 */

import { Settings } from 'lucide-react';
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
      <div className="flex items-center gap-1.5 mb-1.5 text-xs font-medium text-ds-muted uppercase tracking-wider">
        <Settings size={12} />
        Mode
      </div>

      <div className="space-y-0.5">
        {MODES.map((m) => (
          <button
            key={m.value}
            onClick={() => onChange(m.value)}
            className={`
              w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs
              transition-colors text-left
              ${mode === m.value
                ? 'bg-ds-accent/10 text-ds-accent'
                : 'text-ds-text/70 hover:bg-ds-bg hover:text-ds-text'}
            `}
          >
            {/* Radio indicator */}
            <div className={`
              w-3 h-3 rounded-full border flex-shrink-0
              flex items-center justify-center
              ${mode === m.value ? 'border-ds-accent' : 'border-ds-muted/40'}
            `}>
              {mode === m.value && (
                <div className="w-1.5 h-1.5 rounded-full bg-ds-accent" />
              )}
            </div>

            <div>
              <div className="font-medium">{m.label}</div>
              <div className="text-[10px] text-ds-muted leading-tight">{m.desc}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
