import React from 'react';
// PR-UI-18-4 repair: the preview previously imported a dead JS barrel
// (`../src/design-system`) plus `styles/global.css` / `styles/animations.css`
// that no longer exist — `build-storybook` failed with
// "Could not resolve ../src/design-system". Mirror the app's real global
// CSS chain instead (the main.tsx subset the primitives consume):
// theme.css (base vars), macos.css (component classes + font),
// design-system/tokens.css (canonical --mac-* scale).
import '../src/styles/theme.css';
import '../src/styles/macos.css';
import '../src/design-system/tokens.css';

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
        // Canonical --mac-bg-primary values (src/design-system/tokens.css):
        // light = #eef3fa, dark = #1c1c1e.
        { name: 'light', value: '#eef3fa' },
        { name: 'dark', value: '#1c1c1e' }
      ]
    }
  },
};

export default preview;
