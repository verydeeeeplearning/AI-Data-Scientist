/**
 * Editable standing-order panel for autonomous policy control.
 */

import { ListTree, Save } from 'lucide-react';
import { useEffect, useId, useMemo, useState } from 'react';
import { Badge, Button, Card, Textarea } from '../../design-system/primitives';
import { useWs } from '../../hooks/WsProvider';
import { fetchPolicySnapshot } from '../../hooks/usePolicy';
import { usePolicyStore } from '../../stores/policyStore';

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

function normalizeOrders(text: string): string[] {
  const seen = new Set<string>();
  const orders: string[] = [];
  for (const rawLine of text.split('\n')) {
    const line = rawLine.trim();
    if (!line || seen.has(line)) continue;
    seen.add(line);
    orders.push(line);
  }
  return orders;
}

export function StandingOrdersPanel() {
  const headingId = useId();
  const { rpc } = useWs();
  const snapshot = usePolicyStore((s) => s.snapshot);
  const setSnapshot = usePolicyStore((s) => s.setSnapshot);
  const markUpdated = usePolicyStore((s) => s.markUpdated);
  const standingOrders = snapshot?.standingOrders ?? [];
  const [draft, setDraft] = useState(standingOrders.join('\n'));
  const [dirty, setDirty] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!dirty) {
      setDraft(standingOrders.join('\n'));
    }
  }, [dirty, standingOrders]);

  const normalizedDraft = useMemo(() => normalizeOrders(draft), [draft]);
  const normalizedCurrent = useMemo(() => normalizeOrders(standingOrders.join('\n')), [standingOrders]);
  const hasChanges = dirty || normalizedDraft.join('\n') !== normalizedCurrent.join('\n');
  const helperText = 'One standing order per line. Duplicate and empty lines are removed on save.';

  const save = async () => {
    setSaveState('saving');
    setErrorMessage(null);
    try {
      await rpc('policy.setStandingOrders', { orders: normalizedDraft });
      setSnapshot(await fetchPolicySnapshot(rpc));
      markUpdated();
      setDirty(false);
      setSaveState('saved');
    } catch (err) {
      setSaveState('error');
      setErrorMessage((err as Error)?.message ?? 'Failed to save standing orders.');
    }
  };

  return (
    <section aria-labelledby={headingId}>
      <Card className="space-y-4 bg-ds-bg/60" aria-busy={saveState === 'saving'}>
        <header className="flex flex-wrap items-center gap-2">
          <div
            id={headingId}
            className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-ds-muted"
          >
            <ListTree size={12} aria-hidden="true" />
            Standing Orders
          </div>
          <Badge compact>{standingOrders.length}</Badge>
        </header>

        <Textarea
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
            setDirty(true);
            setSaveState('idle');
            setErrorMessage(null);
          }}
          rows={5}
          resize="none"
          label="Orders"
          description={helperText}
          errorMessage={errorMessage ?? undefined}
          placeholder="One standing order per line"
        />

        {saveState === 'saved' ? (
          <p role="status" className="text-xs text-ds-success">
            Standing orders saved.
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button
            onClick={() => void save()}
            disabled={!hasChanges}
            loading={saveState === 'saving'}
            variant="primary"
            size="sm"
            leadingIcon={<Save size={14} aria-hidden="true" />}
          >
            Save orders
          </Button>
          <Button
            onClick={() => {
              setDraft(standingOrders.join('\n'));
              setDirty(false);
              setSaveState('idle');
              setErrorMessage(null);
            }}
            disabled={!hasChanges || saveState === 'saving'}
            variant="secondary"
            size="sm"
          >
            Reset
          </Button>
        </div>
      </Card>
    </section>
  );
}
