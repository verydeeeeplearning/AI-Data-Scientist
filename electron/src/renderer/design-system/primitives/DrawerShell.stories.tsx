import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { Button } from './Button';
import { DrawerShell } from './DrawerShell';

const meta = {
  title: 'Design System/Primitives/DrawerShell',
  component: DrawerShell,
  parameters: {
    layout: 'fullscreen',
  },
  args: {
    open: true,
    title: 'Inspector drawer',
    description: 'A token-driven drawer for focused workflows and side-panel tasks.',
  },
} satisfies Meta<typeof DrawerShell>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: (args) => {
    const [open, setOpen] = useState(true);
    return (
      <div className="min-h-screen bg-ds-bg p-ds-6">
        <Button variant="primary" onClick={() => setOpen(true)}>
          Open drawer
        </Button>
        <DrawerShell
          {...args}
          open={open}
          onDismiss={() => setOpen(false)}
          footer={
            <>
              <Button variant="secondary" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={() => setOpen(false)}>
                Confirm
              </Button>
            </>
          }
        >
          <div className="space-y-ds-4">
            <div className="rounded-ds-lg border border-ds-border/70 bg-ds-bg/70 p-ds-4 text-ds-sm text-ds-text">
              Drawer body content lives here.
            </div>
            <div className="rounded-ds-lg border border-ds-border/70 bg-ds-bg/70 p-ds-4 text-ds-sm text-ds-muted">
              Use this for mission details, inspectors, approval flows, or guided edits.
            </div>
          </div>
        </DrawerShell>
      </div>
    );
  },
};

export const LargeLeft: Story = {
  args: {
    placement: 'left',
    size: 'lg',
    title: 'Large editor drawer',
    description: 'Supports wider side tasks without introducing a separate screen.',
  },
};
