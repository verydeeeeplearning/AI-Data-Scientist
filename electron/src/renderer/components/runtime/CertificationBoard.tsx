/**
 * Mission certification board for Electron runtime operators.
 */

import { BadgeCheck, RefreshCcw, ShieldCheck, ShieldX } from 'lucide-react';
import { useId, useMemo, useState } from 'react';
import {
  ResultCardSectionPanel,
  ResultCardSectionTitle,
} from '../../design-system/composites';
import { Badge, Button, Card, Input, Select } from '../../design-system/primitives';
import { useCertificationBoard } from '../../hooks/useCertificationBoard';

function parseApprovers(input: string): string[] {
  const seen = new Set<string>();
  const values: string[] = [];
  for (const token of input.split(/[\s,]+/)) {
    const value = token.trim();
    if (!value) continue;
    const key = value.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    values.push(value);
  }
  return values;
}

function formatDate(value: string | null): string {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString();
}

function formatScore(value: number | null): string {
  if (value === null) return 'n/a';
  return value.toFixed(2);
}

function boardNoticeToneClass(tone: 'neutral' | 'danger' = 'neutral'): string {
  return tone === 'danger'
    ? 'border-ds-error/30 bg-ds-error/10 text-ds-error'
    : 'bg-ds-surface/60 text-ds-muted';
}

