import type { Meta, StoryObj } from '@storybook/react';
import { applyDensityScale } from '../../application/layout/applyDensityScale';
import type { DensityMode } from '../../domain/layout/density';
import { Card, type CardProps } from './Card';

const meta = {
  title: 'Design System/Primitives/Card',
  component: Card,
  tags: ['autodocs'],
  args: {
    children: (
      <div className="space-y-ds-2">
        <div className="text-ds-xs uppercase tracking-widest text-ds-muted">Mission</div>
        <div className="text-ds-lg font-semibold text-ds-text">Churn prediction refresh</div>
        <div className="text-ds-sm text-ds-muted">
          Rebuild the monthly churn forecast with the current subscription cohort.
        </div>
      </div>
    ),
  },
} satisfies Meta<typeof Card>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Elevated: Story = {
  args: {
    tone: 'elevated',
  },
};

export const Accent: Story = {
  args: {
    tone: 'accent',
  },
};

export const Danger: Story = {
  args: {
    tone: 'danger',
  },
};

function DensityShowcase({ mode, args }: { mode: DensityMode; args: CardProps }) {
  return (
    <div
      data-density={mode}
      style={applyDensityScale(mode) as React.CSSProperties}
      className="grid gap-ds-3 bg-ds-bg p-ds-4"
    >
      <Card {...args} tone="default" />
      <Card {...args} tone="elevated" />
      <Card {...args} tone="accent" />
    </div>
  );
}

export const CompactDensity: Story = {
  render: (args) => <DensityShowcase mode="compact" args={args} />,
};

export const ComfortableDensity: Story = {
  render: (args) => <DensityShowcase mode="comfortable" args={args} />,
};

export const SpaciousDensity: Story = {
  render: (args) => <DensityShowcase mode="spacious" args={args} />,
};
