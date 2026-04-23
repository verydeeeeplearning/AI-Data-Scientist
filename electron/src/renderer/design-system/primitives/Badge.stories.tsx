import type { Meta, StoryObj } from '@storybook/react';
import { CheckCircle2, CircleAlert, ShieldAlert, Sparkles } from 'lucide-react';
import { Badge } from './Badge';

const meta = {
  title: 'Design System/Primitives/Badge',
  component: Badge,
  tags: ['autodocs'],
  args: {
    children: 'Trust ready',
  },
} satisfies Meta<typeof Badge>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Neutral: Story = {};

export const Accent: Story = {
  args: {
    tone: 'accent',
    leadingIcon: <Sparkles size={12} />,
    children: 'Recommended',
  },
};

export const Success: Story = {
  args: {
    tone: 'success',
    leadingIcon: <CheckCircle2 size={12} />,
    children: 'Verifier passed',
  },
};

export const Warning: Story = {
  args: {
    tone: 'warning',
    leadingIcon: <CircleAlert size={12} />,
    children: 'Approval pending',
  },
};

export const Danger: Story = {
  args: {
    tone: 'danger',
    leadingIcon: <ShieldAlert size={12} />,
    children: 'High risk',
  },
};