export function CertificationBoard() {
  const {
    missions,
    selectedMission,
    selectedMissionName,
    setSelectedMissionName,
    loading,
    error,
    lastSubmission,
    refresh,
    submit,
  } = useCertificationBoard();
  const [approverDraft, setApproverDraft] = useState('');
  const [evidenceRef, setEvidenceRef] = useState('');
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const titleId = useId();

  const approvers = useMemo(() => parseApprovers(approverDraft), [approverDraft]);
  const nextTarget = selectedMission?.next_target ?? null;
  const missionOptions =
    missions.length === 0
      ? [{ value: '', label: 'No missions' }]
      : missions.map((mission) => ({
          value: mission.mission_name,
          label: mission.mission_name,
        }));

  const handleSubmit = async () => {
    if (!selectedMission || !nextTarget) {
      return;
    }

    setBusy(true);
    setSubmitError(null);
    try {
      await submit({
        missionName: selectedMission.mission_name,
        targetLevel: nextTarget,
        approvedBy: approvers,
        evidenceRef: evidenceRef.trim() || undefined,
      });
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Certification submit failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      data-testid="certification-board"
      className="space-y-ds-3 bg-ds-bg/70 p-ds-3"
      aria-labelledby={titleId}
    >
      <header className="flex flex-wrap items-start gap-ds-2">
        <div className="space-y-ds-1">
          <div
            id={titleId}
            className="flex items-center gap-ds-2 text-ds-xs font-semibold uppercase tracking-[0.16em] text-ds-muted"
          >
            <BadgeCheck size={14} aria-hidden="true" />
            <span>Certification</span>
          </div>
          <p className="text-ds-xs text-ds-muted">
            Review mission readiness and submit the next certification level.
          </p>
        </div>
        <Badge compact className="ml-auto">
          {missions.length} mission{missions.length === 1 ? '' : 's'}
        </Badge>
      </header>

      <section className="grid gap-ds-3">
        <Select
          id="certification-mission-select"
          label="Mission"
          value={selectedMissionName ?? ''}
          onChange={(event) => setSelectedMissionName(event.target.value || null)}
          data-testid="certification-mission-select"
          options={missionOptions}
          disabled={loading || missions.length === 0}
        />
        <div className="flex justify-end">
          <Button
            onClick={() => void refresh()}
            variant="secondary"
            size="sm"
            disabled={loading}
            leadingIcon={
              <RefreshCcw
                size={14}
                className={loading ? 'animate-spin' : undefined}
                aria-hidden="true"
              />
            }
            title="Refresh certification board"
          >
            Sync
          </Button>
        </div>
      </section>

      {loading && missions.length === 0 ? (
        <ResultCardSectionPanel
          role="status"
          aria-live="polite"
          className={boardNoticeToneClass()}
        >
          Loading mission certification state...
        </ResultCardSectionPanel>
      ) : error ? (
        <ResultCardSectionPanel role="alert" className={boardNoticeToneClass('danger')}>
          {error}
        </ResultCardSectionPanel>
      ) : !selectedMission ? (
        <ResultCardSectionPanel
          role="status"
          aria-live="polite"
          className={boardNoticeToneClass()}
        >
          No mission packs with certification metadata were found.
        </ResultCardSectionPanel>
      ) : (
        <>
          <ResultCardSectionPanel className="space-y-ds-2 bg-ds-surface/60">
            <div className="flex items-center justify-between gap-ds-2">
              <ResultCardSectionTitle>Mission State</ResultCardSectionTitle>
              <Badge compact>v{selectedMission.mission_version}</Badge>
            </div>
            <DetailRow label="Current" value={selectedMission.current_level ?? 'none'} />
            <DetailRow label="Effective" value={selectedMission.effective_level ?? 'none'} />
            <DetailRow label="Next" value={selectedMission.next_target ?? 'none'} />
          </ResultCardSectionPanel>

          <section
            className="grid grid-cols-2 gap-ds-2"
            aria-label="Certification readiness metrics"
          >
            <MetricCard
              label="Shadow Runs"
              value={String(selectedMission.stats.shadow_runs_passed)}
            />
            <MetricCard
              label="Verifier"
              value={formatScore(selectedMission.stats.verifier_avg_score)}
            />
            <MetricCard
              label="Critical"
              value={String(selectedMission.stats.critical_violations)}
              tone={selectedMission.stats.critical_violations > 0 ? 'warn' : 'normal'}
            />
            <MetricCard
              label="Rollback"
              value={selectedMission.stats.rollback_rehearsal_passed ? 'pass' : 'pending'}
              tone={selectedMission.stats.rollback_rehearsal_passed ? 'success' : 'warn'}
            />
          </section>

          <ResultCardSectionPanel className="space-y-ds-2 bg-ds-surface/60">
            <div className="flex flex-wrap items-center gap-ds-2">
              <ResultCardSectionTitle>Readiness</ResultCardSectionTitle>
              <Badge
                tone={selectedMission.certified_for_next_target ? 'success' : 'warning'}
                compact
                leadingIcon={
                  selectedMission.certified_for_next_target ? (
                    <ShieldCheck size={12} aria-hidden="true" />
                  ) : (
                    <ShieldX size={12} aria-hidden="true" />
                  )
                }
                className="ml-auto"
              >
                {selectedMission.certified_for_next_target ? 'Ready' : 'Pending'}
              </Badge>
            </div>
            <p className="text-ds-sm text-ds-text">
              {selectedMission.certified_for_next_target
                ? `${selectedMission.next_target ?? 'Target'} evidence is ready.`
                : `Needs ${selectedMission.required_approvers} owner approvals for ${
                    selectedMission.next_target ?? 'the next level'
                  }.`}
            </p>
            {selectedMission.latest_certification ? (
              <p className="text-ds-xs text-ds-muted">
                Latest approval: {selectedMission.latest_certification.level} on{' '}
                {formatDate(selectedMission.latest_certification.approved_at)}
              </p>
            ) : null}
            {selectedMission.gaps.length > 0 ? (
              <ul className="space-y-1" aria-label="Evidence gaps">
                {selectedMission.gaps.slice(0, 3).map((gap) => (
                  <li key={gap} className="text-ds-xs text-ds-warning">
                    {gap}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-ds-xs text-ds-success">No evidence gaps reported.</p>
            )}
          </ResultCardSectionPanel>

          <ResultCardSectionPanel className="space-y-ds-3 bg-ds-surface/60">
            <div className="flex flex-wrap items-center gap-ds-2">
              <ResultCardSectionTitle>Submit Certification</ResultCardSectionTitle>
              <Badge compact tone={nextTarget ? 'accent' : 'neutral'} className="ml-auto">
                {nextTarget ?? 'No next target'}
              </Badge>
            </div>

            <Input
              id="certification-approvers"
              label="Approvers"
              description="Separate owner IDs with spaces or commas."
              value={approverDraft}
              onChange={(event) => setApproverDraft(event.target.value)}
              placeholder="owner-park owner-cho"
            />

            <Input
              id="certification-evidence-ref"
              label="Evidence Reference"
              value={evidenceRef}
              onChange={(event) => setEvidenceRef(event.target.value)}
              placeholder="evidence ref (optional)"
            />

            <div className="flex items-center justify-between gap-ds-2 text-ds-xs text-ds-muted">
              <span>Parsed approvers</span>
              <Badge
                compact
                tone={
                  approvers.length >= selectedMission.required_approvers ? 'success' : 'warning'
                }
              >
                {approvers.length}/{selectedMission.required_approvers}
              </Badge>
            </div>

            <Button
              onClick={() => void handleSubmit()}
              disabled={busy || !nextTarget}
              variant="primary"
              size="sm"
              loading={busy}
              className="w-full"
            >
              {busy ? 'Submitting...' : nextTarget ? `Submit ${nextTarget}` : 'No next target'}
            </Button>

            {submitError ? (
              <p role="alert" className="text-ds-xs text-ds-error">
                {submitError}
              </p>
            ) : null}

            {lastSubmission && lastSubmission.mission_name === selectedMission.mission_name ? (
              <p aria-live="polite" className="text-ds-xs text-ds-muted">
                Last submit: {lastSubmission.status} to {lastSubmission.target_level}
              </p>
            ) : null}
          </ResultCardSectionPanel>
        </>
      )}
    </Card>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-ds-3 text-ds-xs">
      <span className="text-ds-muted">{label}</span>
      <span className="font-mono text-ds-text">{value}</span>
    </div>
  );
}

function MetricCard({
  label,
  value,
  tone = 'normal',
}: {
  label: string;
  value: string;
  tone?: 'normal' | 'success' | 'warn';
}) {
  const toneClass =
    tone === 'success' ? 'text-ds-success' : tone === 'warn' ? 'text-ds-warning' : 'text-ds-text';

  return (
    <ResultCardSectionPanel className="space-y-ds-1 bg-ds-surface/60 px-ds-3 py-ds-2">
      <ResultCardSectionTitle>{label}</ResultCardSectionTitle>
      <div className={`font-mono text-ds-lg ${toneClass}`}>{value}</div>
    </ResultCardSectionPanel>
  );
}
