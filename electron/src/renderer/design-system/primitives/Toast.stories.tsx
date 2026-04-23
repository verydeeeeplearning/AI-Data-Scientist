import type { Meta, StoryObj } from '@storybook/react';
import { AlertTriangle, Bell, CheckCircle2, ShieldAlert } from 'lucide-react';
import { Button } from './Button';
import { Toast, ToastViewport } from './Toast';

const meta = {
  title: 'Design System/Primitives/Toast',
  component: Toast,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
  },
  args: {
    title: 'Runtime notification',
    description: 'The autonomous runtime completed a background review and queued the next operator action.',
    tone: 'info',
    leadingIcon: <Bell size={14} />,
  },
} satisfies Meta<typeof Toast>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Info: Story = {
  render: (args) => (
    <div className="min-h-[240px] p-ds-6">
      <Toast {...args} />
    </div>
  ),
};

export const WarningWithAction: Story = {
  args: {
    title: 'Sandbox violation',
    description: 'The agent attempted an unapproved filesystem write outside the workspace boundary.',
    tone: 'warning',
    meta: 'write_file',
    leadingIcon: <ShieldAlert size={14} />,
  },
  render: (args) => (
    <div className="min-h-[240px] p-ds-6">
      <Toast {...args}>
        <div className="flex gap-ds-2">
          <Button variant="secondary" size="sm">Review trace</Button>
          <Button variant="primary" size="sm">Adjust policy</Button>
        </div>
      </Toast>
    </div>
  ),
};

export const ViewportStack: Story = {
  render: () => (
    <div className="min-h-[320px] p-ds-6">
      <ToastViewport placement="bottom-right">
        <Toast
          title="Experiment promoted"
          description="The latest baseline beat the previous champion on holdout precision."
          tone="success"
          meta="model_eval"
          leadingIcon={<CheckCircle2 size={14} />}
        />
        <Toast
          title="Delivery fallback enabled"
          description="Telegram quiet hours are active, so low-urgency alerts are being buffered."
          tone="info"
          meta="operator_runtime"
          leadingIcon={<Bell size={14} />}
        />
        <Toast
          title="Repeated blocked state"
          description="The same network host has been denied three times in the last hour."
          tone="danger"
          meta="network_sandbox"
          leadingIcon={<AlertTriangle size={14} />}
        />
      </ToastViewport>
    </div>
  ),
};
