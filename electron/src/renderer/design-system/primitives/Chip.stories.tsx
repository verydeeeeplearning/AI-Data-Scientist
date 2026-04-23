import type { Meta, StoryObj } from '@storybook/react';
import { CircleAlert, ShieldCheck, Sparkles, Tag } from 'lucide-react';
import { Chip } from './Chip';

const meta = {
  title: 'Design System/Primitives/Chip',
  component: Chip,
  tags: ['autodocs'],
  args: {
    children: 'Primary reviewer',
  },
} satisfies Meta<typeof Chip>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Neutral: Story = {};

export const SelectedAccent: Story = {
  args: {
    tone: 'accent',
    selected: true,
    leadingIcon: <Sparkles size={14} />,
    children: 'Recommended policy',
  },
};

export const ApprovalFilters: Story = {
  render: () => (
    <div className="flex flex-wrap gap-ds-2">
      <Chip leadingIcon={<Tag size={14} />}>All requests</Chip>
      <Chip tone="accent" selected leadingIcon={<ShieldCheck size={14} />}>
        Needs review
      </Chip>
      <Chip tone="warning" selected leadingIcon={<CircleAlert size={14} />}>
        Escalated
      </Chip>
    </div>
  ),
};

export const CompactDanger: Story = {
  args: {
    tone: 'danger',
    size: 'sm',
    selected: true,
    children: 'Override enabled',
  },
};

export const Disabled: Story = {
  args: {
    tone: 'neutral',
    children: 'Digest locked',
    disabled: true,
  },
};
