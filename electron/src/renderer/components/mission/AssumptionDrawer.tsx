import { useState } from 'react';
import {
  DrawerSurfaceSection,
  DrawerSurfaceSectionTitle,
} from '../../design-system/composites/DrawerSurface';
import {
  Badge,
  Button,
  DrawerShell,
  Textarea,
} from '../../design-system/primitives';
import type { AssumptionEntry } from '../../types/taskContract';

interface Props {
  open: boolean;
  entries: AssumptionEntry[];
  verifying: boolean;
  onVerify: (entryId: string, verificationNote?: string) => Promise<void>;
  onClose: () => void;
}

export function AssumptionDrawer({ open, entries, verifying, onVerify, onClose }: Props) {
  const [verificationNotes, setVerificationNotes] = useState<Record<string, string>>({});

  const toneForRisk = (riskLevel: AssumptionEntry['risk_level']) => {
    if (riskLevel === 'high') {
      return 'warning';
    }
    if (riskLevel === 'medium') {
      return 'accent';
    }
    return 'neutral';
  };

  const description = 'Unverified assumptions captured in the current contract.';

  return (
    <DrawerShell
      open={open}
      size="lg"
      title="Open Assumptions"
      description={description}
      dismissLabel="Close assumptions drawer"
      onDismiss={onClose}
      data-testid="assumption-drawer"
    >
      <div className="space-y-ds-3">
        {entries.length === 0 && (
          <DrawerSurfaceSection data-testid="assumption-empty-state">
            <p className="text-ds-sm text-ds-muted">No open assumptions.</p>
          </DrawerSurfaceSection>
        )}

        {entries.map((entry) => (
          <DrawerSurfaceSection
            key={entry.entry_id}
            data-testid={`assumption-entry-${entry.entry_id}`}
            className={entry.risk_level === 'high' ? 'border-ds-warning/40 bg-ds-warning/10' : ''}
          >
            <div className="flex flex-wrap items-center justify-between gap-ds-2">
              <Badge tone={toneForRisk(entry.risk_level)} compact>
                {entry.risk_level}
              </Badge>
              <span className="text-ds-xs text-ds-muted">{entry.entry_id}</span>
            </div>

            <p className="mt-ds-3 text-ds-sm font-medium text-ds-text">{entry.statement}</p>
            <p className="mt-ds-2 text-ds-sm leading-6 text-ds-muted">{entry.rationale}</p>

            <div className="mt-ds-4 space-y-ds-3">
              <DrawerSurfaceSectionTitle>Verification Note</DrawerSurfaceSectionTitle>
              <Textarea
                value={verificationNotes[entry.entry_id] ?? ''}
                onChange={(event) =>
                  setVerificationNotes((current) => ({
                    ...current,
                    [entry.entry_id]: event.target.value,
                  }))
                }
                rows={3}
                placeholder="Verification note (optional)"
                resize="none"
                data-testid={`assumption-note-${entry.entry_id}`}
              />
              <Button
                type="button"
                variant="primary"
                size="sm"
                disabled={verifying}
                onClick={() =>
                  void onVerify(entry.entry_id, verificationNotes[entry.entry_id] ?? '')
                }
                data-testid={`assumption-verify-${entry.entry_id}`}
              >
                Mark Verified
              </Button>
            </div>
          </DrawerSurfaceSection>
        ))}
      </div>
    </DrawerShell>
  );
}
