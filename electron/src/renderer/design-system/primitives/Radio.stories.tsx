import type { Meta, StoryObj } from '@storybook/react';
import { Radio } from './Radio';

const meta = {
  title: 'Design System/Primitives/Radio',
  component: Radio,
  tags: ['autodocs'],
  args: {
    id: 'storybook-radio',
    name: 'storybook-approval-decision',
    label: 'Escalate immediately',
    description: 'Notify the operator as soon as the blocked state crosses the configured threshold.',
    hint: 'Use a shared name across radios to build a full decision group.',
  },
} satisfies Meta<typeof Radio>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Selected: Story = {
  args: {
    id: 'storybook-radio-selected',
    label: 'Queue for digest',
    description: 'Hold the notification until the next operator digest window.',
    defaultChecked: true,
  },
};

export const ApprovalGroup: Story = {
  render: () => (
    <div className="space-y-ds-3">
      <Radio
        id="storybook-radio-group-now"
        name="storybook-approval-group"
        label="Approve now"
        description="Release the action token and continue without waiting for the next digest."
        defaultChecked
      />
      <Radio
        id="storybook-radio-group-hold"
        name="storybook-approval-group"
        label="Hold for review"
        description="Pause execution and keep the task parked in the approval inbox."
      />
      <Radio
        id="storybook-radio-group-reject"
        name="storybook-approval-group"
        label="Reject request"
        description="Return the run to the operator with a blocked outcome."
      />
    </div>
  ),
};

export const ErrorState: Story = {
  args: {
    id: 'storybook-radio-error',
    label: 'Bypass secondary review',
    description: 'Only use this for emergency maintenance windows.',
    errorMessage: 'A bypass decision must be paired with an incident reference.',
  },
};
