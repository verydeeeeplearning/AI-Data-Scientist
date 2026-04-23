import type { Meta, StoryObj } from '@storybook/react';
import { CircleAlert, Search } from 'lucide-react';
import { applyDensityScale } from '../../application/layout/applyDensityScale';
import type { DensityMode } from '../../domain/layout/density';
import { Input, type InputProps } from './Input';

const meta = {
  title: 'Design System/Primitives/Input',
  component: Input,
  tags: ['autodocs'],
  args: {
    id: 'storybook-input',
    label: 'Workspace name',
    description: 'Use a concise label that operators can recognize in Telegram and desktop views.',
    placeholder: 'North America retention refresh',
  },
} satisfies Meta<typeof Input>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const WithLeadingIcon: Story = {
  args: {
    label: 'Search runs',
    description: 'Filter the latest completed analyses by keyword.',
    placeholder: 'Find a regression audit',
    leadingIcon: <Search size={14} />,
  },
};

export const ErrorState: Story = {
  args: {
    label: 'Webhook URL',
    description: 'Provide an HTTPS endpoint for operator callbacks.',
    value: 'http://localhost:8000/events',
    trailingIcon: <CircleAlert size={14} />,
    errorMessage: 'Webhook URLs must start with https://.',
    readOnly: true,
  },
};

export const Disabled: Story = {
  args: {
    label: 'Run identifier',
    value: 'run_2026_04_20_114500',
    hint: 'Generated automatically after the backend handshake succeeds.',
    disabled: true,
  },
};

function DensityShowcase({ mode, args }: { mode: DensityMode; args: InputProps }) {
  return (
    <div
      data-density={mode}
      style={applyDensityScale(mode) as React.CSSProperties}
      className="flex flex-col gap-ds-3 bg-ds-bg p-ds-4"
    >
      <Input
        {...args}
        id={`density-${mode}-input-1`}
        label="Workspace name"
        placeholder="North America retention refresh"
      />
      <Input
        {...args}
        id={`density-${mode}-input-2`}
        label="Search runs"
        placeholder="Find a regression audit"
        leadingIcon={<Search size={14} />}
      />
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
