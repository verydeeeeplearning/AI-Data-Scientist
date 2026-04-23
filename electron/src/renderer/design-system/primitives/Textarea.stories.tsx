import type { Meta, StoryObj } from '@storybook/react';
import { Textarea } from './Textarea';

const meta = {
  title: 'Design System/Primitives/Textarea',
  component: Textarea,
  tags: ['autodocs'],
  args: {
    id: 'storybook-textarea',
    label: 'Mission brief',
    description: 'Capture the business context, target metric, and delivery deadline.',
    placeholder: 'Summarize the churn drivers for the Q2 renewal committee...',
  },
} satisfies Meta<typeof Textarea>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const WithHint: Story = {
  args: {
    hint: 'Keep this under 500 characters so the operator digest stays readable.',
    defaultValue:
      'Review the latest churn model and prepare a one-page summary for the subscription leadership team.',
  },
};

export const ErrorState: Story = {
  args: {
    value: 'Need help soon.',
    errorMessage: 'Include the target dataset, success metric, and delivery date.',
    resize: 'none',
  },
};
