import type { Meta, StoryObj } from '@storybook/react';
import { Select } from './Select';

const meta = {
  title: 'Design System/Primitives/Select',
  component: Select,
  tags: ['autodocs'],
  args: {
    id: 'storybook-select',
    label: 'Theme',
    description: 'Choose the operator console surface tone.',
    value: 'dark',
    options: [
      { value: 'dark', label: 'Dark' },
      { value: 'light', label: 'Light' },
      { value: 'high-contrast', label: 'High Contrast' },
    ],
  },
} satisfies Meta<typeof Select>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const WithoutDescription: Story = {
  args: {
    description: undefined,
  },
};

