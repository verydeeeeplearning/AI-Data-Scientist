import type { Meta, StoryObj } from '@storybook/react';
import { AlertTriangle, ArrowUpRight, ShieldAlert } from 'lucide-react';
import {
  ResultCardActionButton,
  ResultCardDetailBlock,
  ResultCardFooter,
  ResultCardIconFrame,
  ResultCardMetaRow,
  ResultCardMetricPanel,
  ResultCardPill,
  ResultCardShell,
  ResultCardSectionPanel,
  ResultCardSectionTitle,
} from './ResultCardShell';

type ResultCardDemoProps = {
  readonly title: string;
  readonly summary: string;
  readonly metricLabel: string;
  readonly metricValue: string;
  readonly metricHint: string;
  readonly audienceLabel: string;
  readonly runLabel: string;
  readonly toneClassName: string;
  readonly requestReviewTone?: 'default' | 'accent' | 'danger';
  readonly linkedArtifacts?: string[];
};

function ResultCardDemo({
  title,
  summary,
  metricLabel,
  metricValue,
  metricHint,
  audienceLabel,
  runLabel,
  toneClassName,
  requestReviewTone = 'accent',
  linkedArtifacts = ['Feature importance plot', 'Validation summary'],
}: ResultCardDemoProps) {
  return (
    <ResultCardShell className="w-full max-w-2xl">
      <header className="flex items-start justify-between gap-ds-3">
        <div className="min-w-0">
          <ResultCardMetaRow className="text-ds-xs uppercase tracking-widest">
            <ResultCardPill className={toneClassName}>
              Experiment
            </ResultCardPill>
            <ResultCardPill>Apr 20, 2026, 6:30 PM</ResultCardPill>
            <ResultCardPill className="border-ds-accent/30 bg-ds-accent/10 text-ds-accent">
              {audienceLabel}
            </ResultCardPill>
          </ResultCardMetaRow>
          <h3 className="mt-ds-2 text-ds-sm font-semibold text-ds-text">
            {title}
          </h3>
          <p className="mt-ds-1 text-ds-xs text-ds-muted">
            {summary}
          </p>
        </div>
        <ResultCardIconFrame className={toneClassName}>
          <ShieldAlert size={16} aria-hidden="true" />
        </ResultCardIconFrame>
      </header>

      <div className="mt-ds-4 space-y-ds-3">
        <ResultCardMetricPanel label={metricLabel} value={metricValue} hint={metricHint} />
        <div className="grid gap-ds-3 md:grid-cols-2">
          <ResultCardDetailBlock label="Model" value="GradientBoostingClassifier v7" />
          <ResultCardDetailBlock label="Data version" value="customer-churn-2026-04-19" />
        </div>
        <ResultCardSectionPanel>
          <ResultCardSectionTitle>Linked artifacts</ResultCardSectionTitle>
          <div className="mt-ds-2 flex flex-wrap gap-ds-2">
            {linkedArtifacts.map((artifact) => (
              <ResultCardPill key={artifact}>{artifact}</ResultCardPill>
            ))}
          </div>
        </ResultCardSectionPanel>
      </div>

      <ResultCardFooter>
        <ResultCardMetaRow>
          <span className="font-medium text-ds-text">Run</span>
          <ResultCardPill>{runLabel}</ResultCardPill>
          <span className="font-medium text-ds-text">Tool</span>
          <ResultCardPill>model.compare</ResultCardPill>
        </ResultCardMetaRow>
        <div className="flex flex-wrap gap-ds-2">
          <ResultCardActionButton leadingIcon={<ArrowUpRight size={13} aria-hidden="true" />}>
            Compare
          </ResultCardActionButton>
          <ResultCardActionButton
            tone={requestReviewTone}
            leadingIcon={<ShieldAlert size={13} aria-hidden="true" />}
          >
            Request review
          </ResultCardActionButton>
        </div>
      </ResultCardFooter>
    </ResultCardShell>
  );
}

const meta = {
  title: 'Design System/Composites/ResultCard',
  component: ResultCardShell,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component:
          'Shared result-card chrome for evidence, review, and escalation surfaces. The stories cover optimistic, review-required, dense-audit, and incident-style states so live cards can reuse a consistent structure.',
      },
    },
  },
  render: () => (
    <ResultCardDemo
      title="Gradient boosting beat the baseline on recall"
      summary="Recall improved while training cost stayed within the current mission budget."
      metricLabel="Recall"
      metricValue="0.8421"
      metricHint="+0.0412 vs baseline"
      audienceLabel="Rendered for Exec"
      runLabel="run-2026-04-20-001"
      toneClassName="border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
    />
  ),
} satisfies Meta<typeof ResultCardShell>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => (
    <ResultCardDemo
      title="Gradient boosting beat the baseline on recall"
      summary="Recall improved while training cost stayed within the current mission budget."
      metricLabel="Recall"
      metricValue="0.8421"
      metricHint="+0.0412 vs baseline"
      audienceLabel="Rendered for Exec"
      runLabel="run-2026-04-20-001"
      toneClassName="border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
    />
  ),
};

