import type { Meta, StoryObj } from '@storybook/react';
import { useState } from 'react';
import { Accordion, type AccordionProps } from './Accordion';

const noop = () => undefined;

const meta = {
  title: 'Design System/Primitives/Accordion',
  component: Accordion,
  tags: ['autodocs'],
  args: {
    value: 'delivery',
    onValueChange: noop,
    items: [
      {
        value: 'delivery',
        title: 'Delivery policy',
        content: (
          <div className="space-y-ds-2">
            <p className="text-ds-sm leading-6 text-ds-muted">
              Outcome digests respect quiet hours and notify only the subscribed operator set.
            </p>
          </div>
        ),
      },
      {
        value: 'sessions',
        title: 'Session isolation',
        content: (
          <p className="text-ds-sm leading-6 text-ds-muted">
            Channel identity stays canonical so retries resume into the correct thread.
          </p>
        ),
      },
      {
        value: 'guards',
        title: 'Safety guards',
        content: (
          <p className="text-ds-sm leading-6 text-ds-muted">
            Sandbox violations block execution until the approval flow captures a human decision.
          </p>
        ),
      },
    ],
  },
} satisfies Meta<typeof Accordion>;

export default meta;

type Story = StoryObj<typeof meta>;

function AccordionStory(args: AccordionProps) {
  const [value, setValue] = useState<string | null>(args.value);

  return <Accordion {...args} value={value} onValueChange={setValue} />;
}

export const Default: Story = {
  args: {
    onValueChange: noop,
  },
  render: (args) => <AccordionStory {...(args as AccordionProps)} />,
};

export const NoCollapse: Story = {
  args: {
    value: 'delivery',
    onValueChange: noop,
    allowCollapse: false,
  },
  render: (args) => <AccordionStory {...(args as AccordionProps)} />,
};
