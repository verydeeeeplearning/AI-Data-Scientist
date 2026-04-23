import type { Meta, StoryObj } from '@storybook/react';
import { Card } from './Card';
import { Skeleton } from './Skeleton';

const meta = {
  title: 'Design System/Primitives/Skeleton',
  component: Skeleton,
  tags: ['autodocs'],
  args: {
    shape: 'line',
  },
} satisfies Meta<typeof Skeleton>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Line: Story = {};

export const Avatar: Story = {
  args: {
    shape: 'avatar',
  },
};

export const CardComposition: Story = {
  render: () => (
    <Card className="max-w-xl space-y-ds-3">
      <div className="flex items-center gap-ds-3">
        <Skeleton shape="avatar" />
        <div className="flex-1 space-y-ds-2">
          <Skeleton className="max-w-sm" />
          <Skeleton className="max-w-md" tone="muted" />
        </div>
      </div>
      <Skeleton shape="block" />
      <div className="flex gap-ds-2">
        <Skeleton shape="pill" />
        <Skeleton shape="pill" tone="muted" />
      </div>
    </Card>
  ),
};
