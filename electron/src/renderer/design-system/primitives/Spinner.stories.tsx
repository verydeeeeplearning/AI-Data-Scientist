import type { Meta, StoryObj } from '@storybook/react';
import { Spinner } from './Spinner';

const meta = {
  title: 'Design System/Primitives/Spinner',
  component: Spinner,
  tags: ['autodocs'],
  args: {
    tone: 'accent',
    size: 'md',
  },
} satisfies Meta<typeof Spinner>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const WithLabel: Story = {
  args: {
    label: 'Running profile checks',
  },
};

export const Warning: Story = {
  args: {
    tone: 'warning',
    size: 'lg',
    label: 'Waiting on approval',
  },
};
