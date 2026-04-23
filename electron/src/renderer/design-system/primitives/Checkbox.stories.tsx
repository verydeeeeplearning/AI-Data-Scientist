import type { Meta, StoryObj } from '@storybook/react';
import { Checkbox } from './Checkbox';

const meta = {
  title: 'Design System/Primitives/Checkbox',
  component: Checkbox,
  tags: ['autodocs'],
  args: {
    id: 'storybook-checkbox',
    label: 'Require operator acknowledgement',
    description: 'Block autonomous execution until a human confirms the risk summary.',
    hint: 'Use this for high-impact actions during quiet hours.',
  },
} satisfies Meta<typeof Checkbox>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Checked: Story = {
  args: {
    id: 'storybook-checkbox-checked',
    label: 'Auto-close after completion',
    description: 'Dismiss the dialog when the delivery policy finishes sending the outcome digest.',
    defaultChecked: true,
  },
};

export const ErrorState: Story = {
  args: {
    id: 'storybook-checkbox-error',
    label: 'Allow irreversible action',
    description: 'This approval bypasses the default rollback checkpoint.',
    errorMessage: 'Irreversible actions require a typed rationale before approval.',
  },
};

export const Disabled: Story = {
  args: {
    id: 'storybook-checkbox-disabled',
    label: 'Mute follow-up notifications',
    description: 'This control becomes available after the current alert is acknowledged.',
    disabled: true,
  },
};
