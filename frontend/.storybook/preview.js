import React from 'react';
import { designTokens } from '../src/design-system';
import '../src/design-system/styles/global.css';
import '../src/design-system/styles/animations.css';

/** @type { import('@storybook/react').Preview } */
const preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i
      }
    },
    docs: {
      toc: true
    },
    backgrounds: {
      default: 'light',
      values: [
        {
          name: 'light',
          value: designTokens.colors.secondary[50]
        },
        {
          name: 'dark',
          value: designTokens.colors.secondary[900]
        }
      ]
    }
  },
  decorators: [
    (Story) => React.createElement(
      'div',
      {
        style: {
          fontFamily: designTokens.typography.fontFamily.sans.join(', '),
          lineHeight: designTokens.typography.lineHeight.normal
        }
      },
      React.createElement(Story)
    )
  ]
};

export default preview;