export const ReviewRequired: Story = {
  render: () => (
    <ResultCardDemo
      title="Population shift crossed the review threshold"
      summary="Drift exceeded the approved PSI guardrail, so rollout should pause until the verifier signs off on mitigation."
      metricLabel="Max PSI"
      metricValue="0.312"
      metricHint="+0.118 above policy threshold"
      audienceLabel="Rendered for Governance"
      runLabel="run-2026-04-20-014"
      toneClassName="border-ds-warning/30 bg-ds-warning/10 text-ds-warning"
      requestReviewTone="danger"
      linkedArtifacts={['Drift report', 'Policy diff', 'Rollback checklist']}
    />
  ),
};

export const DenseAuditTrail: Story = {
  render: () => (
    <ResultCardDemo
      title="Backtest evidence stayed stable across all folds"
      summary="The run maintained consistent statistical quality across the monitored windows and cleared the current reproducibility gate."
      metricLabel="Consistency"
      metricValue="0.93"
      metricHint="8 / 8 folds passed"
      audienceLabel="Rendered for DS"
      runLabel="run-2026-04-20-022"
      toneClassName="border-ds-accent/30 bg-ds-accent/10 text-ds-accent"
      linkedArtifacts={[
        'Fold summary',
        'Confidence intervals',
        'Calibration plot',
        'Residual distribution',
      ]}
    />
  ),
};

export const EscalationCandidate: Story = {
  render: () => (
    <ResultCardShell className="w-full max-w-2xl">
      <header className="flex items-start justify-between gap-ds-3">
        <div className="min-w-0">
          <ResultCardMetaRow className="text-ds-xs uppercase tracking-widest">
            <ResultCardPill className="border-ds-error/30 bg-ds-error/10 text-ds-error">
              Incident
            </ResultCardPill>
            <ResultCardPill>Apr 20, 2026, 7:10 PM</ResultCardPill>
            <ResultCardPill>Rendered for Operator</ResultCardPill>
          </ResultCardMetaRow>
          <h3 className="mt-ds-2 text-ds-sm font-semibold text-ds-text">
            Regression pack flagged a rollback recommendation
          </h3>
          <p className="mt-ds-1 text-ds-xs text-ds-muted">
            New findings appeared in the verifier and the candidate run fell below the accepted
            policy envelope for deployment.
          </p>
        </div>
        <ResultCardIconFrame className="border-ds-error/30 bg-ds-error/10 text-ds-error">
          <AlertTriangle size={16} aria-hidden="true" />
        </ResultCardIconFrame>
      </header>

      <div className="mt-ds-4 grid gap-ds-3 md:grid-cols-2">
        <ResultCardMetricPanel label="Verifier delta" value="3 new findings" hint="rollback recommended" />
        <ResultCardSectionPanel>
          <ResultCardSectionTitle>Blocked promotions</ResultCardSectionTitle>
          <div className="mt-ds-2 flex flex-wrap gap-ds-2">
            <ResultCardPill>policy.matrix</ResultCardPill>
            <ResultCardPill>monitoring.gate</ResultCardPill>
            <ResultCardPill>certification.review</ResultCardPill>
          </div>
        </ResultCardSectionPanel>
      </div>

      <ResultCardFooter>
        <ResultCardMetaRow>
          <span className="font-medium text-ds-text">Run</span>
          <ResultCardPill>run-2026-04-20-031</ResultCardPill>
          <span className="font-medium text-ds-text">Surface</span>
          <ResultCardPill>Regression Board</ResultCardPill>
        </ResultCardMetaRow>
        <div className="flex flex-wrap gap-ds-2">
          <ResultCardActionButton
            tone="danger"
            leadingIcon={<AlertTriangle size={13} aria-hidden="true" />}
          >
            Escalate now
          </ResultCardActionButton>
          <ResultCardActionButton leadingIcon={<ArrowUpRight size={13} aria-hidden="true" />}>
            Open evidence pack
          </ResultCardActionButton>
        </div>
      </ResultCardFooter>
    </ResultCardShell>
  ),
};
