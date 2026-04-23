import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { applyDensityScale } from '../../application/layout/applyDensityScale';
import type { DensityMode } from '../../domain/layout/density';
import { Tabs, type TabsProps } from './Tabs';

const noop = () => undefined;

const meta = {
  title: 'Design System/Primitives/Tabs',
  component: Tabs,
  tags: ['autodocs'],
  args: {
    value: 'overview',
    onValueChange: noop,
    items: [
      {
        value: 'overview',
        label: 'Overview',
        content: (
          <div className="space-y-ds-2">
            <div className="text-ds-sm font-medium text-ds-text">Pipeline summary</div>
            <p className="text-ds-sm leading-6 text-ds-muted">
              The agent has a clean execution path, no blocked approvals, and stable delivery policy settings.
            </p>
          </div>
        ),
      },
      {
        value: 'quality',
        label: 'Quality',
        content: (
          <div className="space-y-ds-2">
            <div className="text-ds-sm font-medium text-ds-text">Validation signals</div>
            <p className="text-ds-sm leading-6 text-ds-muted">
              Contract checks, lint gates, and workflow guards all point to a ready-to-ship state.
            </p>
          </div>
        ),
      },
      {
        value: 'delivery',
        label: 'Delivery',
        content: (
          <div className="space-y-ds-2">
            <div className="text-ds-sm font-medium text-ds-text">Operator outcome</div>
            <p className="text-ds-sm leading-6 text-ds-muted">
              Notifications are aligned with the current cadence, quiet hours, and escalation policy.
            </p>
          </div>
        ),
      },
    ],
  },
} satisfies Meta<typeof Tabs>;

export default meta;

type Story = StoryObj<typeof meta>;

function TabsStory(args: TabsProps) {
  const [value, setValue] = useState(args.value);

  return <Tabs {...args} value={value} onValueChange={setValue} />;
}

export const Default: Story = {
  args: {
    onValueChange: noop,
  },
  render: (args) => <TabsStory {...(args as TabsProps)} />,
};

export const WithDisabledTab: Story = {
  args: {
    value: 'overview',
    onValueChange: noop,
    items: [
      {
        value: 'overview',
        label: 'Overview',
        content: <p className="text-ds-sm leading-6 text-ds-muted">Active tab content.</p>,
      },
      {
        value: 'locked',
        label: 'Locked',
        disabled: true,
        content: <p className="text-ds-sm leading-6 text-ds-muted">This tab cannot be selected.</p>,
      },
    ],
  },
  render: (args) => <TabsStory {...(args as TabsProps)} />,
};

function DensityShowcase({ mode, args }: { mode: DensityMode; args: TabsProps }) {
  const [value, setValue] = useState(args.value);
  return (
    <div
      data-density={mode}
      style={applyDensityScale(mode) as React.CSSProperties}
      className="bg-ds-bg p-ds-4"
    >
      <Tabs {...args} value={value} onValueChange={setValue} />
    </div>
  );
}

export const CompactDensity: Story = {
  render: (args) => <DensityShowcase mode="compact" args={args as TabsProps} />,
};

export const ComfortableDensity: Story = {
  render: (args) => <DensityShowcase mode="comfortable" args={args as TabsProps} />,
};

export const SpaciousDensity: Story = {
  render: (args) => <DensityShowcase mode="spacious" args={args as TabsProps} />,
};
