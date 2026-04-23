import type { Meta, StoryObj } from '@storybook/react';
import { AlertTriangle, Info } from 'lucide-react';
import { Button } from './Button';
import { Tooltip } from './Tooltip';

const meta = {
  title: 'Design System/Primitives/Tooltip',
  component: Tooltip,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
  args: {
    content: 'The latest runtime health check passed and operator delivery is active.',
    children: (
      <Button variant="secondary" leadingIcon={<Info size={14} />}>
        Runtime health
      </Button>
    ),
  },
} satisfies Meta<typeof Tooltip>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const AccentTone: Story = {
  args: {
    tone: 'accent',
    content: 'This action will use the current policy template as the starting point.',
    children: (
      <Button variant="primary" leadingIcon={<Info size={14} />}>
        Recommended policy
      </Button>
    ),
  },
};

export const PlacementGallery: Story = {
  render: () => (
    <div className="grid grid-cols-2 gap-ds-6">
      <Tooltip placement="top" content="Top placement keeps the label close to the trigger.">
        <Button variant="secondary">Top</Button>
      </Tooltip>
      <Tooltip placement="right" content="Right placement is useful in dense table rows.">
        <Button variant="secondary">Right</Button>
      </Tooltip>
      <Tooltip placement="bottom" tone="accent" content="Bottom placement works well beneath compact controls.">
        <Button variant="primary">Bottom</Button>
      </Tooltip>
      <Tooltip
        placement="left"
        tone="danger"
        content="This override bypasses the default network sandbox allowlist."
      >
        <Button variant="danger" leadingIcon={<AlertTriangle size={14} />}>
          Left
        </Button>
      </Tooltip>
    </div>
  ),
};
