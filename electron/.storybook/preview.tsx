import type { Preview } from '@storybook/react';
import React from 'react';
import { applyThemeToDocument, type Theme } from '../src/renderer/design-system/themes';
import '../src/renderer/styles/globals.css';

const preview: Preview = {
  globalTypes: {
    theme: {
      name: 'Theme',
      description: 'Global DS Agent theme',
      defaultValue: 'dark',
      toolbar: {
        icon: 'mirror',
        items: [
          { value: 'dark', title: 'Dark' },
          { value: 'light', title: 'Light' },
          { value: 'high-contrast', title: 'High Contrast' },
        ],
      },
    },
  },
  decorators: [
    (Story, context) => {
      applyThemeToDocument(context.globals.theme as Theme);
      return (
        <div className="min-h-screen bg-ds-bg p-ds-6 text-ds-text">
          <Story />
        </div>
      );
    },
  ],
  parameters: {
    layout: 'centered',
    backgrounds: { disable: true },
    controls: { expanded: true },
  },
};

export default preview;

