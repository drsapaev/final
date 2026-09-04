import React from 'react';
import { ThemeProvider } from '../src/contexts/ThemeContext';
// Real app stylesheets — mirrors src/main.tsx import set (minus admin.css,
// which is admin-panel-specific and irrelevant to primitive stories).
// PR-UI-18-2 repair: previous preview.js imported dead paths
// ('../src/design-system' JS module, 'styles/global.css', 'styles/animations.css')
// left over from a pre-remediation project structure — Storybook could not load.
import '../src/styles/theme.css';
import '../src/styles/dark-theme-visibility-fix.css';
import '../src/styles/global-fixes.css';
import '../src/design-system/tokens.css';
import '../src/styles/macos.css';

/** @type { import('@storybook/react').Preview } */
const preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
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
        // Values mirror design tokens: --mac-bg-primary (tokens.css L8 light,
        // L178 dark). The old preview read them from the dead designTokens JS
        // object; literals are used instead because .storybook/*.js is outside
        // the src/ token-scanner scope (ui-baseline.mjs codeFiles metric).
        { name: 'light', value: '#eef3fa' },
        { name: 'dark', value: '#1c1c1e' }
      ]
    }
  },
  decorators: [
    // ThemeProvider: required by useTheme() consumers (macos/Card, macos/Modal)
    // — useTheme throws outside a provider.
    (Story) => React.createElement(
      ThemeProvider,
      null,
      React.createElement(Story)
    ),
    (Story) => React.createElement(
      'div',
      {
        style: {
          fontFamily: 'var(--ui-font)',
          lineHeight: 1.5
        }
      },
      React.createElement(Story)
    )
  ]
};

export default preview;
