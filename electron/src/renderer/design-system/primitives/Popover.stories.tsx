import type { Meta, StoryObj } from '@storybook/react';
import { AlertTriangle, Bell, SlidersHorizontal } from 'lucide-react';
import { Badge } from './Badge';
import { Button } from './Button';
import { Popover } from './Popover';

const meta = {
  title: 'Design System/Primitives/Popover',
  component: Popover,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
  args: {
    trigger: (
      <Button variant="secondary" leadingIcon={<SlidersHorizontal size={14} />}>
        Delivery policy
      </Button>
    ),
    title: 'Operator delivery',
    description: 'Tune notifications for blocked runs without leaving the current workflow.',
    children: (
      <div className="space-y-ds-3">
        <div className="rounded-ds-lg border border-ds-border bg-ds-bg/60 p-ds-3 text-ds-xs text-ds-text">
          Escalate repeated blocked states after two digest cycles and keep quiet hours pinned to the active timezone.
        </div>
        <div className="flex items-center justify-between gap-ds-3 rounded-ds-lg border border-ds-border bg-ds-bg/40 p-ds-3">
          <div>
            <div className="text-ds-xs font-medium text-ds-text">Digest cadence</div>
            <div className="mt-1 text-[11px] text-ds-muted">Every 30 minutes</div>
          </div>
          <Badge tone="accent">Recommended</Badge>
        </div>
        <div className="flex gap-ds-2">
          <Button variant="secondary" size="sm">Dismiss</Button>
          <Button variant="primary" size="sm">Apply policy</Button>
        </div>
      </div>
    ),
  },
} satisfies Meta<typeof Popover>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const AccentTone: Story = {
  args: {
    tone: 'accent',
    trigger: (
      <Button variant="primary" leadingIcon={<Bell size={14} />}>
        Notification digest
      </Button>
    ),
    title: 'Digest window',
    description: 'Aggregate low-urgency events and send them as a single operator update.',
  },
};

export const DangerTone: Story = {
  args: {
    tone: 'danger',
    placement: 'right',
    align: 'start',
    trigger: (
      <Button variant="danger" leadingIcon={<AlertTriangle size={14} />}>
        Destructive action
      </Button>
    ),
    title: 'Delete cached artifacts',
    description: 'This clears local exports, generated notebooks, and runtime snapshots for the selected run.',
    children: (
      <div className="space-y-ds-3">
        <div className="rounded-ds-lg border border-ds-error/30 bg-ds-error/10 p-ds-3 text-ds-xs text-ds-text">
          The backend will not restore deleted artifacts during startup recovery.
        </div>
        <div className="flex gap-ds-2">
          <Button variant="secondary" size="sm">Keep artifacts</Button>
          <Button variant="danger" size="sm">Delete cache</Button>
        </div>
      </div>
    ),
  },
};
