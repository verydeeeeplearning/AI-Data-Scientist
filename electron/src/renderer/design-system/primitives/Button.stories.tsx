import type { Meta, StoryObj } from '@storybook/react';
import { ArrowRight } from 'lucide-react';
import { applyDensityScale } from '../../application/layout/applyDensityScale';
import type { DensityMode } from '../../domain/layout/density';
import { Button, type ButtonProps } from './Button';

const meta = {
  title: 'Design System/Primitives/Button',
  component: Button,
  tags: ['autodocs'],
  args: {
    children: 'Run analysis',
  },
} satisfies Meta<typeof Button>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Primary: Story = {};

export const Secondary: Story = {
  args: {
    variant: 'secondary',
  },
};

export const Danger: Story = {
  args: {
    variant: 'danger',
    children: 'Delete draft',
  },
};

export const Loading: Story = {
  args: {
    loading: true,
  },
};

export const WithIcon: Story = {
  args: {
    trailingIcon: <ArrowRight size={14} />,
  },
};

function DensityShowcase({ mode, args }: { mode: DensityMode; args: ButtonProps }) {
  return (
    <div
      data-density={mode}
      style={applyDensityScale(mode) as React.CSSProperties}
      className="flex flex-wrap items-center gap-ds-3 bg-ds-bg p-ds-4"
    >
      <Button {...args} variant="primary">
        Run analysis
      </Button>
      <Button {...args} variant="secondary">
        Cancel
      </Button>
      <Button {...args} variant="ghost">
        More
      </Button>
      <Button {...args} variant="danger">
        Delete
      </Button>
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
