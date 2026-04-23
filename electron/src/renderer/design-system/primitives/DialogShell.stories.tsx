import type { Meta, StoryObj } from '@storybook/react';
import { applyDensityScale } from '../../application/layout/applyDensityScale';
import type { DensityMode } from '../../domain/layout/density';
import { Button } from './Button';
import { DialogShell } from './DialogShell';

const meta = {
  title: 'Design System/Primitives/DialogShell',
  component: DialogShell,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
  },
  args: {
    open: true,
    title: 'Approve high-impact rerun',
    description:
      'The agent wants to retrain the production churn model with a new cohort split. Review the risk summary before continuing.',
    children: (
      <div className="space-y-ds-3">
        <div className="rounded-ds-lg border border-ds-border bg-ds-bg/60 p-ds-3">
          <div className="text-ds-xs uppercase tracking-widest text-ds-muted">Impact</div>
          <div className="mt-ds-2 text-ds-sm text-ds-text">
            This rerun will replace the current forecast baseline and notify subscribed operators.
          </div>
        </div>
        <div className="rounded-ds-lg border border-ds-border bg-ds-bg/60 p-ds-3">
          <div className="text-ds-xs uppercase tracking-widest text-ds-muted">Evidence</div>
          <div className="mt-ds-2 text-ds-sm text-ds-text">
            Drift detectors flagged feature instability across two acquisition channels.
          </div>
        </div>
      </div>
    ),
    footer: (
      <>
        <Button variant="secondary">Cancel</Button>
        <Button variant="primary">Approve rerun</Button>
      </>
    ),
  },
} satisfies Meta<typeof DialogShell>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const DangerTone: Story = {
  args: {
    tone: 'danger',
    title: 'Delete archived workspace',
    description:
      'Deleting this workspace removes the local transcript cache and export history for every run linked to the project.',
    footer: (
      <>
        <Button variant="secondary">Keep workspace</Button>
        <Button variant="danger">Delete workspace</Button>
      </>
    ),
  },
};

function DensityShowcase({ mode }: { mode: DensityMode }) {
  return (
    <div
      data-density={mode}
      style={applyDensityScale(mode) as React.CSSProperties}
      className="min-h-screen bg-ds-bg p-ds-6"
    >
      <DialogShell
        open
        title={`Approve rerun (${mode})`}
        description="Review the risk summary before continuing."
        footer={
          <>
            <Button variant="secondary">Cancel</Button>
            <Button variant="primary">Approve</Button>
          </>
        }
      >
        <div className="text-ds-sm text-ds-text">
          Density {mode} preview of the dialog shell. Padding and font scales follow the active mode.
        </div>
      </DialogShell>
    </div>
  );
}

export const CompactDensity: Story = {
  render: () => <DensityShowcase mode="compact" />,
};

export const ComfortableDensity: Story = {
  render: () => <DensityShowcase mode="comfortable" />,
};

export const SpaciousDensity: Story = {
  render: () => <DensityShowcase mode="spacious" />,
};
